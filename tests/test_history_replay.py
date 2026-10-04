from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.evaluation.history import collect_history, digest, replay_case, summarize


def entry():
    answer = dict(customer_id="C003", observations=[dict(kind="fact", text="KYC expired.",
                  fact_refs=["kyc_status"], transaction_refs=[])], policy_context=[],
                  suggested_checks=["Verify KYC."], human_review_required=True)
    report = dict(customer_id="C003", as_of="2026-10-01", window={},
                  facts=dict(kyc_status="expired", aml_risk_score=85), candidate_pairs=[],
                  transactions=[], review_signals=[], policy_evidence=[], disposition={},
                  limitations=[], ai_generation=dict(status="succeeded"), ai_explanation=answer)
    case = dict(id="missing_policy", customer_id="C003", scenario="missing_policy",
                request_id="00000000-0000-0000-0000-000000000001", report=report,
                usage=dict(usage_available=True, input_tokens=10, output_tokens=5, total_tokens=15))
    return dict(case=case, sources=["live-test.json"], fingerprint=digest(case))


class HistoryReplayTests(unittest.TestCase):
    def test_valid_answer_and_input_unchanged(self):
        saved = entry()
        before = deepcopy(saved)
        row = replay_case(saved)
        self.assertEqual(row["replay_status"], "accepted")
        self.assertEqual(saved, before)
        self.assertNotIn("KYC expired.", json.dumps(row))

    def test_threshold_rejected_and_corrected_control_accepted(self):
        saved = entry()
        answer = saved["case"]["report"]["ai_explanation"]
        answer["suggested_checks"] = ["AML评分85（演示阈值）。"]
        row = replay_case(saved)
        self.assertEqual(row["replay_status"], "rejected")
        self.assertEqual(row["diagnostic"]["expected"], "80")
        control = deepcopy(saved)
        control["case"]["report"]["ai_explanation"]["suggested_checks"] = ["AML评分85（演示阈值80）。"]
        self.assertEqual(replay_case(control)["replay_status"], "accepted")
        self.assertEqual(answer["suggested_checks"], ["AML评分85（演示阈值）。"])

    def test_only_deterministic_notice_is_removed(self):
        saved = entry()
        answer = saved["case"]["report"]["ai_explanation"]
        answer["policy_evidence_notice"] = "No evidence."
        self.assertEqual(replay_case(saved)["replay_status"], "accepted")
        answer["unexpected"] = "private-model-text"
        row = replay_case(saved)
        self.assertEqual(row["diagnostic"]["code"], "schema_invalid")
        self.assertNotIn("private-model-text", json.dumps(row))

    def test_missing_body_and_pre_call_block_are_not_passes(self):
        saved = entry()
        del saved["case"]["report"]["ai_explanation"]
        self.assertEqual(replay_case(saved)["replay_status"], "unavailable")
        saved["case"]["error_code"] = "audit_start_unconfirmed"
        saved["case"]["usage"] = {}
        row = replay_case(saved)
        self.assertEqual(row["replay_status"], "not_reached")
        self.assertEqual(row["historical_status"], "no_model_call")

    def test_non_object_body_is_schema_rejected(self):
        saved = entry()
        saved["case"]["report"]["ai_explanation"] = ["private-model-text"]
        self.assertEqual(replay_case(saved)["diagnostic"]["code"], "schema_invalid")

    def test_deduplication_conflict_and_free_exclusion(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            case = entry()["case"]
            paths = [root / name for name in ("live-a.json", "live-b.json", "live-c.json")]
            for path in paths[:2]:
                path.write_text(json.dumps(dict(phase="live", cases=[case])), encoding="utf-8")
            paths[2].write_text(json.dumps(dict(phase="free", cases=[case])), encoding="utf-8")
            before = [path.read_bytes() for path in paths]
            entries, sources, duplicates = collect_history(paths)
            self.assertEqual((len(entries), len(sources), duplicates), (1, 2, 1))
            self.assertEqual(before, [path.read_bytes() for path in paths])
            case["report"]["facts"]["aml_risk_score"] = 99
            paths[1].write_text(json.dumps(dict(phase="live", cases=[case])), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Conflicting snapshots"):
                collect_history(paths)

    def test_usage_and_new_call_counters(self):
        row = replay_case(entry())
        counts = summarize([row], 2)
        self.assertEqual(counts["historical_token_totals"]["total_tokens"], 15)
        self.assertEqual(counts["new_model_calls"], 0)
        self.assertEqual(counts["new_model_tokens"], 0)
        row["historical_usage"]["input_tokens"] = None
        self.assertIsNone(summarize([row], 0)["historical_token_totals"]["input_tokens"])
        row["historical_usage"]["usage_available"] = False
        self.assertEqual(summarize([row], 0)["unknown_usage_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
