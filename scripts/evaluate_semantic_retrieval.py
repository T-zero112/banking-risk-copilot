"""Small cross-language retrieval smoke tests, not a banking accuracy benchmark."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.semantic import search_semantic

CASES = [
    ("什么情况下需要提交可疑交易报告？", "spf-str-reporting", "Reporting Requirements"),
    ("如何通过SONAR提交报告？", "spf-str-reporting", "How to file"),
    ("资金存入账户后立即提现属于什么风险信号？", "spf-bank-red-flags", "PDF page 1"),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    failures = 0
    for query, source, locator in CASES:
        docs = search_semantic(query, top_k=5, source_id=source)
        found = any(locator.lower() in d.metadata["locator"].lower() for d in docs)
        print(f"{'PASS' if found else 'FAIL'} {query}")
        print([(d.metadata["locator"], round(d.metadata["score"], 4)) for d in docs])
        failures += not found
    if search_semantic("可疑交易", source_id="mas-notice-626"):
        raise AssertionError("Unavailable source must not return evidence")
    if failures:
        raise SystemExit(1)
    print("3 Chinese retrieval cases and unavailable-source filter passed")


if __name__ == "__main__":
    main()
