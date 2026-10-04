# Traceable customer reviews

Apply the additive migration once (safe to repeat), then use the normal CLI:

```powershell
.\.venv\Scripts\python.exe scripts/setup_review_audit.py
.\.venv\Scripts\python.exe scripts/review_customer.py C003
.\.venv\Scripts\python.exe scripts/read_review_audit.py REQUEST_UUID
.\.venv\Scripts\python.exe scripts/evaluate_review_audit.py
```

The customer review CLI now calls `run_customer_review`, the audited entry point.
The bare LangGraph builder and older workflow evaluation remain unaudited helpers;
future APIs must use the audited entry point, not invoke the graph directly.

Each attempt creates a UUID request ID and separately commits a `started` row in
the existing `audit_logs` table BEFORE configuring a model or querying customer
data. No generated SQL is used; `generated_sql` stays NULL. `review_metadata`
stores the reference time, requested model/configuration, workflow/prompt version,
SHA-256 of fixed query and workflow files, completed SQL evidence snapshot,
and (when composed for model generation) the input and actual prompt hashes.
Policy refs preserve document/chunk/corpus IDs, document version, content hash
and citation URL. `final_answer` stores the report as JSON text, including facts,
transactions, rules, full retrieved policy excerpts and accepted AI explanation.
Monetary values are strings, preserving decimal precision.

The terminal update commits in another short transaction. `succeeded` means the
workflow completed, NOT that a customer is safe or a model answer is accurate.
`partial_success` means SQL/rule evidence is available but AI generation failed.
`failed` preserves a sanitized error code, last/next execution stage and any
completed SQL evidence. SQL status is tracked separately. All failures return
the request ID. Partial AI failures still exit the review CLI with code 1.

Audit start failure prevents graph execution (`audit_start_unconfirmed`). An
unconfirmed terminal update never returns a successful audited report and raises
`audit_completion_unconfirmed`. Commit uncertainty may mean a record did commit;
inspect the request ID instead of claiming success or blindly repeating a paid
request. A killed/interrupted process leaves `started`; do not interpret that as
completed. Automatic stale-record reconciliation is not yet implemented.
Elapsed milliseconds cover work through terminal-update initiation, not the final
audit write itself. DB-created timestamps bound audit transaction timing.

No API key, DSN, password, environment dump or raw exception/model error body is
logged. Requested model names and file/prompt fingerprints do not guarantee exact
answer reproduction; there is no provider response ID, token accounting or model
artifact version from the cloud provider yet. Injected evaluation graphs are marked
`execution_adapter=injected`; the audit evaluation makes NO paid model calls and
retains its three success/failure/partial records for inspection.

This is local demo traceability, NOT immutable or bank-grade audit. Database owner
credentials can modify/delete records; separate roles, authentication, integrity
protection and retention controls are not all solved by traceability. Runtime
query/audit roles are now separated; see [permissions](database-permissions.md).
Retention rules, authentication and export controls remain future work. `user_role`
is the fixed `local_demo_operator` label, not verified user identity. Full synthetic
snapshots are stored; never use real customer records without a privacy/retention
design. Only the review CLI is audited, not the standalone policy-answer command.
