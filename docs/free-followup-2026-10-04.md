# Free Follow-up: 2026-10-04

No DeepSeek calls were made. Historical live outcomes are unchanged.

Numeric mismatch diagnostics now include `fact_field`, `expected`, `observed`,
and character offsets `claim_start`/`claim_end`, alongside the existing code and
schema path. They do not include whole rejected prose, reference values or keys.
These numeric values still belong to customer evidence and require the same
access controls as the report; diagnostics are not public-safe merely because
prose is omitted.

A local false-positive example was reproduced: `跨境交易数量 2` could be
matched as an assertion about total `transaction_count`. The validator now skips
recognized qualified subset counts, while still rejecting wrong explicit total
counts. Subset counts are not verified by this rule. This does NOT establish
the cause of the historical C004 failure; its rejected text was not retained.
Arbitrary prose, thresholds and hypothetical claims remain limitations of the
narrow numeric-label approach.

Reports now expose `policy_evidence_status` as `available`, `not_found` or
`not_requested`, plus a deterministic Chinese notice. No pairing candidate means
this workflow did not request policy retrieval; absence of a matching result
after retrieval is a different state. The generated explanation receives the
same deterministic notice after validation, separately from model prose. The
prompt requests an acknowledgement, but the notice does not depend on compliance.
The workbench policy section renders the escaped notice; historical reports
without a status get an explicitly unknown-state fallback, not a retroactive claim.
Prompt provenance is `review-explanation-v3`.

Validation: 68 unit tests and ten free evaluation scenarios passed. The latter
write real local audit records with injected fake generators where needed.
No live model acceptance claim is added by these changes.
