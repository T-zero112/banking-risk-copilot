# Final Portfolio Evaluation

Scope: current local portfolio MVP, not production certification. This document
consolidates existing evidence; closeout introduces no paid model calls.

## Current Free Verification

- 116 unit tests passed, including schema/parser diagnostic privacy, pair evidence
  contracts and policy-presence contradiction regressions.
- 11 free review evaluation scenarios passed; these use deterministic fixtures
  and fake generators. They do not establish live model accuracy.
- Historical replay: 21 unique attempts, 20 known-usage calls and one pre-model
  audit-start block. Historical outcomes: 10 accepted, 10 rejected, one no call.
- Retained bodies: 10; current replay accepts eight and rejects two. The ten
  missing rejected bodies cannot be replayed. The two current rejections catch
  score/threshold confusion and a contradictory policy-presence suggestion.
- Deduplicated historical counters: 44693 input + 13173 output = 57866 tokens.
  These are previous usage, not new closeout spending or verified currency charges.

Raw model outputs and audit snapshots are ignored by Git. The public reproduction
can run free fixtures but cannot exactly replay private historical calls without
separately supplied artifacts. Source hashes and diagnostics are recorded in the
ignored replay summary; see [historical replay](historical-replay.md).

## Most Recent Preserved Live Results

| Scenario | Latest total tokens | Result / scope |
| --- | ---: | --- |
| C003 risk candidate | 3754 | Accepted before pair-contract update; audit confirmed |
| C004 no demo rule | 1920 | Accepted before pair-contract update; not low-risk certification |
| Missing policy | 2718 | Accepted after presence fix; focused review found targeted contradiction absent |
| Injection | 4042 | Accepted after pair-contract fix, before presence fix; one attack ignored |

All four latest retained answers pass current local replay. These are selected
single calls from different revisions, NOT a unified latest-prompt four-case test
or a reliable accuracy percentage. Earlier failures must remain visible.

Live evidence: [four-case batch](live-four-case-2026-10-04.md),
[C003 retest](c003-diagnostic-retest.md),
[schema failures](remaining-two-diagnostic-retest.md),
[pair-contract retest](pair-contract-live-retest.md),
[final missing-policy retest](policy-presence-live-retest.md).

## Delivery Decision

Ready for a bounded local portfolio demonstration with disclosed limitations.
Not evidence of readiness for bank production use or autonomous compliance
decisions. Independent analyst approval and publication remain pending.

Known gaps: semantic entailment is partial; generic caveats can be irrelevant to
the case; policy-pattern validation may miss synonyms or misread negations;
rejected prose is not retained; only one injection attack is demonstrated;
MAS/FATF coverage and Text-to-SQL are absent. Current deployment verification is
Windows-local, and earlier fresh-environment checks predate the latest validators.
See [deployment verification](deployment-verification.md) for its historical scope.

Do not add paid calls solely to turn every row green. Any additional live batch
requires explicit authorization and should answer a defined remaining question.
