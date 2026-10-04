# SQL + policy review workflow

Run from the repository root with the database and policy text index ready:

```powershell
.\.venv\Scripts\python.exe scripts/setup_review_audit.py
.\.venv\Scripts\python.exe scripts/review_customer.py C003
.\.venv\Scripts\python.exe scripts/review_customer.py C003 --mode deepseek
.\.venv\Scripts\python.exe scripts/evaluate_customer_review.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

By default LangGraph executes load_sql -> assess -> retrieve_policy -> compose.
This default is deterministic and makes no paid API calls. Customer IDs
are explicit input; free-form question routing and text-to-SQL are not implemented.
Only two allowlisted, parameterized SELECT files execute in one repeatable-read,
read-only transaction with a 5-second statement timeout. More than 200 matching
transactions causes failure rather than a silently incomplete report. Database
connections now use banking_reader; audit writes use banking_audit. See
[database permissions](database-permissions.md). This is not customer authorization.

The reference time is fixed at 2026-10-01T00:00:00+08:00. Transactions are SGD only
and use [as_of - 30 days, as_of). KYC is a mutable snapshot, not historical KYC.
No customer name or counterparty name is needed for this workflow.

C003 has 8 transactions, SGD 18,000 incoming, SGD 18,897 outgoing, two cross-border
transactions, expired KYC, demo AML score 85 and one unresolved alert. The rule
identifies T00038 -> T00039 (18,000 -> 17,500 in 60 minutes, same account).
The 24-hour window, 0.9-1.1 amount ratio and score threshold 80 are demo choices,
not regulatory thresholds. Pairing is many-to-many and does not trace actual money.

English lexical retrieval finds the matching-payments indicator on SPF PDF page 3.
Its exact scope includes credits paid in by CASH. C003's credits are transfers;
therefore the report labels the citation CONTEXT ONLY, not direct evidence that
the indicator applies. KYC/score/alert signals have no fabricated policy citations.
Missing policy evidence is explicitly recorded. Human review is suggested, never
an automatic STR filing, misconduct verdict or declaration of low risk.

Reports expose relevant transaction IDs, facts, candidate pairs, rule reasons,
verbatim policy chunks and source metadata. Policy lookup uses the existing text
baseline for this fixed rule; multilingual embeddings remain available separately.
The CLI now persists [traceable audit records](review-audit.md) with a request ID.
API/UI, relevance/answer evaluation and bank-grade access controls remain future work.

## Optional DeepSeek explanation

Configure `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` in the ignored local `.env`, then
explicitly select `--mode deepseek`. The graph appends generate_explanation ->
validate_explanation. Original SQL facts, rules, policy snapshots, disposition
and limitations remain unchanged. `ai_explanation` separately contains Chinese
observations (fact versus inference), context-only policy comments and suggested
human checks. This does not automate STR reporting or create a misconduct verdict.

The API receives aggregate synthetic facts, candidate pairs, only the transactions
referenced by those pairs, policy excerpts and limitations. Unrelated transaction
details are omitted. Customer/account/transaction IDs are still sent; use only
synthetic data, never actual customer records without approved controls. Calls
are paid, use JSON mode, cap output at 4096 tokens, have a 60-second timeout and
no automatic retries. There is no automatic second model call to repair output.

Local checks enforce the expected customer, supplied fact keys, supplied transaction
IDs, policy citation identifiers, JSON schema and context-only applicability.
Explicit labelled AML scores, transaction counts, inbound totals and outbound totals
are also compared with SQL facts using decimal arithmetic (including comma grouping
and Chinese thousand/ten-thousand units). Labels must be immediately followed by
a number, optionally with a copula, colon and SGD prefix. Arbitrary paraphrases,
individual transaction amounts, hypothetical questions and unlabelled numbers are
not comprehensively verified. They do NOT prove semantic entailment, general numeric
accuracy, sound legal interpretation or resistance to prompt injection. Human review
and a broader answer evaluation dataset are still necessary.

On API, parsing or reference-validation failure the deterministic report is retained,
`ai_explanation` is omitted, `ai_generation.status` becomes `failed`, and the CLI exits
with code 1. Missing credentials fail before graph execution. Raw model/API error
bodies are not included in the report. The default command never calls a model.

A live C003 smoke request succeeded and preserved the cash-condition limitation;
this is one integration example, not a general accuracy benchmark. Unit tests use
fake generators and require neither API credentials nor paid network calls.

## Free Validation Update: 2026-10-03

Prompts now enumerate allowed bare fact keys, transaction IDs and policy numbers.
The prompt version is `review-explanation-v2`. Reference failures retain the
existing aggregate `invalid_evidence_references` error code, with an additional
`ai_generation.validation_diagnostic` containing a trusted code and schema path:

```json
{"code": "unknown_fact_reference", "path": "observations[0].fact_refs[0]"}
```

Other codes identify customer mismatch, unknown transactions/citations, blank
text and numeric mismatch. Numeric contradictions use the aggregate error code
`inconsistent_numeric_facts`. Diagnostics expose only the first failure; they
do not contain rejected prose, reference values, secrets or provider error bodies.
Parsing/API failures retain their existing safe aggregate codes. Reports and
their diagnostics are persisted by the existing audit path without a schema migration.

Run `scripts/evaluate_review_suite.py` without `--live` for ten free scenarios.
All ten and 66 unit tests passed on 2026-10-03, using fake model generators.
The four historical live failures remain unchanged; their exact reference errors
cannot be recovered from those stored reports. No paid retest was performed.
