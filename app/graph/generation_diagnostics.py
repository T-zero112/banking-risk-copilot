"""Privacy-safe classification; raw answers are inspected in memory only."""

import json
from pydantic import ValidationError

from app.graph.review_explanation import ReviewExplanation


FIELDS = {"customer_id", "observations", "kind", "text", "fact_refs", "transaction_refs",
          "policy_context", "policy_citations", "applicability", "suggested_checks",
          "human_review_required", "candidate_pair_refs"}
ERROR_TYPES = {"missing", "extra_forbidden", "string_type", "list_type", "literal_error",
               "int_type", "int_parsing", "bool_type", "bool_parsing", "too_short", "too_long",
               "model_type", "dict_type", "greater_than_equal", "less_than_equal"}


def schema_diagnostic(error):
    issues = error.errors(include_url=False, include_context=False, include_input=False)
    safe = []
    for issue in issues[:8]:
        path = "$"
        for part in issue["loc"]:
            if type(part) is int and part >= 0:
                path += f"[{part}]"
            else:
                path += "." + (part if isinstance(part, str) and part in FIELDS else "<unknown_field>")
        kind = issue["type"]
        safe.append(dict(path=path, type=kind if kind in ERROR_TYPES else "schema_constraint"))
    return dict(stage="schema", code="schema_invalid", issue_count=len(issues),
                issues=safe, issues_truncated=len(issues) > len(safe))


def parsing_diagnostic(raw=None, error=None):
    # Prefer typed errors; never expose exception messages or untrusted keys.
    if isinstance(error, ValidationError):
        return schema_diagnostic(error)
    content = getattr(raw, "content", None)
    if not isinstance(content, str):
        return dict(stage="parser", code="structured_parse_failed")
    if not content.strip():
        return dict(stage="json", code="empty_model_content")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as failure:
        return dict(stage="json", code="invalid_json", line=failure.lineno,
                    column=failure.colno, offset=failure.pos)
    except (ValueError, RecursionError):
        return dict(stage="json", code="json_decode_failed")
    try:
        ReviewExplanation.model_validate(value)
    except ValidationError as failure:
        return schema_diagnostic(failure)
    # A local strict parse succeeding does not override the provider parser failure.
    return dict(stage="parser", code="structured_parse_failed", local_schema_valid=True)
