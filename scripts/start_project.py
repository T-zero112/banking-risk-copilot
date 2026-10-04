"""Explicit initialization and non-destructive daily startup of the localhost demo."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class StartupError(ValueError):
    """Only locally authored, credential-free diagnostics may be printed."""


def run(arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def check_dependencies():
    if sys.version_info[:2] != (3, 12):
        raise StartupError("Validated runtime requires Python 3.12")
    for line in (ROOT / "requirements-lock.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        package, expected = line.split(";", 1)[0].strip().split("==")
        if "sys_platform" in line and sys.platform != "win32":
            continue
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            raise StartupError("Locked dependency missing; use -InstallDependencies") from None
        if actual != expected:
            raise StartupError("Dependency versions differ; install requirements-lock.txt")


def configuration(initialize, db_port=None):
    from dotenv import dotenv_values, set_key, load_dotenv
    from psycopg.conninfo import make_conninfo
    path = ROOT / ".env"
    if not path.exists():
        if not initialize:
            raise StartupError("Missing .env; run explicit initialization or configure from .env.example")
        shutil.copyfile(ROOT / ".env.example", path)
        password = secrets.token_urlsafe(32)
        port = db_port or 55432
        for key, value in {"POSTGRES_PASSWORD":password, "POSTGRES_PORT":str(port),
            "ADMIN_DATABASE_URL":make_conninfo(host="127.0.0.1", port=port, dbname="banking_risk", user="banking_owner", password=password),
            "DATABASE_URL":""}.items():
            set_key(str(path), key, value)
    values = dotenv_values(path)
    if db_port is not None and str(db_port) != values.get("POSTGRES_PORT"):
        raise StartupError("Requested database port conflicts with existing configuration; no configuration overwritten")
    load_dotenv(path, override=False)
    if initialize and not values.get("ADMIN_DATABASE_URL"):
        raise StartupError("Missing ADMIN_DATABASE_URL for initialization; existing configuration was not overwritten")


def initialize(offline):
    from app.sql.database import connect
    from app.api.auth import AuthStore
    if not (ROOT / "data/synthetic/seed.sql").exists():
        run([sys.executable, "scripts/generate_synthetic_data.py"])
    run(["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "db"])
    # Additive migrations only; no schema recreation, volume deletion or data reset.
    with connect("admin") as connection:
        for migration in ("001_policy_retrieval.sql", "002_policy_embeddings.sql", "003_customer_review_audit.sql"):
            connection.execute((ROOT / "app/sql/migrations" / migration).read_text())
        indexed = connection.execute("SELECT 1 FROM policy_retrieval_state WHERE singleton").fetchone()
    if not indexed:
        args = [sys.executable, "scripts/ingest_policy_documents.py"]
        if offline:
            args.append("--offline")
        run(args)
        run([sys.executable, "scripts/build_policy_index.py"])
    run([sys.executable, "scripts/setup_database_roles.py"])
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / ".env")
    for key in ("QUERY_DATABASE_URL", "AUDIT_DATABASE_URL"):
        os.environ[key] = values[key]
    auth = AuthStore()
    auth.initialize()
    with auth.connect() as db:
        accounts_exist = db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if not accounts_exist:
        run([sys.executable, "scripts/setup_local_accounts.py", "--bootstrap"])


def ready():
    from app.api.auth import AuthStore
    from app.sql.database import connect
    from dotenv import dotenv_values
    values = dotenv_values(ROOT / ".env")
    for key in ("QUERY_DATABASE_URL", "AUDIT_DATABASE_URL"):
        if not values.get(key):
            raise StartupError(f"Missing {key}; run explicit initialization")
    with connect() as db:
        if not db.execute("SELECT 1 FROM policy_retrieval_state WHERE singleton").fetchone():
            raise StartupError("Policy corpus not initialized; initialize with verified policy snapshots")
    with connect("audit") as db:
        db.execute("SELECT request_id FROM audit_logs LIMIT 1")
    with AuthStore().connect() as db:
        if not db.execute("SELECT 1 FROM users WHERE active=1 AND role='admin' LIMIT 1").fetchone():
            raise StartupError("No active local admin; provision accounts explicitly")


def read_health(port):
    with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
        return json.load(response)


def start_api(port):
    instance = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    with socket.socket() as probe:
        occupied = probe.connect_ex(("127.0.0.1", port)) == 0
    if occupied:
        health = read_health(port)
        if health.get("instance") != instance or health.get("app") != "banking-risk-copilot":
            raise StartupError("Port occupied by another service; select --port explicitly")
        print(f"Existing project API: http://127.0.0.1:{port}/")
        return
    logs = ROOT / "data/runtime"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / f"api-{port}.stdout.log").open("ab") as stdout, (logs / f"api-{port}.stderr.log").open("ab") as stderr:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-proxy-headers"],
            cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt")
    for _ in range(60):
        if process.poll() is not None:
            raise StartupError("API exited; inspect ignored data/runtime logs")
        try:
            if read_health(port).get("instance") == instance:
                print(f"API started: http://127.0.0.1:{port}/ (PID {process.pid})")
                return
        except Exception:
            pass
        time.sleep(.5)
    process.terminate()
    process.wait(timeout=10)
    raise StartupError("API did not become live; startup process stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--offline-policies", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-port", type=int)
    parser.add_argument("--project-name", help="Explicit separate Compose project, primarily for isolated verification")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or (args.db_port is not None and not 1024 <= args.db_port <= 65535):
        raise StartupError("Ports must be in 1024-65535")
    if args.project_name:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,60}", args.project_name):
            raise StartupError("Invalid Compose project name")
        os.environ["COMPOSE_PROJECT_NAME"] = args.project_name
    check_dependencies()
    configuration(args.initialize, args.db_port)
    # Require an already-running engine; do not install Docker or start unrelated projects.
    try:
        subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise StartupError("Docker engine unavailable; start Docker Desktop, then retry. No data was reset") from None
    if args.initialize:
        initialize(args.offline_policies)
    elif not args.check_only:
        run(["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "db"])
    ready()
    print("PASS runtime, restricted DB access, policy index and local accounts; no model calls")
    if not args.check_only:
        start_api(args.port)


if __name__ == "__main__":
    try:
        main()
    except StartupError as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        # Never print DSNs, raw database errors, environment values or login credentials.
        print("Startup failed. Check Python 3.12/locked packages, Docker engine, .env runtime roles, policy cache and local accounts. Existing data was not reset.", file=sys.stderr)
        raise SystemExit(1)
