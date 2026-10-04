"""Verify positive and denied runtime privileges without modifying business rows."""

from pathlib import Path
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audit.customer_review import run_customer_review
from app.sql.database import connect


def deny(connection, statement, params=None):
    try:
        with connection.transaction():
            connection.execute(statement, params)
            raise AssertionError("An operation expected to be denied was allowed")
    except psycopg.errors.InsufficientPrivilege:
        return


def main():
    with connect() as reader:
        # Test ACL enforcement, not merely the connection's default read-only setting.
        reader.execute("SET TRANSACTION READ WRITE")
        identity = reader.execute("SELECT current_user AS name").fetchone()["name"]
        assert identity == "banking_reader"
        assert reader.execute("SELECT count(*) AS n FROM customers").fetchone()["n"] == 20
        for statement in (
            "UPDATE customers SET name=name WHERE false",
            "DELETE FROM transactions WHERE false",
            "UPDATE policy_chunks SET content=content WHERE false",
            "SELECT * FROM audit_logs LIMIT 0",
            "CREATE TABLE public.permission_probe(id int)",
            "CREATE TEMP TABLE permission_probe(id int)",
            "SET ROLE banking_owner",
        ):
            deny(reader, statement)
        print("PASS banking_reader reads allowed tables; business/policy writes, audit access, DDL and role escalation denied")

    report = run_customer_review("C003")
    request_id = report["request_id"]
    with connect("audit") as writer:
        identity = writer.execute("SELECT current_user AS name").fetchone()["name"]
        assert identity == "banking_audit"
        assert writer.execute("SELECT review_status FROM audit_logs WHERE request_id=%s", (request_id,)).fetchone()["review_status"] == "succeeded"
        for statement in (
            "SELECT * FROM customers LIMIT 0",
            "UPDATE customers SET name=name WHERE false",
            "DELETE FROM audit_logs WHERE false",
            "TRUNCATE audit_logs",
            "UPDATE audit_logs SET request_id=request_id WHERE false",
            "UPDATE audit_logs SET customer_id=customer_id WHERE false",
            "UPDATE audit_logs SET created_at=created_at WHERE false",
            "CREATE TABLE public.permission_probe(id int)",
            "SET ROLE banking_owner",
        ):
            deny(writer, statement)
        deny(writer, "UPDATE audit_logs SET elapsed_ms=elapsed_ms+1 WHERE request_id=%s", (request_id,))
        print("PASS banking_audit writes/reads reviews; customer access, deletion, identity mutation and terminal rewrites denied")
    with connect("admin") as admin:
        rows = admin.execute("""SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
                                 FROM pg_roles WHERE rolname IN ('banking_reader','banking_audit')""").fetchall()
        assert len(rows) == 2 and all(not row[key] for row in rows for key in
                                     ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"))
        assert not admin.execute("""SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
                                    WHERE r.rolname IN ('banking_reader','banking_audit')""").fetchone()
    print(f"PASS role flags/membership; retained verification review: {request_id}")


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error:
        print("Permission verification failed: database error (credentials suppressed)", file=sys.stderr)
        raise SystemExit(1)
