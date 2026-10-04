"""Generate fixtures, start the local PostgreSQL service, and verify it."""

import subprocess
import sys

from generate_synthetic_data import ROOT, write_dataset


def main():
    write_dataset(ROOT / "data" / "synthetic", seed=42)
    try:
        subprocess.run(["docker", "compose", "config", "--quiet"], cwd=ROOT, check=True)
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "db"],
            cwd=ROOT, check=True,
        )
        subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_database.py")],
                       cwd=ROOT, check=True)
    except FileNotFoundError:
        print("Docker CLI was not found. Install Docker Desktop and start its engine.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError:
        print("Setup failed. Inspect docker compose ps and docker compose logs db. "
              "Existing database data has not been reset.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
