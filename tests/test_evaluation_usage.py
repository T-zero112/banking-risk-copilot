import unittest

from langchain_core.messages import AIMessage

from app.rag.providers import call_metadata
from app.graph.customer_review import build_review_graph
from app.sql.review import AS_OF


class UsageTests(unittest.TestCase):
    def test_provider_usage_is_retained_without_content(self):
        message = AIMessage(content="sensitive-output", response_metadata={"token_usage": {
            "prompt_tokens":1000, "completion_tokens":200, "total_tokens":1200,
            "prompt_cache_hit_tokens":400, "prompt_cache_miss_tokens":600}, "model_name":"deepseek-flash"})
        metadata = call_metadata(message)
        self.assertTrue(metadata["usage_available"])
        self.assertEqual(metadata["cache_hit_tokens"], 400)
        self.assertNotIn("sensitive", str(metadata))

    def test_missing_counts_not_silently_zero(self):
        metadata = call_metadata(AIMessage(content=""))
        self.assertFalse(metadata["usage_available"])
        self.assertIsNone(metadata["input_tokens"])

    def test_parse_failure_still_records_billed_usage(self):
        class Generator:
            def invoke(self, messages):
                return {"raw":AIMessage(content="bad JSON", usage_metadata={"input_tokens":10,"output_tokens":5,"total_tokens":15}),
                        "parsed":None, "parsing_error":ValueError("sensitive raw body")}
        evidence = dict(as_of=AS_OF,transactions=[],customer={"customer_id":"C003","kyc_status":"expired","aml_risk_score":85,"unresolved_alert_count":1})
        result = build_review_graph(loader=lambda _:evidence, mode="deepseek", generator=Generator()).invoke({"customer_id":"C003"})["report"]
        self.assertEqual(result["ai_generation"]["model_call"]["total_tokens"],15)
        self.assertEqual(result["ai_generation"]["status"],"failed")
        self.assertNotIn("sensitive raw body",str(result))
