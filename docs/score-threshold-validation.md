# Score versus Threshold Validation

Free follow-up on 2026-10-04. No model calls or permission-system changes.

The AML demo threshold is defined as 80 and used by the deterministic rule.
Prompt version `review-explanation-v4` explicitly separates that threshold from
the customer's SQL score, including in suggested checks.

Local checks reject the historical wording `AML评分85（演示阈值）`, explicit
incorrect AML/demo-score threshold numbers, and explicit incorrect SQL numeric
assertions in suggested checks. Diagnostics retain the trusted field name,
expected/observed numbers and character offsets, not whole rejected prose.
The existing aggregate numeric error and partial-success audit semantics remain.

Correct wording such as `核实AML评分85的构成；AML演示阈值为80` is accepted.
Recognized hypothetical/question clauses containing words such as 是否, 假设,
如果 or 调整 are not treated as current SQL numeric assertions in suggestions.
This narrow heuristic is not semantic verification and can miss contradictions
embedded in questions or quoted examples. Explicit score-as-threshold labelling
is still checked separately; arbitrary paraphrases remain unverified.

Validation includes local fake generators, incorrect suggestion retention of SQL
facts, correct/incorrect thresholds and hypothetical suggestions. The historical
live answer is not edited or reclassified as a newly successful result. A paid
retest of the new prompt remains unperformed and requires separate authorization.
