"""Check retrieval evidence and citation integrity against a small fixed suite."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag.chunking import load_chunks
from app.rag.retrieval import PolicyRetriever
from app.sql.database import connect


def main():
    expected = load_chunks()
    with connect() as connection:
        state = connection.execute("SELECT active_corpus_id FROM policy_retrieval_state WHERE singleton").fetchone()
        if state is None or state["active_corpus_id"] != expected["corpus_id"]:
            raise ValueError("This suite expects the default index configuration")
        rows = connection.execute("SELECT chunk_id, content, metadata FROM policy_chunks WHERE corpus_id = %s",
                                  (expected["corpus_id"],)).fetchall()
    actual = {row["chunk_id"]: row for row in rows}
    if len(actual) != len(expected["chunks"]):
        raise ValueError("Chunk count mismatch")
    for chunk in expected["chunks"]:
        row = actual.get(chunk["chunk_id"])
        if row is None or row["content"] != chunk["content"] or row["metadata"] != chunk["metadata"]:
            raise ValueError("Indexed content or citation metadata does not match the source")
    cases = json.loads((ROOT / "evals/policy_retrieval_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        documents = PolicyRetriever(top_k=3, source_id=case.get("source_id")).invoke(case["query"])
        if case.get("expect_empty"):
            passed = not documents
        else:
            passed = any(doc.metadata["locator"] == case["expected_locator"]
                         and case["expected_phrase"].casefold() in " ".join(doc.page_content.split()).casefold()
                         for doc in documents)
        results.append(dict(id=case["id"], passed=passed,
                            locators=[doc.metadata["locator"] for doc in documents]))
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: {results[-1]['locators']}")
    report = dict(corpus_id=expected["corpus_id"], chunk_count=len(actual), cases=results,
                  note="Small deterministic smoke suite; not a general retrieval accuracy estimate.")
    (ROOT / "data/policies/retrieval-evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not all(result["passed"] for result in results):
        raise ValueError("Retrieval evaluation failed")
    print(f"PASS: {len(results)} retrieval cases and exact indexed source/citation integrity.")


if __name__ == "__main__":
    main()
