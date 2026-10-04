# Compliance-Aware Banking Risk Copilot

An AI portfolio project for banking risk and compliance analysis.

## Quick Start (Windows / Python 3.12)

Start Docker Desktop, then run `./start.ps1 -InstallDependencies -Initialize`
for first setup, or `./start.ps1` for daily startup. Provider keys are optional
for deterministic reviews. Use `./start.ps1 -CheckOnly` for configuration/runtime
checks without installation or initialization. See [deployment and reproduction](docs/deployment.md)
for policy caches, account setup, exact dependency lock and isolated verification.

## Portfolio Delivery

This is a local synthetic-data portfolio MVP, not a bank production system.
SQL uses fixed, inspectable queries; Text-to-SQL is not implemented. The current
policy corpus contains two SPF/STRO source snapshots, not MAS/FATF coverage.

- [Architecture and trust boundaries](docs/architecture.md)
- [Final evaluation and release scope](docs/final-evaluation.md)
- [Free demo walkthrough and handoff](docs/demo-handoff.md)
- [Production gaps and staged roadmap (proposal only)](docs/production-roadmap.md)

Current verification: 116 unit tests and 11 free review scenarios passed.
The latest missing-policy live retest passed with 2718 tokens; other latest
scenario results come from earlier revisions. No general accuracy or injection
security claim is made. Publication and independent analyst sign-off are pending.

## Implementation History

The following entries describe successive historical revisions, not one unified
latest-version acceptance run. Use the final evaluation above for current scope.

SQL fixture analytics, document ingestion, lexical/multilingual retrieval, and
a SQL + policy review workflow run locally, with optional DeepSeek explanations.
DeepSeek policy answers and one C003 review were live-smoke-tested; general answer
accuracy is not established. Customer reviews now persist traceable audit records.
The local review workbench, FastAPI API and separate query/audit DB roles are available.
Text-to-SQL remains a project goal. Local login and customer-scoped API access
are now available; see [user access](docs/user-access.md). Only two
SPF policy snapshots are currently ingested; MAS/FATF sources remain unavailable.

The 2026-10-02 evaluation passed eight free contract scenarios. All four new live
review explanations were rejected by evidence-reference validation; SQL reports
were retained as partial successes. This is not an AI quality pass. See
[evaluation results and costs](docs/evaluation-report.md).
On 2026-10-03, safe diagnostic paths, prompt reference allowlists and explicit
numeric-label validation passed ten free scenarios and 66 unit tests. No new
paid calls were made; live acceptance after these changes is not yet established.
Subsequently, one authorized C003 live retest succeeded with 3541 tokens and
confirmed audit persistence. Other scenarios remain unverified after the fix;
see [single live retest](docs/live-retest-2026-10-03.md).
The remaining three scenarios were subsequently called once each: no-rule output
was rejected by numeric validation; missing-policy and injection outputs were
accepted, but missing-policy prose did not explicitly acknowledge absent evidence.
See [follow-up assessment](docs/live-followup-2026-10-03.md); this is not a complete
quality pass or a general injection-resistance claim.
On 2026-10-04, the updated no-rule and missing-policy cases both passed local
validation and persisted audits, with explicit policy notices. A generated
suggestion still confused score 85 with threshold 80, so this is not a complete
semantic quality pass. See [two-case retest](docs/two-case-retest-2026-10-04.md).
The subsequent free score/threshold fix passed 71 unit tests and 11 evaluation
scenarios, without new model calls. Suggested-check numeric assertions are now
checked with documented heuristic limitations; see
[score/threshold validation](docs/score-threshold-validation.md).

Offline historical replay deduplicates 11 attempts: five retained answers can be
revalidated, with four accepted and one rejected for score/threshold confusion.
Five rejected bodies were not retained; one attempt stopped before generation.
No new model calls are made. See [historical replay summary](docs/historical-replay.md).
This does not validate the latest prompt or establish model accuracy.
The subsequent authorized four-case live batch used 12005 tokens: only the
no-rule case was accepted; three returned invalid_model_output with insufficient
diagnostics. SQL reports and all audit records were retained. See
[four-case live assessment](docs/live-four-case-2026-10-04.md).
Privacy-safe JSON/schema diagnostics were subsequently added without paid calls;
105 unit tests and 11 free scenarios passed. See
[generation diagnostics](docs/generation-diagnostics.md). Earlier rejected bodies
cannot be retrospectively diagnosed because they were not retained.
A subsequent authorized C003-only call passed with 3754 tokens and confirmed
audit persistence. Score 85 and threshold 80 were explicitly distinguished;
real failure diagnostics remain unexercised by this successful call. See
[C003 diagnostic retest](docs/c003-diagnostic-retest.md).
The remaining two authorized calls used 6514 tokens and both failed schema
validation: observations[3] and observations[4] had too-short fact_refs. Safe
diagnostics and partial-success audit persistence worked; injection resistance
and missing-policy prose remain unverified. See
[remaining two-case diagnostic retest](docs/remaining-two-diagnostic-retest.md).
A free contract correction adds candidate-pair references with mandatory paired
transaction provenance, while keeping observations evidence-required. 111 unit
tests and 11 free scenarios passed; no live acceptance is established for this
prompt yet. See [candidate-pair contract](docs/candidate-pair-contract.md).
The two authorized pair-contract retests both passed automated validation and
audit persistence, using 6756 tokens. Missing-policy prose still contains a
contradictory retrieved-indicator caveat; semantic quality is not fully passed.
The injection answer ignored this single saved attack, not a general security
benchmark. See [pair-contract live retest](docs/pair-contract-live-retest.md).
The contradictory missing-policy caveat is now rejected by a free narrow
presence-assertion check; 116 unit tests and 11 free scenarios passed. Offline
replay rejects the saved offending suggestion and still accepts the injection
answer. New-prompt live quality remains untested. See
[policy-presence validation](docs/policy-presence-validation.md).
One authorized missing-policy wording retest passed with 2718 tokens and confirmed
audit persistence; the targeted contradictory wording was absent on focused
review. This is one call, not a stability benchmark. See
[missing-policy wording live retest](docs/policy-presence-live-retest.md).

