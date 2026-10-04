from datetime import timedelta
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.graph.customer_review import build_review_graph, find_candidates
from app.sql.review import AS_OF, load_customer_evidence


def transaction(identifier, direction, hours, amount="100", account="A001"):
    return dict(transaction_id=identifier, direction=direction,
                transaction_time=AS_OF - timedelta(days=1) + timedelta(hours=hours),
                amount=Decimal(amount), account_id=account, is_cross_border=None)


class ReviewTests(unittest.TestCase):
    def test_pair_boundaries(self):
        incoming = transaction("in", "inbound", 0)
        for hours, amount, expected in ((24, "90", 1), (24, "110", 1), (24.01, "100", 0),
                                        (0, "100", 0), (-1, "100", 0), (1, "89.99", 0), (1, "110.01", 0)):
            self.assertEqual(len(find_candidates([incoming, transaction("out", "outbound", hours, amount)])), expected)
        self.assertEqual(find_candidates([incoming, transaction("out", "outbound", 1, account="A002")]), [])

    def test_bad_id_does_not_connect(self):
        with patch("app.sql.review.connect") as connection:
            with self.assertRaises(ValueError):
                load_customer_evidence("C003'; DROP TABLE customers;--")
            connection.assert_not_called()

    def test_row_cap_refuses_partial_analysis(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {"customer_id": "C003"}
        connection.execute.return_value.fetchall.return_value = [object()] * 201
        with patch("app.sql.review.connect", return_value=connection):
            with self.assertRaisesRegex(ValueError, "partial analysis"):
                load_customer_evidence("C003")
        connection.execute.assert_any_call("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        params = connection.execute.call_args.args[1]
        self.assertEqual(params["customer_id"], "C003")

    def test_missing_customer_stops_transaction_query(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = None
        with patch("app.sql.review.connect", return_value=connection):
            with self.assertRaisesRegex(ValueError, "not found"):
                load_customer_evidence("C999")
        connection.execute.return_value.fetchall.assert_not_called()

    def test_empty_snapshot_not_low_risk_verdict(self):
        evidence = dict(as_of=AS_OF, transactions=[], customer=dict(customer_id="C001", kyc_status="complete",
                        aml_risk_score=None, unresolved_alert_count=0))
        class NoSearch:
            def invoke(self, query):
                raise AssertionError("No candidate should skip retrieval")
        report = build_review_graph(lambda _: evidence, NoSearch()).invoke({"customer_id": "C001"})["report"]
        self.assertEqual(report["disposition"], "no_demo_rule_triggered")
        self.assertEqual(report["policy_evidence"], [])
        self.assertEqual(report["policy_evidence_status"], "not_requested")

    def test_cash_indicator_not_direct_transfer_evidence(self):
        evidence = dict(as_of=AS_OF, transactions=[transaction("in", "inbound", 0), transaction("out", "outbound", 1)],
                        customer=dict(customer_id="C003", kyc_status="expired", aml_risk_score=85, unresolved_alert_count=1))
        class FakeSearch:
            def invoke(self, query):
                return [Document(page_content="Matching of payments out with credits paid in by cash on the same or previous day.",
                                 metadata={"source_id": "spf-bank-red-flags", "locator": "PDF page 3"})]
        report = build_review_graph(lambda _: evidence, FakeSearch()).invoke({"customer_id": "C003"})["report"]
        signal = report["review_signals"][-1]
        self.assertEqual(signal["policy_citations"], [1])
        self.assertEqual(signal["policy_support"], "context_only_cash_condition_not_established")
        self.assertEqual(report["policy_evidence_status"], "available")
        self.assertEqual(report["facts"]["unknown_cross_border_count"], 2)

    def test_missing_policy_stays_explicit(self):
        evidence = dict(as_of=AS_OF, transactions=[transaction("in", "inbound", 0), transaction("out", "outbound", 1)],
                        customer=dict(customer_id="C001", kyc_status="complete", aml_risk_score=None, unresolved_alert_count=0))
        class EmptySearch:
            def invoke(self, query):
                return []
        report = build_review_graph(lambda _: evidence, EmptySearch()).invoke({"customer_id": "C001"})["report"]
        self.assertEqual(report["review_signals"][-1]["policy_support"], "not_found")
        self.assertEqual(report["policy_evidence_status"], "not_found")
        self.assertIn("未获得", report["policy_evidence_notice"])
