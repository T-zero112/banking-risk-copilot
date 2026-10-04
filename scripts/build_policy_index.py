"""Apply the policy search migration and atomically activate a verified corpus."""

import argparse
import json
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag.chunking import load_chunks
from app.sql.database import connect


def build_index(chunk_size=1000, chunk_overlap=150):
    corpus = load_chunks(chunk_size, chunk_overlap)
    with connect("admin") as connection:
        connection.execute((ROOT / "app/sql/migrations/001_policy_retrieval.sql").read_text(encoding="utf-8"))
        for document in corpus["documents"]:
            row = connection.execute("SELECT content_sha256 FROM policy_documents WHERE document_id = %s",
                                     (document["document_id"],)).fetchone()
            if row is None or row["content_sha256"] != document["content_sha256"]:
                raise ValueError("Document is not registered with the expected hash; run policy ingestion first")
        connection.execute("""
            INSERT INTO policy_corpora (corpus_id, splitter_config, chunk_count)
            VALUES (%s, %s, %s) ON CONFLICT (corpus_id) DO NOTHING
        """, (corpus["corpus_id"], Jsonb(corpus["splitter_config"]), len(corpus["chunks"])))
        with connection.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO policy_chunks (chunk_id, corpus_id, document_id, content, metadata)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (corpus_id, chunk_id) DO NOTHING
            """, [(chunk["chunk_id"], corpus["corpus_id"], chunk["document_id"], chunk["content"],
                   Jsonb(chunk["metadata"])) for chunk in corpus["chunks"]])
        count = connection.execute("SELECT COUNT(*) AS n FROM policy_chunks WHERE corpus_id = %s",
                                   (corpus["corpus_id"],)).fetchone()["n"]
        if count != len(corpus["chunks"]):
            raise ValueError("Indexed chunk count differs; corpus was not activated")
        connection.execute("""
            INSERT INTO policy_retrieval_state (singleton, active_corpus_id) VALUES (TRUE, %s)
            ON CONFLICT (singleton) DO UPDATE SET active_corpus_id = EXCLUDED.active_corpus_id
        """, (corpus["corpus_id"],))
    summary = {key: corpus[key] for key in ("corpus_id", "splitter_config", "documents")}
    summary["chunk_count"] = len(corpus["chunks"])
    output = ROOT / "data/policies/index.json"
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    args = parser.parse_args()
    try:
        build_index(args.chunk_size, args.chunk_overlap)
    except (OSError, ValueError, psycopg.Error) as error:
        print(f"Indexing failed: {error}", file=sys.stderr)
        raise SystemExit(1)
