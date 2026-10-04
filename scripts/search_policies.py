"""Search the active corpus and display verbatim chunks with citations."""

import argparse
import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag.retrieval import PolicyRetriever


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Question or keywords")
    parser.add_argument("--method", choices=["lexical", "semantic"], default="lexical")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--source", help="Optional catalogue source_id")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args()
    if args.method == "semantic":
        from app.rag.semantic import SemanticPolicyRetriever
        retriever = SemanticPolicyRetriever
    else:
        retriever = PolicyRetriever
    documents = retriever(top_k=args.top_k, source_id=args.source).invoke(args.query)
    if args.json:
        print(json.dumps([dict(content=doc.page_content, metadata=doc.metadata) for doc in documents],
                         indent=2, ensure_ascii=True))
        return
    if not documents:
        print("No matching evidence in the active corpus. Try fewer English keywords.")
    for number, document in enumerate(documents, start=1):
        metadata = document.metadata
        print(f"\n[{number}] {metadata['title']} | {metadata['locator']} | score={metadata['score']:.4f}")
        print(f"Source: {metadata['citation_url']}")
        print(f"Chunk: {metadata['chunk_id']}")
        print(document.page_content)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, psycopg.Error) as error:
        print(f"Search failed: {error}", file=sys.stderr)
        raise SystemExit(1)
