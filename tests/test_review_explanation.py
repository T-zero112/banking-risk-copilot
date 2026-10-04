from copy import deepcopy
from decimal import Decimal
import unittest
import httpx
from openai import APIConnectionError

from app.graph.customer_review import build_review_graph
from app.graph.review_explanation import ExplanationValidationError, ReviewExplanation, explanation_messages, review_payload, validate_explanation
from app.sql.review import AS_OF


def explanation():
    return dict(customer_id="C003", observations=[dict(kind="fact", text="KYC 信息已过期，需要核实。",
                fact_refs=["kyc_status"], transaction_refs=[])], policy_context=[],
                suggested_checks=["核实客户 KYC 状态和更新计划。"], human_review_required=True)


def payload():
    return dict(customer_id="C003", facts={"kyc_status": "expired"},
                transactions=[{"transaction_id": "T001"}], policy_evidence=[{"citation_id": 1}])


class EmptyRetriever:
    def invoke(self, query):
        return []


def loader(customer_id):
    return dict(as_of=AS_OF, transactions=[], customer=dict(customer_id=customer_id,
                kyc_status="expired", aml_risk_score=85, unresolved_alert_count=1))


class ExplanationTests(unittest.TestCase):
    def test_suggestions_distinguish_score_from_threshold(self):
        examples = [
            ("确认AML评分85（演示阈值）的构成。", False),
            ("AML演示阈值为85。", False),
            ("核实AML评分85的构成；AML演示阈值为80。", True),
            ("AML评分85（演示阈值80）。", True),
            ("是否将AML演示阈值调整为85？", True),
            ("假设AML评分99，是否需要进一步核查？", True),
            ("核实AML评分99的构成。", False),
            ("交易数量为9笔，请核查。", False),
        ]
        for text, valid in examples:
            with self.subTest(text=text):
                output = explanation()
                output["suggested_checks"] = [text]
                data = dict(payload(), facts=dict(kyc_status="expired", aml_risk_score=85, transaction_count=8))
                parsed = ReviewExplanation.model_validate(output)
                if valid:
                    validate_explanation(parsed, data)
                else:
                    with self.assertRaises(ExplanationValidationError) as caught:
                        validate_explanation(parsed, data)
                    self.assertEqual(caught.exception.diagnostic["path"], "suggested_checks[0]")

    def test_threshold_confusion_in_observation_rejected(self):
        output = explanation()
        output["observations"][0]["text"] = "AML评分85（演示阈值）。"
        data = dict(payload(), facts=dict(kyc_status="expired", aml_risk_score=85))
        with self.assertRaises(ExplanationValidationError) as caught:
            validate_explanation(ReviewExplanation.model_validate(output), data)
        self.assertEqual(caught.exception.diagnostic["fact_field"], "demo_aml_threshold")
        self.assertEqual(caught.exception.diagnostic["expected"], "80")

    def test_invalid_suggestion_retains_sql_report(self):
        class Generator:
            def invoke(self, messages):
                output = explanation()
                output["suggested_checks"] = ["确认AML评分85（演示阈值）的构成。"]
                return output
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id":"C003"})["report"]
        self.assertEqual(report["ai_generation"]["error_code"], "inconsistent_numeric_facts")
        self.assertEqual(report["ai_generation"]["validation_diagnostic"]["path"], "suggested_checks[0]")
        self.assertEqual(report["facts"]["aml_risk_score"], 85)
        self.assertNotIn("ai_explanation", report)

    def test_safe_diagnostic_codes_and_paths(self):
        cases = [
            ("customer_id", "secret-model-value", "customer_id_mismatch", "customer_id"),
            ("fact_refs", ["secret-model-value"], "unknown_fact_reference", "observations[0].fact_refs[0]"),
            ("transaction_refs", ["secret-model-value"], "unknown_transaction_reference", "observations[0].transaction_refs[0]"),
        ]
        for field, value, code, path in cases:
            with self.subTest(field=field):
                output = explanation()
                target = output if field == "customer_id" else output["observations"][0]
                target[field] = value
                with self.assertRaises(ExplanationValidationError) as caught:
                    validate_explanation(ReviewExplanation.model_validate(output), payload())
                self.assertEqual(caught.exception.diagnostic, dict(code=code, path=path))
                self.assertNotIn("secret", str(caught.exception))
        output = explanation()
        output["policy_context"] = [dict(text="背景。", policy_citations=[999], applicability="context_only_cash_condition_not_established")]
        with self.assertRaises(ExplanationValidationError) as caught:
            validate_explanation(ReviewExplanation.model_validate(output), payload())
        self.assertEqual(caught.exception.diagnostic, dict(code="unknown_policy_citation", path="policy_context[0].policy_citations[0]"))

    def test_explicit_numeric_claims(self):
        facts = dict(kyc_status="expired", aml_risk_score=85, transaction_count=8,
                     inbound_sgd=Decimal("18000"), outbound_sgd=Decimal("18897"))
        examples = [
            ("AML评分为85。", True), ("AML评分为99。", False),
            ("交易数量为8笔。", True), ("交易数量为9笔。", False),
            ("入账总额：SGD 18,000.00。", True), ("入账总额为1.8万。", True),
            ("出账总额为18897。", True), ("出账总额为18898。", False),
            ("演示阈值为80；交易配对窗口为24小时。", True),
        ]
        for text, valid in examples:
            with self.subTest(text=text):
                output = explanation()
                output["observations"][0]["text"] = text
                data = dict(payload(), facts=facts)
                parsed = ReviewExplanation.model_validate(output)
                if valid:
                    validate_explanation(parsed, data)
                else:
                    with self.assertRaises(ExplanationValidationError) as caught:
                        validate_explanation(parsed, data)
                    self.assertEqual(caught.exception.diagnostic["code"], "numeric_fact_mismatch")
        data["facts"]["aml_risk_score"] = None
        output["observations"][0]["text"] = "AML评分为85。"
        with self.assertRaises(ExplanationValidationError):
            validate_explanation(ReviewExplanation.model_validate(output), data)

    def test_prompt_lists_exact_allowed_references(self):
        messages = explanation_messages(payload())
        self.assertIn('"fact_refs": ["kyc_status"]', messages[0][1])
        self.assertIn('"transaction_refs": ["T001"]', messages[0][1])
        self.assertIn('"policy_citations": [1]', messages[0][1])
        self.assertIn("never facts.key", messages[0][1])

    def test_numeric_failure_retains_sql_with_diagnostic(self):
        class Generator:
            def invoke(self, messages):
                output = explanation()
                output["observations"][0].update(text="AML评分为99。", fact_refs=["aml_risk_score"])
                return output
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id":"C003"})["report"]
        self.assertEqual(report["facts"]["aml_risk_score"], 85)
        self.assertEqual(report["ai_generation"]["error_code"], "inconsistent_numeric_facts")
        diagnostic = report["ai_generation"]["validation_diagnostic"]
        self.assertEqual(diagnostic["code"], "numeric_fact_mismatch")
        self.assertEqual(diagnostic["path"], "observations[0].text")
        self.assertEqual(diagnostic["fact_field"], "aml_risk_score")
        self.assertEqual(diagnostic["expected"], "85")
        self.assertEqual(diagnostic["observed"], "99")
        self.assertNotIn("text", diagnostic)
        self.assertNotIn("ai_explanation", report)

    def test_qualified_transaction_count_not_compared_to_total(self):
        from app.graph.review_explanation import validate_numeric_claims
        for qualifier in ("跨境", "非跨境", "现金", "入账", "出账", "候选"):
            validate_numeric_claims(qualifier + "交易数量 2。", {"transaction_count": 6}, "observations[0].text")
        validate_numeric_claims("窗口内交易数量 6。", {"transaction_count": 6}, "observations[0].text")
        with self.assertRaises(ExplanationValidationError):
            validate_numeric_claims("窗口内交易数量 2。", {"transaction_count": 6}, "observations[0].text")

    def test_policy_notice_attached_without_model_dependency(self):
        class Generator:
            def invoke(self, messages):
                return explanation()
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id":"C003"})["report"]
        self.assertEqual(report["policy_evidence_status"], "not_requested")
        self.assertEqual(report["ai_explanation"]["policy_evidence_notice"], report["policy_evidence_notice"])
        self.assertIn("未执行", report["policy_evidence_notice"])

    def test_valid_explanation(self):
        result = validate_explanation(ReviewExplanation.model_validate(explanation()), payload())
        self.assertEqual(result.customer_id, "C003")

    def test_wrong_customer(self):
        output = explanation()
        output["customer_id"] = "C002"
        with self.assertRaises(ValueError):
            validate_explanation(ReviewExplanation.model_validate(output), payload())

    def test_unknown_fact_and_transaction(self):
        for field, value in (("fact_refs", ["invented"]), ("transaction_refs", ["T999"])):
            output = explanation()
            output["observations"][0][field] = value
            with self.assertRaises(ValueError):
                validate_explanation(ReviewExplanation.model_validate(output), payload())

    def test_missing_or_unknown_policy(self):
        output = explanation()
        output["policy_context"] = [dict(text="背景参考。", policy_citations=[2],
                applicability="context_only_cash_condition_not_established")]
        with self.assertRaises(ValueError):
            validate_explanation(ReviewExplanation.model_validate(output), payload())
        output["policy_context"][0]["policy_citations"] = [1]
        data = payload()
        data["policy_evidence"] = []
        with self.assertRaises(ValueError):
            validate_explanation(ReviewExplanation.model_validate(output), data)

    def test_schema_rejects_direct_applicability_and_verdict(self):
        output = explanation()
        output["policy_context"] = [dict(text="直接适用。", policy_citations=[1], applicability="direct")]
        with self.assertRaises(ValueError):
            ReviewExplanation.model_validate(output)
        output = explanation()
        output["verdict"] = "guilty"
        with self.assertRaises(ValueError):
            ReviewExplanation.model_validate(output)

    def test_success_does_not_modify_facts_or_disposition(self):
        class Generator:
            def invoke(self, messages):
                self.messages = messages
                return explanation()
        baseline = build_review_graph(loader, EmptyRetriever()).invoke({"customer_id": "C003"})["report"]
        generator = Generator()
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=generator).invoke({"customer_id": "C003"})["report"]
        for key in ("facts", "candidate_pairs", "transactions", "disposition", "limitations"):
            self.assertEqual(report[key], baseline[key])
        self.assertEqual(report["ai_generation"]["status"], "succeeded")
        self.assertIn("JSON", generator.messages[0][1])

    def test_invalid_output_retains_baseline(self):
        class Generator:
            def invoke(self, messages):
                output = explanation()
                output["observations"][0]["transaction_refs"] = ["T999"]
                return output
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id": "C003"})["report"]
        self.assertEqual(report["ai_generation"]["error_code"], "invalid_evidence_references")
        self.assertNotIn("ai_explanation", report)
        self.assertEqual(report["facts"]["aml_risk_score"], 85)

    def test_parsing_failure_retains_baseline(self):
        class Generator:
            def invoke(self, messages):
                raise ValueError("Invalid JSON containing sensitive response")
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id": "C003"})["report"]
        self.assertEqual(report["ai_generation"]["error_code"], "invalid_model_output")
        self.assertNotIn("sensitive", str(report))

    def test_api_failure_retains_baseline(self):
        class Generator:
            def invoke(self, messages):
                raise APIConnectionError(request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))
        report = build_review_graph(loader, EmptyRetriever(), mode="deepseek", generator=Generator()).invoke({"customer_id": "C003"})["report"]
        self.assertEqual(report["ai_generation"]["status"], "failed")
        self.assertEqual(report["ai_generation"]["error_code"], "model_api_failed")
        self.assertNotIn("ai_explanation", report)
        self.assertEqual(report["facts"]["kyc_status"], "expired")

    def test_payload_excludes_unrelated_transactions(self):
        report = dict(customer_id="C003", as_of=AS_OF, window="SGD", facts={}, candidate_pairs=[],
                      transactions=[{"transaction_id": "T001", "amount": Decimal("100")}],
                      review_signals=[], policy_evidence=[], disposition="no_demo_rule_triggered", limitations=[])
        before = deepcopy(report)
        self.assertEqual(review_payload(report)["transactions"], [])
        self.assertEqual(report, before)
