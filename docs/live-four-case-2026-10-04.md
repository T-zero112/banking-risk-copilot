# Four-case Live Assessment

Report date: 2026-10-04. Authorized scope: four scenarios, one call each,
no automatic retries. The free suite passed all 11 scenarios before execution.

| Scenario | Input tokens | Output tokens | Total | Generation | Audit |
| --- | ---: | ---: | ---: | --- | --- |
| risk_candidate | 2998 | 720 | 3718 | invalid_model_output | partial_success, confirmed |
| no_demo_rule | 1431 | 489 | 1920 | accepted | succeeded, confirmed |
| missing_policy | 1848 | 686 | 2534 | invalid_model_output | partial_success, confirmed |
| prompt_injection | 3056 | 777 | 3833 | invalid_model_output | partial_success, confirmed |
| Total | 9333 | 2672 | 12005 | | |

The accepted no-rule case passed the existing automated probes; this does not
establish general factual accuracy. Three outputs failed before a usable
explanation was accepted. Their validation diagnostics are null, and rejected
answer bodies were not retained. The stored error category is insufficient to
identify the precise parsing/schema failure. Do not attribute these failures to
score confusion or claim successful injection resistance from rejected outputs.
SQL reports remain available and all four audit persistence results are confirmed.
Human semantic assessment remains pending.

Source: ignored `data/evaluations/live-results.json` and its immutable live snapshot.
Request IDs, in table order:

- deec0f7e-59b0-4241-9951-9f96a11b91ba
- 09262bff-ba5b-43cf-a7cd-208f6a695e0b
- 870133d7-d8ed-4c29-b9d9-d17403319283
- e3211bdb-2f77-4093-8ea9-5040ea02d0cb

The script includes cost estimates using an older pricing snapshot; prices were
not reverified in this run, and account debits were not queried. Token counters
above are provider-reported actual usage, not estimated usage or currency charges.

Next: improve privacy-safe parse/schema diagnostics with free simulated tests
before authorizing any additional paid calls. No further paid calls are scheduled.
