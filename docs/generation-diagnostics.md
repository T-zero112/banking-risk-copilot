# Generation Failure Diagnostics

Customer review generation keeps the compatible `invalid_model_output` error
code while populating `ai_generation.validation_diagnostic` for parsing/schema
failures. API failures also expose a fixed provider-stage diagnostic.

Diagnostic fields are allowlisted:

- `stage`: json, schema, parser or provider.
- `code`: invalid_json, json_decode_failed, empty_model_content, schema_invalid,
  structured_parse_failed or model_api_failed.
- JSON failures: numeric line, column and offset; no nearby text.
- Schema failures: total issue count, up to eight controlled paths/types, and
  a truncation flag. Unknown field names are replaced with `<unknown_field>`.
- Parser disagreement: `local_schema_valid=true` when strict local JSON/schema
  inspection succeeds but the structured parser did not accept the answer.

No exception messages, rejected values, schema error input/context, raw model
content or provider headers are saved in these diagnostics. Raw content is
inspected in memory only. Missing raw content leaves a generic parser-stage
classification; do not infer a JSON failure without evidence. Local inspection
does not repair malformed JSON or promote rejected responses to success.

Provider usage remains available when the structured-output wrapper returned raw
metadata, even if parsing failed. Direct exceptions without that metadata cannot
establish actual token usage. Existing evidence/numeric validation diagnostics
remain unchanged. SQL evidence remains available on generation failure; the
existing audit flow persists the report and treats it as partial success.

Verification: 105 unit tests passed; 11 free evaluation scenarios passed, with
zero paid calls. New tests cover malformed/empty/non-string content, wrong JSON
root, missing/extra fields, nested enum failures, redaction, bounded issues,
parser disagreement, usage retention and SQL preservation.

The three failures in the preceding live batch had no retained rejected body
and null diagnostics. They cannot be retrospectively diagnosed by this change.
No new live calls were made, so future provider behavior remains unverified.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts/evaluate_review_suite.py
```
