"""Isolated Windows/Python 3.12 install and fresh DB verification; no provider calls."""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-python", action="store_true", help="Fast DB-only check; does NOT verify a fresh Python install")
    args = parser.parse_args()
    run_id = uuid4().hex[:12]
    workspace = ROOT / "data/deployment-check" / run_id
    workspace.mkdir(parents=True)
    # Explicit allowlist: never copy .env, account DBs, sessions, credentials or customer audits.
    for directory in ("app", "scripts", "tests"):
        shutil.copytree(ROOT / directory, workspace / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("compose.yaml", ".env.example", "requirements-lock.txt"):
        shutil.copyfile(ROOT / name, workspace / name)
    (workspace / "data/policies").mkdir(parents=True)
    for name in ("sources.json", "manifest.json"):
        shutil.copyfile(ROOT / "data/policies" / name, workspace / "data/policies" / name)
    # Public PDF cache only; offline extraction/indexing is re-run in the fresh DB.
    shutil.copytree(ROOT / "data/policies/raw", workspace / "data/policies/raw")
    env = os.environ.copy()
    for key in ("DATABASE_URL", "ADMIN_DATABASE_URL", "QUERY_DATABASE_URL", "AUDIT_DATABASE_URL",
                "POSTGRES_PASSWORD", "POSTGRES_PORT", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_MODEL"):
        env.pop(key, None)
    project = "rag-deploy-check-" + run_id
    env["COMPOSE_PROJECT_NAME"] = project
    api_port, db_port = free_port(), free_port()
    while db_port == api_port:
        db_port = free_port()
    python = Path(sys.executable)
    logs = workspace / "verification.log"
    success = False
    failure = None
    with logs.open("w", encoding="utf-8") as log:
        def run(command, cwd=workspace):
            subprocess.run([str(item) for item in command], cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        try:
            if not args.reuse_python:
                print("Creating independent Python environment and installing exact dependency lock", flush=True)
                run([sys.executable, "-m", "venv", workspace / ".venv"])
                python = workspace / ".venv/Scripts/python.exe" if os.name == "nt" else workspace / ".venv/bin/python"
                run([python, "-m", "pip", "install", "-r", "requirements-lock.txt"])
                run([python, "-m", "pip", "check"])
            print("Initializing isolated Compose project, database, policy index and new accounts", flush=True)
            run([python, "scripts/start_project.py", "--initialize", "--offline-policies", "--port", api_port, "--db-port", db_port, "--project-name", project])
            run([python, "-m", "unittest", "discover", "-s", "tests"])
            run([python, "scripts/evaluate_api.py", "--base-url", f"http://127.0.0.1:{api_port}", "--bootstrap-credentials"])
            # Test reviewer isolation with real DB-backed reports, never selecting DeepSeek mode.
            probe = """
import json, httpx
from pathlib import Path
accounts=dict(line.split(': ',1) for line in Path('data/auth/bootstrap-credentials.txt').read_text().splitlines() if ': ' in line)
with httpx.Client(base_url='http://127.0.0.1:PORT',trust_env=False) as client:
    assert client.get('/ready').status_code==200
    assert client.post('/auth/login',json={'username':'admin','password':accounts['admin']}).status_code==200
    created=client.post('/reviews',json={'customer_id':'C004'})
    assert created.status_code==201
    audit_id=created.json()['request_id']
    assert client.post('/auth/logout').status_code==200
    assert client.post('/auth/login',json={'username':'reviewer','password':accounts['reviewer']}).status_code==200
    assert client.post('/reviews',json={'customer_id':'C004'}).status_code==403
    assert client.get('/reviews/'+audit_id).status_code==404
    assert client.post('/reviews',json={'customer_id':'C003'}).status_code==201
    assert client.post('/reviews',json={'customer_id':'C003','mode':'deepseek'}).status_code==422
print('PASS fresh DB and new account isolation; no paid consent or model calls')
""".replace("PORT", str(api_port))
            run([python, "-c", probe])
            # Repeated daily startup must preserve account/DB state and reuse its own API.
            run([python, "scripts/start_project.py", "--port", api_port, "--project-name", project])
            success = True
        except Exception:
            failure = "verification_failed_see_private_log"
        finally:
            # Stop only this generated API, verifying its root hash before finding its process.
            import hashlib
            import httpx
            try:
                health = httpx.get(f"http://127.0.0.1:{api_port}/health", timeout=2, trust_env=False).json()
                if health.get("instance") == hashlib.sha256(str(workspace).encode()).hexdigest()[:16]:
                    # The endpoint exposes no PID. Find the isolated command by its chosen port.
                    if os.name == "nt":
                        command = f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match 'uvicorn app\\.api\\.main:app.*--port {api_port}( |$)' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }}"
                        subprocess.run(["powershell", "-NoProfile", "-Command", command], env=env, stdout=log, stderr=log, check=False)
            except Exception:
                pass
            # Keep this fresh named volume for diagnostics; never delete or touch the primary project.
            subprocess.run(["docker", "compose", "down"], cwd=workspace, env=env, stdout=log, stderr=log, check=False)
    result = dict(passed=success, fresh_python=not args.reuse_python, fresh_database=True,
                  public_policy_cache_reused=True, external_downloads_verified=False, paid_calls=0,
                  failure=failure,
                  compose_project=project, api_port=api_port, db_port=db_port, workspace=str(workspace))
    (workspace / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
