# Local FastAPI service

Install dependencies, apply audit migration, then run one local worker:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe scripts/setup_review_audit.py
.\.venv\Scripts\python.exe scripts/setup_database_roles.py
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

The PostgreSQL container and policy text index must already be ready. If port
8000 is occupied, use an unused port (for example 8001). Open
`http://127.0.0.1:8000/docs` for the interactive API, or `/openapi.json` for schema.
The [review workbench](workbench.md) is served at `/` on the same origin.
No API key is accepted in request bodies. DeepSeek reads the server's local `.env`.

| Endpoint | Behavior |
| --- | --- |
| GET /health | Process liveness only; not DB/model readiness |
| POST /reviews | Audited customer review; defaults to deterministic |
| GET /reviews/{request_id} | Stored audit status, metadata, policy refs and report |

Example from PowerShell (replace request ID when retrieving):

```powershell
$body = @{customer_id='C003'; mode='deterministic'} | ConvertTo-Json
$result = Invoke-RestMethod -Uri http://127.0.0.1:8000/reviews -Method Post -ContentType application/json -Body $body
$result.request_id
Invoke-RestMethod -Uri "http://127.0.0.1:8000/reviews/$($result.request_id)"
```

Explicitly set `mode=deepseek` to send synthetic evidence to the paid model API.
The POST response has request_id, status and report. Monetary values are strings.
Both succeeded and partial_success return HTTP 201 (a review record was created);
clients MUST inspect status and report.ai_generation, not assume 201 means AI
success. Partial AI failure retains the deterministic report. Audit failure is
never reported as success. Error responses contain sanitized codes and, when
the audited workflow was entered, a request ID.

Status mapping: 422 invalid input/over-capacity evidence, 404 unknown customer or
audit, 429 both review slots busy, 503 database/audit/configuration unavailable,
500 unexpected workflow failure. Validation, cross-origin and concurrency
rejections happen BEFORE review execution and are not review audit records.
No automatic retries or request idempotency: repeating a POST makes a new review
and may incur another model charge. GET lookups never regenerate an answer.

Synchronous handlers run blocking SQL/LLM work outside the event loop. There are
two concurrent review slots per process, not a distributed quota or rate limit.
This version waits for completion; long-running background jobs and disconnect
cancellation are not implemented. Closing the browser does not guarantee a
model call is cancelled. Future deployment needs an explicit timeout/job design.

The service now has local demo authentication and customer-scoped permissions.
Bind only to loopback; do not use 0.0.0.0 or publish it. Host filtering and
same-origin browser checks are additional boundaries. No permissive CORS is configured; a frontend
on another port will be rejected until deliberately integrated. Responses use
no-store. Report access requires a session and customer assignment (or admin role).
Production identity controls, HTTPS, request-size
limits, durable job management and anti-tamper audits remain future work.
Database query/audit roles are now separated; see [permissions](database-permissions.md).

`python -m unittest discover -s tests` covers API contracts using injected
services, including partial failures, sanitized errors, validation and concurrency.
Those tests do not call a paid API or require PostgreSQL.
With the service running, use `.venv\Scripts\python.exe scripts/evaluate_api.py`
for actual HTTP + PostgreSQL smoke checks. It retains two audit records (C003
success and C999 failure) and never requests DeepSeek mode.
It prompts for the local admin password, or accepts `--bootstrap-credentials`
to read the ignored temporary credential file without printing secrets.

Reference: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).
# Authentication Update

The API now requires a local login session for review creation and audit/report
lookup. Open the workbench to log in, or use `POST /auth/login` with a JSON
username/password and retain the HttpOnly cookie. See [user access](user-access.md)
for account provisioning, customer assignments, local-only limits and tests.
DeepSeek mode requires explicit `paid_consent: true`; earlier examples that omit
login/consent are no longer sufficient. Public health/assets/schema contain no
customer evidence. Unassigned historical records return 404.

