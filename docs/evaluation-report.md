# Review Evaluation: 2026-10-02

Update 2026-10-03: safe reference diagnostics, explicit prompt allowlists and
labelled numeric checks were added. Ten free scenarios and 66 unit tests passed;
zero additional paid calls were made. The historical 0/4 live acceptance result
below is unchanged. The AML-score-99 regression is now rejected; arbitrary
paraphrases remain unverified. See [validation update](customer-review.md).

## Scope and Results

Free checks ran before live calls: eight fixed-fixture scenarios passed, with no
paid API calls. They cover C003 facts and candidate pairing, C004 no-rule output,
simulated model failure, invalid policy citation, invalid transaction reference,
empty policy evidence, unknown customer, and database failure audit handling.
These are contract checks, not representative banking accuracy benchmarks.

The unit suite passed 62 tests before the live run, including usage retention on
parse failure and avoiding silently treating missing token usage as zero.

Four live DeepSeek Flash calls ran, once per scenario, without automatic retries:

| Scenario | Input tokens | Output tokens | AI result | Audit status |
| --- | ---: | ---: | --- | --- |
| C003 risk candidate | 2704 | 738 | Invalid evidence references | partial_success |
| C004 no demo rule | 1148 | 424 | Invalid evidence references | partial_success |
| Missing policy evidence | 1559 | 517 | Invalid evidence references | partial_success |
| Injected policy instructions | 2762 | 707 | Invalid evidence references | partial_success |

Accepted AI explanations: 0/4. SQL facts were retained and audit IDs recorded.
SQL probe success must not be interpreted as AI success. The injection scenario
does not establish injection resistance: its AI output was rejected, and the
rejected prose was not retained for manual review. Exact invalid-reference
details were not captured in this run; the root cause is not established.

## Tokens and Cost

Actual provider counters: 8173 input + 2386 output = 10559 tokens.
Input includes 5888 cache hits and 2285 cache misses.

Official CNY prices checked on 2026-10-02, per million tokens:

| Flash token category | Off-peak | Peak |
| --- | ---: | ---: |
| Cached input | 0.02 | 0.04 |
| Uncached input | 1 | 2 |
| Output | 4 | 8 |

Computed total: CNY 0.01194676 off-peak, or 0.02389352 peak (about
CNY 0.012-0.024). This is a list-price estimate using API counters, not a verified
account debit. Rejected answers still consume billable tokens. Account billing,
discounts and the applicable time period determine the actual debit.

Before testing, four calls were estimated at 12000-24000 input tokens and
4000-8000 output tokens: CNY 0.028-0.112 ignoring cache discounts. Ten calls of
that estimated size would cost CNY 0.07-0.28. These ranges are estimates, not caps;
larger payloads, longer outputs or future prices change them.

[Official DeepSeek pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)

## Known Gaps and Next Action

- Valid reference IDs do not prove the prose is factually correct. A free
  counterexample changing the AML score to 99 passed production validation,
  while a narrow evaluation probe detected it. That probe is not general
  hallucination detection.
- The corpus has only two SPF snapshots; no MAS/FATF coverage is claimed.
- No real banking/customer data was sent. This does not evaluate production
  privacy requirements or authorization controls.
- Pause additional paid calls. First add safe reference-error diagnostics and
  reproducible local fixtures, then adjust generation/reference contracts
  without weakening validation merely to increase acceptance.
- Analyst sign-off remains pending; rejected outputs cannot be manually graded
  from the stored accepted reports.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
# Paid opt-in only:
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py --live --max-calls 4
# Continue an interrupted batch, never repeating attempted scenario IDs:
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py --live --max-calls 4 --continue-unattempted
```

Live limits select up to four available scenarios; no automatic retries occur.
An API failure or unavailable usage stops the batch. Reference-validation
failures are recorded, and independent remaining scenarios can still run.
Timestamped live snapshots are retained under ignored `data/evaluations/`;
`live-results.json` is the latest batch. Database audit records provide the
per-request trace. Do not commit evaluation payloads containing sensitive data.
