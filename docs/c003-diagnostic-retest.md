# C003 Single-call Retest

Authorized scope: risk_candidate only, one paid call, no retries. No other paid
scenario ran. Request ID: `4320205b-7699-49d9-ab44-5f92b6807634`.

Provider-reported usage: 2998 input + 756 output = 3754 tokens.
Generation succeeded, all existing automated probes passed, audit status was
succeeded and persistence confirmed. No failure diagnostic was generated because
this response was accepted. This run therefore does not exercise new diagnostics
against a real provider failure or explain the earlier rejected responses.

Focused review against the saved SQL snapshot confirmed the reported KYC/review
dates, score 85, one alert, eight transactions, SGD totals, cross-border counts,
transaction IDs/amounts/times, 60-minute interval and approximate ratio 0.9722.
The answer explicitly separates customer score 85 from demo threshold 80 and
qualifies cash-related policy evidence as background only. No automatic legal
decision was proposed.

Residual quality issues: candidate observations use transaction_count as their
fact reference rather than a dedicated candidate-pair reference; existing
transaction IDs provide provenance but membership validation alone does not
establish claim entailment. A generic no-rule caveat appears even though this
case has signals; it should not be interpreted as this customer's disposition.
This is a focused developer check, not independent compliance sign-off, broad
model accuracy or proof of stability across repeated calls.

Original source: ignored live-results.json and timestamped live snapshot in
data/evaluations. Older live snapshots remain preserved. Currency charges were
not queried; built-in estimates rely on an older pricing snapshot.

Remaining proposed paid scenarios: missing_policy and prompt_injection. These
require separate authorization; this single-case approval does not cover them.
