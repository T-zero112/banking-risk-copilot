# Demo Walkthrough and Handoff

## Prepare Without Provider Charges

Start Docker Desktop. From the repository root:

```powershell
.\start.ps1 -CheckOnly
.\start.ps1
```

For first setup use the [deployment guide](deployment.md), not a destructive reset.
Open http://127.0.0.1:8000/ or the printed alternate port. Use the locally
provisioned account; never place credentials in slides, screenshots or commits.
Do not select paid mode during this free walkthrough. Existing saved reviews
can be read without generating new explanations.

## Five-minute Demonstration

1. Explain the boundary: synthetic banking data, two public SPF/STRO snapshots,
   human review, not laundering detection or legal advice.
2. Run a deterministic C003 review. Show KYC status, score 85, transaction totals,
   candidate pair T00038/T00039, and why matching amounts do not prove fund tracing.
3. Inspect policy citations and source locators. Explain that cash applicability
   is not established, and MAS/FATF are not active corpus sources.
4. Run deterministic C004 as an authorized admin. Show no demo rule triggered,
   not a clean bill of health. A C003-only reviewer must not access C004.
5. Show the review request ID and persisted evidence/audit status. Explain partial
   success on model failure and audit-start blocking. For saved AI history, use
   [final evaluation](final-evaluation.md) rather than triggering paid calls.
6. Show the architecture and a documented failed-output diagnostic. Explain the
   improvements driven by real failures and their remaining semantic limits.

Do not reuse an admin session when demonstrating reviewer isolation: log out and
log in as the assigned reviewer. Existing reports are sensitive local artifacts;
use redacted docs, not complete downloads, in public presentations.

## Free Verification Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py
.\.venv\Scripts\python.exe scripts/check_release.py
```

The free suite writes local test audits; it is not side-effect-free. The release
guard checks paths only, not arbitrary secret content. Fresh-environment testing
is optional and consumes disk/downloads; see verify_deployment.py instructions.

## Before Public Release

Use the [production gap register](production-roadmap.md) to discuss next steps
in interviews. It is a proposal, not implemented controls or bank approval.

- Review candidate file contents for secrets; exclude .env, credentials, auth/session
  databases, runtime logs, model answers and audit snapshots. No real banking data.
- Review attribution and redistribution rights before publishing public PDF caches;
  a public URL alone does not imply unrestricted redistribution.
- Confirm repo URL, license choice and desired publication scope with the owner.
  No remote repository, commit, push, license or hosting is created by this handoff.
- Record a short demo and use the limitations above. Do not claim regulatory
  compliance, benchmark accuracy, general prompt-injection protection or Text-to-SQL.

## Resume-ready Description

Built a local banking-risk portfolio copilot combining fixed PostgreSQL analytics,
LangChain policy retrieval and LangGraph review orchestration, with optional
DeepSeek explanations, customer-scoped access and traceable audits. Added safe
schema diagnostics and evidence-reference validation, verified through 116 unit
tests and 11 free fixture scenarios; conducted bounded live smoke tests and
documented failures and limitations. Used synthetic data and SPF/STRO snapshots.

This description reflects engineering evidence, not measured business impact.
