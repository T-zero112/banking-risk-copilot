"""Produce a banking review report using fixed SQL and cited policy evidence."""

import argparse
import json
from pathlib import Path
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audit.customer_review import AuditedReviewError, run_customer_review
from app.graph.review_explanation import serialize


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("customer_id", help="Synthetic customer ID, e.g. C003")
    parser.add_argument("--mode", choices=["deterministic", "deepseek"], default="deterministic")
    args = parser.parse_args()
    report = run_customer_review(args.customer_id, args.mode)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=serialize))
    if report.get("ai_generation", {}).get("status") == "failed":
        print("AI explanation failed validation or API execution; deterministic evidence is retained.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditedReviewError as error:
        print(f"Review failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, psycopg.Error):
        print("Review failed: invalid input or database error", file=sys.stderr)
        raise SystemExit(1)
