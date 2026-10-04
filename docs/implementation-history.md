# Implementation History

Archived from the README during portfolio closeout. Entries describe successive
historical revisions, not a single latest-version acceptance run. Some statements
are superseded by later entries; the historical replay document is regenerated
and now has updated totals. See [final evaluation](final-evaluation.md) for the
current consolidated evidence and limitations.

The following entries describe successive historical revisions, not one unified
latest-version acceptance run. Use the final evaluation above for current scope.

SQL fixture analytics, document ingestion, lexical/multilingual retrieval, and
a SQL + policy review workflow run locally, with optional DeepSeek explanations.
DeepSeek policy answers and one C003 review were live-smoke-tested; general answer
accuracy is not established. Customer reviews now persist traceable audit records.
The local review workbench, FastAPI API and separate query/audit DB roles are available.
Text-to-SQL remains a project goal. Local login and customer-scoped API access
are now available; see [user access](user-access.md). Only two
SPF policy snapshots are currently ingested; MAS/FATF sources remain unavailable.

The 2026-10-02 evaluation passed eight free contract scenarios. All four new live
review explanations were rejected by evidence-reference validation; SQL reports
were retained as partial successes. This is not an AI quality pass. See
[evaluation results and costs](evaluation-report.md).
On 2026-10-03, safe diagnostic paths, prompt reference allowlists and explicit
numeric-label validation passed ten free scenarios and 66 unit tests. No new
paid calls were made; live acceptance after these changes is not yet established.
Subsequently, one authorized C003 live retest succeeded with 3541 tokens and
confirmed audit persistence. Other scenarios remain unverified after the fix;
see [single live retest](live-retest-2026-10-03.md).
The remaining three scenarios were subsequently called once each: no-rule output
was rejected by numeric validation; missing-policy and injection outputs were
accepted, but missing-policy prose did not explicitly acknowledge absent evidence.
See [follow-up assessment](live-followup-2026-10-03.md); this is not a complete
quality pass or a general injection-resistance claim.
On 2026-10-04, the updated no-rule and missing-policy cases both passed local
validation and persisted audits, with explicit policy notices. A generated
suggestion still confused score 85 with threshold 80, so this is not a complete
semantic quality pass. See [two-case retest](two-case-retest-2026-10-04.md).
The subsequent free score/threshold fix passed 71 unit tests and 11 evaluation
scenarios, without new model calls. Suggested-check numeric assertions are now
checked with documented heuristic limitations; see
[score/threshold validation](score-threshold-validation.md).

Offline historical replay deduplicates 11 attempts: five retained answers can be
revalidated, with four accepted and one rejected for score/threshold confusion.
Five rejected bodies were not retained; one attempt stopped before generation.
No new model calls are made. See [historical replay summary](historical-replay.md).
This does not validate the latest prompt or establish model accuracy.
The subsequent authorized four-case live batch used 12005 tokens: only the
no-rule case was accepted; three returned invalid_model_output with insufficient
diagnostics. SQL reports and all audit records were retained. See
[four-case live assessment](live-four-case-2026-10-04.md).
Privacy-safe JSON/schema diagnostics were subsequently added without paid calls;
105 unit tests and 11 free scenarios passed. See
[generation diagnostics](generation-diagnostics.md). Earlier rejected bodies
cannot be retrospectively diagnosed because they were not retained.
A subsequent authorized C003-only call passed with 3754 tokens and confirmed
audit persistence. Score 85 and threshold 80 were explicitly distinguished;
real failure diagnostics remain unexercised by this successful call. See
[C003 diagnostic retest](c003-diagnostic-retest.md).
The remaining two authorized calls used 6514 tokens and both failed schema
validation: observations[3] and observations[4] had too-short fact_refs. Safe
diagnostics and partial-success audit persistence worked; injection resistance
and missing-policy prose remain unverified. See
[remaining two-case diagnostic retest](remaining-two-diagnostic-retest.md).
A free contract correction adds candidate-pair references with mandatory paired
transaction provenance, while keeping observations evidence-required. 111 unit
tests and 11 free scenarios passed; no live acceptance is established for this
prompt yet. See [candidate-pair contract](candidate-pair-contract.md).
The two authorized pair-contract retests both passed automated validation and
audit persistence, using 6756 tokens. Missing-policy prose still contains a
contradictory retrieved-indicator caveat; semantic quality is not fully passed.
The injection answer ignored this single saved attack, not a general security
benchmark. See [pair-contract live retest](pair-contract-live-retest.md).
The contradictory missing-policy caveat is now rejected by a free narrow
presence-assertion check; 116 unit tests and 11 free scenarios passed. Offline
replay rejects the saved offending suggestion and still accepts the injection
answer. New-prompt live quality remains untested. See
[policy-presence validation](policy-presence-validation.md).
One authorized missing-policy wording retest passed with 2718 tokens and confirmed
audit persistence; the targeted contradictory wording was absent on focused
review. This is one call, not a stability benchmark. See
[missing-policy wording live retest](policy-presence-live-retest.md).

