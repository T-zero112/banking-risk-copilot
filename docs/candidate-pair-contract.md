# Candidate-pair Evidence Contract

Free correction after the two real schema failures. No provider calls were made.

Every observation requires a nonempty fact_refs OR candidate_pair_refs array.
fact_refs remains a required field; it may be empty only when pair evidence exists.
candidate_pair_refs defaults to an empty array for old fact-based answers.
References are strict integers identifying one-based positions in the report's
ordered candidate_pairs list. IDs are local to that report, not stable database IDs.
Each cited pair requires both its incoming and outgoing transaction IDs in
transaction_refs; all transaction IDs must also belong to the supplied payload.
Unknown pairs, zero/negative IDs, noninteger IDs and missing pair transactions
are rejected. Transaction references alone do not satisfy observation evidence.

The prompt now directs pair observations to pair references rather than the
unrelated transaction_count field. Policy commentary stays in policy_context;
policy absence, generic limitations and questions stay in suggested_checks.
Unsupported observations should be omitted, not repaired by inventing references.
No automatic response repair or retry was introduced.

This is membership/provenance validation, NOT full semantic entailment. An answer
can still cite a valid but unrelated fact, or misstate a pair's time/ratio in prose.
Those claims need focused human review; this change does not promise rejection of
all unsupported natural-language statements. Previous rejected bodies were not
retained, so their semantic content cannot be reconstructed.

Verification: 111 unit tests and 11 free evaluation scenarios passed. Six new
tests cover pair-only evidence, missing evidence, invalid pair IDs, missing
transactions, absent pairs, strict types, backward compatibility and prompt rules.
The latest prompt has not been tested with live model calls. Paid re-evaluation
of missing_policy and prompt_injection requires separate user authorization.
