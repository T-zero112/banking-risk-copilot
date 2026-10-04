"""Read one locally stored customer review audit by request ID."""

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audit.review import ReviewAuditStore
from app.graph.review_explanation import serialize


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_id", type=UUID)
    args = parser.parse_args()
    row = ReviewAuditStore().read(str(args.request_id))
    if row is None:
        print("Review audit not found", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(row, ensure_ascii=False, indent=2, default=serialize))
