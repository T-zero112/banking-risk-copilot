import unittest
from unittest.mock import MagicMock, patch

from app.audit.customer_review import AuditedReviewError, run_customer_review
from app.audit.review import ReviewAuditStore
from app.sql.review import AS_OF


class FakeGraph:
    def __init__(self, partial=False, fail=False):
        self.partial = partial
        self.fail = fail

    def stream(self, input, stream_mode):
        self.input = input
        self.stream_mode = stream_mode
        if self.fail:
            raise ValueError("sensitive error body must not be logged")
        yield {"load_sql": {"evidence": dict(customer={"customer_id": input["customer_id"]},
                                            transactions=[], as_of=AS_OF)}}
        yield {"assess": {"candidates": []}}
        yield {"retrieve_policy": {"policies": []}}
        report = dict(customer_id=input["customer_id"], facts={}, transactions=[], candidate_pairs=[],
                      as_of=AS_OF, window="SGD", review_signals=[], policy_evidence=[],
                      disposition="no_demo_rule_triggered", limitations=[])
        yield {"compose": {"report": report}}
        if self.partial:
            report["ai_generation"] = dict(status="failed", error_code="model_api_failed")
            yield {"generate_explanation": {"explanation": None}}
            yield {"validate_explanation": {"report": report}}


class AuditTests(unittest.TestCase):
    def test_success_stores_correlated_result(self):
        store = MagicMock()
        report = run_customer_review("C003", store=store, graph_factory=lambda **_: FakeGraph())
        request = report["request_id"]
        self.assertEqual(store.start.call_args.args[0], request)
        args = store.finish.call_args.args
        self.assertEqual(args[:3], (request, "succeeded", "succeeded"))
        self.assertGreaterEqual(args[3], 0)
        self.assertEqual(args[5]["request_id"], request)
        self.assertEqual(report["audit"]["persistence"], "confirmed")

    def test_start_failure_prevents_graph_execution(self):
        store = MagicMock()
        store.start.side_effect = RuntimeError("password must not leak")
        factory = MagicMock()
        with self.assertRaises(AuditedReviewError) as caught:
            run_customer_review("C003", store=store, graph_factory=factory)
        self.assertEqual(caught.exception.code, "audit_start_unconfirmed")
        self.assertNotIn("password", str(caught.exception))
        factory.assert_not_called()
        store.finish.assert_not_called()

    def test_completion_failure_is_not_confirmed(self):
        store = MagicMock()
        store.finish.side_effect = RuntimeError("unknown commit state")
        with self.assertRaises(AuditedReviewError) as caught:
            run_customer_review("C003", store=store, graph_factory=lambda **_: FakeGraph())
        self.assertEqual(caught.exception.code, "audit_completion_unconfirmed")

    def test_workflow_failure_records_safe_error(self):
        store = MagicMock()
        with self.assertRaises(AuditedReviewError):
            run_customer_review("C999", store=store, graph_factory=lambda **_: FakeGraph(fail=True))
        args = store.finish.call_args.args
        self.assertEqual(args[1:3], ("failed", "failed"))
        self.assertEqual(args[4]["last_stage"], "load_sql")
        self.assertEqual(args[6], "invalid_request_or_configuration")
        self.assertNotIn("sensitive", str(args))

    def test_configuration_failure_is_logged_without_sql(self):
        store = MagicMock()
        factory = MagicMock(side_effect=ValueError("missing API credentials"))
        with self.assertRaises(AuditedReviewError):
            run_customer_review("C003", "deepseek", store=store, graph_factory=factory)
        args = store.finish.call_args.args
        self.assertEqual(args[1:3], ("failed", "not_requested"))
        self.assertEqual(args[4]["last_stage"], "configure")
        self.assertNotIn("credentials", str(args))

    def test_partial_success_keeps_snapshot_and_prompt_hash(self):
        store = MagicMock()
        report = run_customer_review("C003", "deepseek", store=store,
                                     graph_factory=lambda **_: FakeGraph(partial=True))
        args = store.finish.call_args.args
        self.assertEqual(args[1:3], ("partial_success", "succeeded"))
        self.assertEqual(report["audit"]["status"], "partial_success")
        self.assertIn("prompt_sha256", args[4])
        self.assertIn("sql_evidence_snapshot", args[4])
        self.assertEqual(args[6], "model_api_failed")

    def test_query_failure_after_sql_retains_evidence(self):
        class RetrievalFailure(FakeGraph):
            def stream(self, input, stream_mode):
                yield {"load_sql": {"evidence": {"customer": {"customer_id": "C003"}, "transactions": [], "as_of": AS_OF}}}
                yield {"assess": {"candidates": []}}
                raise RuntimeError("private retrieval error")
        store = MagicMock()
        with self.assertRaises(AuditedReviewError):
            run_customer_review("C003", store=store, graph_factory=lambda **_: RetrievalFailure())
        args = store.finish.call_args.args
        self.assertEqual(args[2], "succeeded")
        self.assertEqual(args[4]["last_stage"], "retrieve_policy")
        self.assertIn("sql_evidence_snapshot", args[4])

    def test_finish_requires_exactly_one_started_record(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.rowcount = 0
        with patch("app.audit.review.connect", return_value=connection):
            with self.assertRaises(RuntimeError):
                ReviewAuditStore().finish("request", "succeeded", "succeeded", 10, {}, None, None)
