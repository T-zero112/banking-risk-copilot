# Local PostgreSQL

Prerequisites: Python and a running Docker Desktop Linux engine. No local psql or
Python database driver is required for this milestone.

From the repository root:

```powershell
python scripts/setup_database.py
```

The script generates the default fixtures, starts the Compose database, waits for
readiness, and verifies row counts and the three MVP queries. The first run pulls
the pinned pgvector image and initializes the database. Later runs reuse the
named volume; they do not reload the regenerated seed or overwrite database rows.
Verification reports a mismatch if existing data differs from the fixtures.

Default maintenance/admin connection (not the runtime application connection):

```text
postgresql+psycopg://banking_owner:banking_local_dev@127.0.0.1:55432/banking_risk
```

The credentials are for local synthetic data development. The service binds only
to loopback. Optional `POSTGRES_PORT` and `POSTGRES_PASSWORD` values in `.env` are
read by Compose. Keep `DATABASE_URL` in sync when changing either value. Changing
the password variable does not change an existing database user's password.

The image includes pgvector, and `extensions.sql` enables it during first-time
initialization. Chunk tables and embedding dimensions will be added during RAG
ingestion. `banking_owner` is an initialization/admin account; create separate
runtime permissions using `scripts/setup_database_roles.py` before running the
review/API. See [runtime permissions](database-permissions.md) for the three
connection settings and fail-closed behavior.

Useful commands:

```powershell
python scripts/verify_database.py
docker compose ps
docker compose logs --tail 50 db
docker compose exec db psql -U banking_owner -d banking_risk
docker compose stop db
docker compose up -d --wait db
```

Stopping the service preserves its data. Schema changes require explicit
migrations after the first initialization. Do not delete the volume to apply a
schema change to data you need to preserve.

References: [pgvector image](https://github.com/pgvector/pgvector#docker) and
[Docker Compose readiness](https://docs.docker.com/compose/how-tos/startup-order/).
