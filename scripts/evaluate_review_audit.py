"""Persist and verify real success/failure audits without calling a paid API."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audit.customer_review import AuditedReviewError, run_customer_review
from app.audit.review import ReviewAuditStore
from app.graph.customer_review import build_review_graph


def main():
    store = ReviewAuditStore()
    report = run_customer_review("C003")
    row = store.read(report["request_id"])
    assert row["review_status"] == "succeeded" and row["finished_at"]
    assert row["final_answer"]["facts"]["aml_risk_score"] == 85
    assert row["final_answer"]["candidate_pairs"][0]["elapsed_minutes"] == 60
    assert row["retrieved_policy_refs"][0]["content_sha256"]
    assert row["review_metadata"]["code_sha256"]["app/sql/queries/review_customer.sql"]
    print(f"PASS success persisted: {report['request_id']}")
    try:
        run_customer_review("C999")
    except AuditedReviewError as error:
        row = store.read(error.request_id)
        assert row["review_status"] == "failed" and row["error_message"]
        assert row["final_answer"] is None
        print(f"PASS missing-customer failure persisted: {error.request_id}")
    else:
        raise AssertionError("Expected missing customer failure")

    class InvalidGenerator:
        def invoke(self, messages):
            raise ValueError("Synthetic invalid response; no live API request")

    partial = run_customer_review("C003", "deepseek", graph_factory=lambda **kwargs:
                                  build_review_graph(**kwargs, generator=InvalidGenerator()))
    row = store.read(partial["request_id"])
    assert row["review_status"] == "partial_success"
    assert row["sql_execution_status"] == "succeeded"
    assert row["final_answer"]["ai_generation"]["status"] == "failed"
    assert row["review_metadata"]["prompt_sha256"]
    assert row["review_metadata"]["execution_adapter"] == "injected"
    print(f"PASS simulated model failure persisted: {partial['request_id']}")
    print("All three audits retained for inspection; no paid model requests made")


if __name__ == "__main__":
    main()
