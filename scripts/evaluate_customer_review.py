"""Integration checks against the existing synthetic fixture and policy corpus."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.graph.customer_review import build_review_graph
from app.sql.review import load_customer_evidence


def main():
    graph = build_review_graph()
    report = graph.invoke({"customer_id": "C003"})["report"]
    assert report["facts"]["transaction_count"] == 8
    assert report["facts"]["cross_border_count"] == 2
    assert report["facts"]["inbound_sgd"] == 18000
    assert report["facts"]["outbound_sgd"] == 18897
    assert len(report["candidate_pairs"]) == 1
    pair = report["candidate_pairs"][0]
    assert pair["incoming_transaction_id"] == "T00038" and pair["outgoing_transaction_id"] == "T00039"
    assert pair["elapsed_minutes"] == 60
    assert report["policy_evidence"] and all(p["page_number"] == 3 for p in report["policy_evidence"])
    assert report["review_signals"][-1]["policy_support"].startswith("context_only")
    for customer, count in (("C004", 0), ("C005", 0), ("C006", 1)):
        txs = load_customer_evidence(customer)["transactions"]
        assert sum(t["amount"] >= 10000 for t in txs) == count, customer
    try:
        load_customer_evidence("C999")
    except ValueError as error:
        assert "not found" in str(error)
    else:
        raise AssertionError("Unknown customer must fail")
    print("PASS: C003 facts/pair/policy context, three time boundaries, missing customer")


if __name__ == "__main__":
    main()
