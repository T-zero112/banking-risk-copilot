# Two-case Live Retest: 2026-10-04

Three free audit integration checks passed before calls. Only `no_demo_rule`
and `missing_policy` were selected, once each, without retries. The script now
supports repeated `--case` options to avoid unintended additional model calls.
The unit suite passed 68 tests. Historical batches remain timestamped snapshots.

| Scenario | Request ID | Input / output tokens | Local validation | Persisted audit |
| --- | --- | --- | --- | --- |
| C004 no demo rule | 78530604-c84c-473d-91c2-7c650e27c40f | 1370 / 415 | Accepted | succeeded |
| C003 missing policy | 52b69489-0de2-4163-89c1-46e8f26e399e | 1787 / 632 | Accepted | succeeded |

Audit statuses were independently read back. Assistant spot-check confirmed:

- C004: AML score 10, six transactions, no inbound total, outbound SGD 1863,
  no cross-border transactions or alerts. The answer explicitly says no-rule
  does not imply low risk and acknowledges policy retrieval was not requested.
- Missing-policy: AML score 85, eight transactions, inbound SGD 18000 and
  outbound SGD 18897, with empty policy context. Its suggested checks explicitly
  acknowledge `not_found`, no matched policy evidence, and the inability to
  infer compliance/risk from that absence. No invented policy citations were found.

## Residual Content Issue

One missing-policy suggestion says `确认AML评分85（演示阈值）的构成`.
This ambiguously labels score 85 as the demo threshold, whereas the threshold
is 80. The first observation correctly distinguishes score 85 and threshold 80,
but the suggestion should not be accepted as flawless content. Suggested checks
are outside the current explicit numeric assertion validation path. Another
generic suggestion repeats the no-rule disclaimer in a case with rule signals;
it is not an explicit assertion that this customer triggered no rules, but
is unnecessary boilerplate. Human analyst sign-off remains pending.

Thus both calls passed current structural/numeric checks and the targeted
no-rule/missing-policy communication criteria, not all semantic correctness
criteria. New C004 success does not retroactively establish the old failure cause.
Next work should first cover score/threshold distinction in suggestions with
free regression tests; no extra paid retry was performed.

## Usage and Price

Total: 3157 input + 1047 output = 4204 tokens. Input cache hits: 256;
cache misses: 2901. Official prices were fetched via local Firecrawl on
2026-10-04 and match the evaluator's price constants. Sunday off-peak estimate:
CNY 0.00709412 (roughly CNY 0.0071); peak estimate CNY 0.01418824.
Actual account debit was not inspected.

[Official pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py --live --max-calls 2 --case no_demo_rule --case missing_policy
```

This command is paid opt-in and creates a new batch; rerunning it incurs new
calls. Latest local results are in ignored `data/evaluations/live-results.json`.
