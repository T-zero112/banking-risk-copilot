# Synthetic Data Milestone

Run from the repository root with Python (standard library only):

```powershell
python scripts/generate_synthetic_data.py
```

This writes five CSV files, `seed.sql`, and `manifest.json` to `data/synthetic/`.
Generated direction and cross-border columns are intentionally omitted from
inserts. PostgreSQL computes them. All names and account identifiers are synthetic.
The balances are illustrative snapshots, not reconciled ledger balances.

The seed defaults to 42, and the reference time is fixed at
`2026-10-01T00:00:00+08:00`. Re-running overwrites generated files reproducibly.
Queries use the same reference time and the interval `[as_of - 30 days, as_of)`.
The thresholds below are demo assumptions, not regulatory requirements.

| Scenario | Expected result |
| --- | --- |
| At least one SGD transaction >= 10,000 in the window | C001, C003, C006 |
| Incomplete KYC and >= 20 SGD transactions in the window | C002 (24 transactions) |
| Review evidence for C003 | Expired KYC, AML score 85, 2 cross-border transactions, 1 unresolved alert |
| C004 high-value transaction 31 days ago | Excluded |
| C005 high-value transaction exactly at reference time | Excluded |
| C006 transaction exactly at the window start | Included |

No country is classified as high risk in this dataset. `synthetic-demo-v1` is a
demo classification label, not a MAS or FATF list. Review evidence is a set of
facts for later RAG grounding; it does not establish misconduct. KYC fields are
current snapshots, so the evidence query is not a full historical reconstruction.

Load into an empty PostgreSQL database with `psql` (using your configured connection):

```powershell
psql -v ON_ERROR_STOP=1 -d banking_risk -f app/sql/schema.sql
psql -v ON_ERROR_STOP=1 -d banking_risk -f data/synthetic/seed.sql
psql -v ON_ERROR_STOP=1 -d banking_risk -f app/sql/queries/high_value_customers.sql
psql -v ON_ERROR_STOP=1 -d banking_risk -f app/sql/queries/incomplete_kyc_active.sql
psql -v ON_ERROR_STOP=1 -d banking_risk -f app/sql/queries/customer_review_evidence.sql
```

The schema and seed are one-time inserts, not idempotent migrations. Loading again
into the same database raises duplicate table or primary-key errors. CSV import
must treat empty cells as NULL. Policy documents and audit logs are left empty
until real public document ingestion and actual requests are implemented.
