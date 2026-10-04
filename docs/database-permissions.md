# Runtime database permissions

Provision after business, policy, embedding and audit tables exist:

```powershell
.\.venv\Scripts\python.exe scripts/setup_database_roles.py
.\.venv\Scripts\python.exe scripts/verify_database_permissions.py
```

Setup applies migration 004 without recreating tables or deleting data. Generated
random passwords are saved in ignored `.env` through a dotenv-aware updater;
unrelated values and API keys are preserved. Reruns reuse passwords. Existing
roles with memberships or object ownership are rejected for manual review.
Do not share/print the dotenv file. PUBLIC privileges are revoked in the dedicated
banking_risk database, including temporary tables/schema CREATE; do not apply this
to a shared database containing unrelated applications.

| Purpose | Role | Config | Allowed |
| --- | --- | --- | --- |
| Business and policy/vector queries | banking_reader | QUERY_DATABASE_URL | SELECT on 11 named tables |
| Audit persistence and lookup | banking_audit | AUDIT_DATABASE_URL | SELECT audits, INSERT start columns, UPDATE 8 completion columns |
| Schema/data/index maintenance | banking_owner | ADMIN_DATABASE_URL | Admin maintenance only |

`connect()` defaults to query; the audit store explicitly uses `connect('audit')`.
Only explicit `connect('admin')` accepts legacy DATABASE_URL as a maintenance
fallback. Runtime keys missing, malformed, or naming an admin user fail closed.
Index builders/migrations use admin; older Docker/psql ingestion and fixture
scripts remain maintenance tools. Restart the API when changing credentials,
because dotenv does not overwrite environment values already loaded by a process.

Runtime roles have no elevated flags or memberships. They cannot become owner or
create tables. The reader defaults to read-only, but verification switches that
off to prove writes are denied by actual grants. New tables are not automatically
granted; update the allowlist explicitly. The audit role cannot DELETE/TRUNCATE or
change request/customer identity and creation time. A trigger permits completing
a started record once, requires timing fields and preserves initial metadata.

This is NOT authentication, per-customer authorization or immutable audit. The
writer can fabricate new records; admin can modify/delete records. Runtime roles
can read all allowed synthetic rows. Workspace admin credentials and the Compose
demo owner password still exist locally; this is not process/filesystem isolation
against someone controlling the machine. Before deployment, remove admin secrets
from runtime configuration, rotate demo credentials, add user/customer access
controls and design retention/integrity protection. Verification makes no paid
model calls and retains one synthetic C003 audit.

References: [PostgreSQL GRANT](https://www.postgresql.org/docs/17/sql-grant.html),
[PostgreSQL roles](https://www.postgresql.org/docs/17/sql-createrole.html).
