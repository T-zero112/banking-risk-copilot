# Customer review workbench

Open `http://127.0.0.1:8000/` with the local FastAPI server running. Static HTML,
CSS and vanilla JavaScript are served by the same FastAPI process; no separate
frontend server, build pipeline or permissive CORS is required. API docs remain
available at `/docs`. Provision the database/audit roles per `docs/api.md` first.

The screen uses real POST /reviews and GET /reviews/{request_id} responses. It
does not contain fabricated dashboard metrics or call a review automatically.
Fixed rules are the default. DeepSeek requires a per-submission confirmation of
API charges and transmission of synthetic evidence. A pending request disables
review/lookup controls; there are no automatic POST retries. Browser timeout or
disconnect can leave server work in progress, and the UI warns against repeating
a paid call. Duplicate guards are per page, not distributed idempotency.

Four views separate facts/rule signals, candidate transaction pairs and details,
verbatim policy citations, and audit metadata. AI fact/inference labels and cited
identifiers are displayed separately from deterministic evidence. Citation buttons
open the corresponding original policy chunk. Partial model failure retains the
SQL/rule report. Missing customers and other failures show request IDs when
available and allow lookup of saved failure records. Started audits are not
presented as successes or automatically resubmitted.

Only up to 12 request IDs and basic synthetic review labels are saved in browser
sessionStorage (per-tab browsing history); reports/API keys are not stored there.
Clearing browsing history does NOT delete database audits. Any known request UUID
can be queried. Copy/download actions export the selected request/report; no API
key field exists in the browser. Untrusted data is HTML-escaped and external policy
links accept HTTPS only. The page uses a self-hosted script CSP and no third-party
fonts, analytics or runtime CDN requests. Lucide 1.50.0 is vendored with its ISC
license. These measures do not replace authentication, access control or review
of generated prose. The application remains local-only and synthetic-data-only.

The frontend-design skill's Swiss direction uses white/neutral surfaces, hairline
rules and a red active accent. The interface is a work surface, not a landing page.
All numbers come from selected reports. Empty, processing, partial, failed and
unfinished states have distinct copy. Reduced-motion preferences, labeled inputs,
keyboard tabs, focus outlines and status announcements are supported.

## Browser verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui-test.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/verify_workbench.py
```

Verification uses actual C003 and missing-customer requests (retaining their audits),
plus intercepted responses for AI success/failure, consent, escaped content and
duplicate submission. No paid model requests are made. Desktop/mobile screenshots
at 390/768/1440 px are written to ignored `data/ui-qa/`. The script also checks
policy expansion, audit lookup and JSON download. Browser checks are not a full
accessibility audit or a factual-correctness benchmark for generated explanations.