Run `.venv\Scripts\python.exe scripts/review_customer.py C003` for the combined
workflow; append `--mode deepseek` for a paid Chinese AI explanation.
See [customer review](docs/customer-review.md) for scope and safeguards.
Apply `scripts/setup_review_audit.py` before using the review CLI; see
[review audit](docs/review-audit.md) for request lookup and failure semantics.
See [local API](docs/api.md) for FastAPI startup and interactive documentation.
Open `http://127.0.0.1:8000/` for the [review workbench](docs/workbench.md).
Provision runtime connections with `scripts/setup_database_roles.py`; see
[database permissions](docs/database-permissions.md).

The system combines:

- SQL analytics over synthetic banking customer, account, transaction, risk score, and alert data
- RAG over public AML/KYC policy documents
- LangGraph workflow orchestration
- LangChain retrieval and LLM components
- SQL safety checks, citations, role-aware access, and audit logging

## MVP Scope

The first version focuses on AML risk analysis:

1. Find customers with high-value transactions in the last 30 days.
2. Find customers with incomplete KYC but high transaction activity.
3. Explain why a customer may require AML review using transaction data and policy evidence.

## Data Sources

- Structured data: synthetic banking data generated locally.
- Policy documents: two ingested public SPF/STRO sources under `data/policies/`;
  MAS/FATF sources are catalogued but not ingested.

No real customer or bank-internal data is used.

## Project Structure

```text
app/
  api/       FastAPI endpoints
  graph/     LangGraph workflow nodes and graph definition
  rag/       Document loading, chunking, embeddings, retrieval
  sql/       Schema helpers, fixed analytics queries and execution
  audit/     Audit log models and writers
data/
  synthetic/ Generated CSV or seed data
  policies/  Public policy documents for RAG
scripts/     Data generation, ingestion, evaluation scripts
evals/       Evaluation questions and expected checks
notebooks/   Exploratory analysis
docs/        Architecture notes and diagrams
```

## First Milestone

The initial schema is in `app/sql/schema.sql`. See [schema notes](docs/schema.md)
for field meanings, analytics assumptions, and validation boundaries.

- Define the PostgreSQL schema.
- Generate synthetic banking data.
- Load sample policy documents.
- Run basic SQL queries against the synthetic dataset.

Generate the deterministic SGD dataset with:

```powershell
python scripts/generate_synthetic_data.py
```

See [synthetic data instructions](docs/synthetic-data.md) for expected results,
time boundaries, and PostgreSQL loading commands.

## Local Database

With Docker Desktop running, initialize and verify PostgreSQL with pgvector:

```powershell
python scripts/setup_database.py
```

See [local database instructions](docs/local-database.md) for connection settings,
verification, and stopping the service without deleting data.

## Public Policy Documents

Download official source snapshots, extract cited pages/sections, and register
document metadata with the database running:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-policy.txt
.\.venv\Scripts\python.exe scripts/ingest_policy_documents.py
.\.venv\Scripts\python.exe scripts/verify_policy_documents.py
```

See [policy corpus notes](docs/policy-corpus.md) for verified source coverage,
download failures, reproduction, and parsing checks. MAS/FATF download failures
are recorded explicitly; they are not counted as ingested documents.

## Policy Retrieval

Build citation-preserving LangChain chunks and search the PostgreSQL text index:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
.\.venv\Scripts\python.exe scripts/build_policy_index.py
.\.venv\Scripts\python.exe scripts/search_policies.py "matching payments credits" --top-k 3
.\.venv\Scripts\python.exe scripts/evaluate_policy_retrieval.py
```

See [policy retrieval instructions](docs/policy-retrieval.md). This milestone uses
English full-text retrieval without embeddings or model API calls.

# Multilingual semantic retrieval

Local embeddings, pgvector search, and a LangGraph evidence/answer workflow are
available. See [semantic retrieval](docs/semantic-retrieval.md) for setup,
Chinese queries, optional paid generation, and limitations.
