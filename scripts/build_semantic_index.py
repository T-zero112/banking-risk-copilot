"""Embed the active immutable corpus locally; publish all vectors atomically."""

import sys
from pathlib import Path

from pgvector.psycopg import register_vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag.semantic import MODEL, LocalEmbeddings, checked_vector, model_version
from app.sql.database import connect


def build_index():
    with connect("admin") as connection:
        state = connection.execute("SELECT active_corpus_id FROM policy_retrieval_state WHERE singleton").fetchone()
        if not state:
            raise ValueError("Build the policy chunk index first")
        corpus = state["active_corpus_id"]
        rows = connection.execute("SELECT chunk_id, content FROM policy_chunks WHERE corpus_id=%s ORDER BY chunk_id", (corpus,)).fetchall()
    vectors = LocalEmbeddings().embed_documents([r["content"] for r in rows])
    if len(vectors) != len(rows) or not rows:
        raise ValueError("Incomplete embedding batch")
    with connect("admin") as connection:
        register_vector(connection)
        connection.execute((ROOT / "app/sql/migrations/002_policy_embeddings.sql").read_text())
        current = connection.execute("SELECT active_corpus_id FROM policy_retrieval_state WHERE singleton FOR UPDATE").fetchone()
        if current["active_corpus_id"] != corpus:
            raise ValueError("Active corpus changed during embedding; retry")
        connection.execute("DELETE FROM policy_chunk_embeddings WHERE corpus_id=%s", (corpus,))
        connection.execute("""INSERT INTO policy_embedding_indexes(corpus_id,model_name,model_version)
            VALUES(%s,%s,%s) ON CONFLICT(corpus_id) DO UPDATE
            SET model_name=EXCLUDED.model_name,model_version=EXCLUDED.model_version,created_at=CURRENT_TIMESTAMP""", (corpus, MODEL, model_version()))
        with connection.cursor() as cursor:
            cursor.executemany("INSERT INTO policy_chunk_embeddings VALUES(%s,%s,%s)",
                               [(corpus, r["chunk_id"], checked_vector(v)) for r, v in zip(rows, vectors)])
    print(f"Indexed {len(rows)} chunks with {MODEL} (384 dimensions)")


if __name__ == "__main__":
    build_index()
