import unittest

from app.graph.review_explanation import ReviewExplanation, ExplanationValidationError, validate_explanation
from test_review_explanation import explanation, payload


class PolicyPresenceTests(unittest.TestCase):
    def validate_text(self, text, evidence=False, observation=False):
        answer = explanation()
        if observation:
            answer["observations"][0]["text"] = text
        else:
            answer["suggested_checks"] = [text]
        data = payload()
        if not evidence:
            data["policy_evidence"] = []
        return validate_explanation(ReviewExplanation.model_validate(answer), data)

    def test_saved_counterexample_and_presence_assertions_rejected(self):
        for text in ("本次政策检索未获得匹配证据；检索条目涉及现金入账。",
                     "已检索到政策背景。", "Retrieved indicators involve cash."):
            with self.subTest(text=text), self.assertRaises(ExplanationValidationError) as caught:
                self.validate_text(text)
            self.assertEqual(caught.exception.diagnostic,
                             dict(code="policy_presence_contradiction", path="suggested_checks[0]"))

    def test_negations_hypotheticals_and_correct_notices_allowed(self):
        for text in ("本次政策检索未获得匹配证据，不能确认风险程度。",
                     "本流程未执行政策检索，不代表低风险。",
                     "没有检索条目。", "检索条目不存在。",
                     "如果检索条目涉及现金，应人工确认。", "No retrieved evidence."):
            with self.subTest(text=text):
                self.validate_text(text)

    def test_negation_does_not_mask_later_assertion(self):
        with self.assertRaises(ExplanationValidationError):
            self.validate_text("没有检索条目；已检索到政策背景。")

    def test_available_evidence_can_have_cash_caveat(self):
        self.validate_text("检索条目涉及现金入账，但现金条件尚未确认。", evidence=True)

    def test_observations_checked_too(self):
        with self.assertRaises(ExplanationValidationError) as caught:
            self.validate_text("已检索到政策背景。", observation=True)
        self.assertEqual(caught.exception.diagnostic["path"], "observations[0].text")


if __name__ == "__main__":
    unittest.main()
