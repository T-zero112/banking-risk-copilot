"""Provision local accounts interactively; optional demo bootstrap stores temporary credentials locally."""

import argparse
from getpass import getpass
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.api.auth import AuthStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--username")
    parser.add_argument("--role", choices=("admin", "reviewer"))
    parser.add_argument("--customer", action="append", default=[])
    args = parser.parse_args()
    store = AuthStore()
    store.initialize()
    if args.bootstrap:
        with store.connect() as db:
            if db.execute("SELECT count(*) FROM users").fetchone()[0]:
                raise SystemExit("Accounts exist; bootstrap will not overwrite them")
        credentials = ROOT / "data/auth/bootstrap-credentials.txt"
        values = []
        for username, role, customers in (("admin", "admin", []), ("reviewer", "reviewer", ["C003"])):
            password = secrets.token_urlsafe(20)
            store.set_user(username, password, role, customers)
            values.append(f"{username}: {password}")
        credentials.write_text("Temporary local demo passwords. Rotate using setup_local_accounts.py, then delete this file.\n" + "\n".join(values), encoding="utf-8")
        print("Created admin and reviewer (C003 only). Credentials in ignored data/auth/bootstrap-credentials.txt")
    else:
        if not args.username or not args.role:
            parser.error("Supply --username and --role")
        password = getpass("New password (12+ characters): ")
        if password != getpass("Confirm password: "):
            raise SystemExit("Passwords do not match")
        store.set_user(args.username, password, args.role, args.customer)
        print("Account updated; existing sessions revoked")


if __name__ == "__main__":
    main()
