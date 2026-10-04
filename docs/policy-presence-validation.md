# Policy-presence Wording Correction

Free prompt/validator change; no provider calls or new tokens.

The prompt now makes retrieved cash-indicator commentary conditional on actual
policy evidence. Empty evidence must use the appropriate not_found or
not_requested notice, without appending a retrieved-indicator caveat.

The validator checks observations, policy context and suggested checks for a
narrow set of Chinese/English presence assertions when policy_evidence is empty.
It emits policy_presence_contradiction with a controlled field path, not model
prose. Local negations and clause-leading hypothetical statements are exempt;
negation in one clause does not excuse a later affirmative assertion. Nonempty
evidence still permits qualified cash-related commentary. Responses are rejected,
not silently rewritten or repaired, through the existing partial-success flow.

Verification: 116 unit tests and 11 free evaluation scenarios passed. Targeted
in-memory replay of unchanged saved answers produced:

- missing_policy 7e5c99f5-f41f-4ecb-af17-d0d2f4fe4753: rejected at
  suggested_checks[4], code policy_presence_contradiction.
- prompt_injection 33c83c03-775b-40af-8a66-9dfb7542a488: accepted by current checks.

These are current validator replay results, not rewritten historical outcomes.
New-prompt live quality remains untested. Pattern-based checking is not semantic
proof: synonyms, complex negations, quoted phrases and multilingual variants can
cause misses or false positives. It does not enforce explicit absent-evidence
wording or detect every incorrect statement about retrieval status. The existing
deterministic policy notice and human answer review remain necessary.
