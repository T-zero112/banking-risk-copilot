from copy import deepcopy
import unittest
from pydantic import ValidationError

from app.graph.review_explanation import ReviewExplanation, ExplanationValidationError, validate_explanation, explanation_messages
from test_review_explanation import explanation, payload


class PairReferenceTests(unittest.TestCase):
    def data(self):
        return dict(payload(), transactions=[dict(transaction_id="T001"), dict(transaction_id="T002")],
                    candidate_pairs=[dict(incoming_transaction_id="T001", outgoing_transaction_id="T002")])

    def answer(self):
        answer = explanation()
        answer["observations"][0].update(text="Pair requires human review.", fact_refs=[],
                                         candidate_pair_refs=[1], transaction_refs=["T001", "T002"])
        return answer

    def test_pair_only_evidence_valid_and_no_mutation(self):
        answer, data = self.answer(), self.data()
        before = deepcopy(data)
        validate_explanation(ReviewExplanation.model_validate(answer), data)
        self.assertEqual(data, before)

    def test_no_evidence_or_transaction_only_rejected(self):
        for transactions in ([], ["T001"]):
            answer = self.answer()
            answer["observations"][0].update(candidate_pair_refs=[], transaction_refs=transactions)
            with self.assertRaises(ValidationError):
                ReviewExplanation.model_validate(answer)

    def test_invalid_pair_and_missing_transactions(self):
        for refs, transactions, code in (([0], ["T001", "T002"], "unknown_candidate_pair_reference"),
                                         ([2], ["T001", "T002"], "unknown_candidate_pair_reference"),
                                         ([1], ["T001"], "candidate_pair_transactions_missing")):
            answer = self.answer()
            answer["observations"][0].update(candidate_pair_refs=refs, transaction_refs=transactions)
            with self.assertRaises(ExplanationValidationError) as caught:
                validate_explanation(ReviewExplanation.model_validate(answer), self.data())
            self.assertEqual(caught.exception.diagnostic["code"], code)

    def test_no_pairs_cannot_be_cited(self):
        data = self.data()
        data["candidate_pairs"] = []
        with self.assertRaises(ExplanationValidationError):
            validate_explanation(ReviewExplanation.model_validate(self.answer()), data)

    def test_strict_pair_ids(self):
        for value in (True, "1", 1.0):
            answer = self.answer()
            answer["observations"][0]["candidate_pair_refs"] = [value]
            with self.assertRaises(ValidationError):
                ReviewExplanation.model_validate(answer)

    def test_legacy_fact_observations_and_prompt(self):
        parsed = ReviewExplanation.model_validate(explanation())
        validate_explanation(parsed, payload())
        self.assertEqual(parsed.observations[0].candidate_pair_refs, [])
        instructions = explanation_messages(self.data())[0][1]
        self.assertIn('"candidate_pair_refs": [1]', instructions)
        self.assertIn("Transaction refs alone are insufficient", instructions)
        self.assertIn("Never use transaction_count as a substitute", instructions)


if __name__ == "__main__":
    unittest.main()
