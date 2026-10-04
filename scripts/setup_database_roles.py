"""Provision dedicated demo roles and save generated credentials without printing them."""

from pathlib import Path
import secrets
import sys

from dotenv import dotenv_values, set_key
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.sql.database import connect


def setup_roles():
    env_path = ROOT / ".env"
    values = dotenv_values(env_path)
    credentials = {}
    # Reuse existing locally provisioned passwords; -- no silent rotation on rerun.
    for role, key in (("banking_reader", "QUERY_DATABASE_URL"), ("banking_audit", "AUDIT_DATABASE_URL")):
        config = conninfo_to_dict(values[key].replace("postgresql+psycopg://", "postgresql://", 1)) if values.get(key) else {}
        if config and (config.get("user") != role or not config.get("password")):
            raise ValueError("Existing runtime configuration does not match the dedicated role")
        credentials[role] = config.get("password") or secrets.token_urlsafe(32)
    with connect("admin") as connection:
        if connection.info.dbname != "banking_risk":
            raise ValueError("Provisioning is restricted to the banking_risk demo database")
        for role, password in credentials.items():
            row = connection.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if row:
                memberships = connection.execute("SELECT 1 FROM pg_auth_members WHERE member=%s", (row["oid"],)).fetchone()
                owned = connection.execute("""SELECT 1 FROM pg_shdepend
                    WHERE refclassid='pg_authid'::regclass AND refobjid=%s AND deptype='o' LIMIT 1""",
                                           (row["oid"],)).fetchone()
                if memberships or owned:
                    raise ValueError("Existing runtime role has memberships or owns objects; review manually")
            else:
                connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
            connection.execute(sql.SQL("ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}")
                               .format(sql.Identifier(role), sql.Literal(password)))
            connection.execute(sql.SQL("ALTER ROLE {} SET search_path TO pg_catalog, public").format(sql.Identifier(role)))
            connection.execute(sql.SQL("ALTER ROLE {} SET statement_timeout TO '5s'").format(sql.Identifier(role)))
        connection.execute("ALTER ROLE banking_reader SET default_transaction_read_only TO on")
        connection.execute("ALTER ROLE banking_audit SET default_transaction_read_only TO off")
        connection.execute((ROOT / "app/sql/migrations/004_runtime_permissions.sql").read_text())
        base = {key: value for key, value in connection.info.get_parameters().items()
                if key in {"host", "port", "dbname", "sslmode"}}
    # Automated credential provisioning preserves all unrelated dotenv values, including API keys.
    for role, key in (("banking_reader", "QUERY_DATABASE_URL"), ("banking_audit", "AUDIT_DATABASE_URL")):
        set_key(str(env_path), key, make_conninfo(**base, user=role, password=credentials[role]))
    if not values.get("ADMIN_DATABASE_URL") and values.get("DATABASE_URL"):
        set_key(str(env_path), "ADMIN_DATABASE_URL", values["DATABASE_URL"])
    print("Dedicated reader/audit roles provisioned; credentials saved privately in .env")


if __name__ == "__main__":
    try:
        setup_roles()
    except (ValueError, OSError, psycopg.Error):
        print("Role setup failed; inspect database availability, admin configuration and existing role ownership. Credentials are not printed.", file=sys.stderr)
        raise SystemExit(1)
