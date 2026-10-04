import json
from types import SimpleNamespace
import unittest

from app.graph.customer_review import build_review_graph
from app.graph.generation_diagnostics import parsing_diagnostic
from test_review_explanation import explanation, loader, EmptyRetriever


class GenerationDiagnosticTests(unittest.TestCase):
    def run_output(self, content, parsed=None, error=None):
        raw = SimpleNamespace(content=content, id="local-test",
                              response_metadata={}, usage_metadata=dict(input_tokens=10, output_tokens=5, total_tokens=15))
        class Generator:
            def invoke(self, messages):
                return dict(raw=raw, parsed=parsed, parsing_error=error)
        return build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke(
            {"customer_id":"C003"})["report"]

    def test_malformed_json_safe_location_and_usage(self):
        report = self.run_output('{"private-secret":', error=ValueError("private-secret"))
        diagnostic = report["ai_generation"]["validation_diagnostic"]
        self.assertEqual(diagnostic["code"], "invalid_json")
        self.assertGreater(diagnostic["column"], 0)
        self.assertEqual(report["ai_generation"]["model_call"]["total_tokens"], 15)
        self.assertNotIn("private-secret", json.dumps(report, default=str))
        self.assertEqual(report["facts"]["aml_risk_score"], 85)
        self.assertNotIn("ai_explanation", report)

    def test_schema_missing_field(self):
        answer = explanation()
        del answer["human_review_required"]
        report = self.run_output(json.dumps(answer), error=ValueError("private-secret"))
        diagnostic = report["ai_generation"]["validation_diagnostic"]
        self.assertEqual(diagnostic["stage"], "schema")
        self.assertIn(dict(path="$.human_review_required", type="missing"), diagnostic["issues"])

    def test_unknown_keys_and_literal_values_are_redacted(self):
        answer = explanation()
        answer["private-secret"] = "private-secret"
        answer["observations"][0]["kind"] = "private-secret"
        diagnostic = parsing_diagnostic(SimpleNamespace(content=json.dumps(answer)))
        self.assertNotIn("private-secret", json.dumps(diagnostic))
        self.assertIn(dict(path="$.observations[0].kind", type="literal_error"), diagnostic["issues"])
        self.assertIn(dict(path="$.<unknown_field>", type="extra_forbidden"), diagnostic["issues"])

    def test_direct_schema_failure_also_has_diagnostic(self):
        answer = explanation()
        answer["suggested_checks"] = []
        report = self.run_output("", parsed=answer)
        self.assertEqual(report["ai_generation"]["validation_diagnostic"]["code"], "schema_invalid")

    def test_parser_disagreement_never_promotes_answer(self):
        report = self.run_output(json.dumps(explanation()), error=ValueError("private-secret"))
        self.assertEqual(report["ai_generation"]["status"], "failed")
        self.assertTrue(report["ai_generation"]["validation_diagnostic"]["local_schema_valid"])
        self.assertNotIn("ai_explanation", report)

    def test_empty_nonstring_and_wrong_root(self):
        self.assertEqual(parsing_diagnostic(SimpleNamespace(content=" "))["code"], "empty_model_content")
        self.assertEqual(parsing_diagnostic(SimpleNamespace(content=[]))["code"], "structured_parse_failed")
        self.assertEqual(parsing_diagnostic(SimpleNamespace(content="[]"))["code"], "schema_invalid")

    def test_schema_issue_list_bounded(self):
        diagnostic = parsing_diagnostic(SimpleNamespace(content=json.dumps({f"secret-{i}":i for i in range(30)})))
        self.assertEqual(len(diagnostic["issues"]), 8)
        self.assertTrue(diagnostic["issues_truncated"])
        self.assertNotIn("secret", json.dumps(diagnostic))


if __name__ == "__main__":
    unittest.main()
