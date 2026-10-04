"""Local multilingual embeddings and exact pgvector cosine retrieval."""

from functools import lru_cache
import hashlib
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from pgvector.psycopg import register_vector
from pydantic import Field
from tokenizers import Tokenizer

from app.sql.database import connect

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "fastembed-0.8.1-onnx-Q-512"
ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def model():
    return TextEmbedding(MODEL, cache_dir=str(ROOT / "data/models"), threads=2)


@lru_cache(maxsize=1)
def model_version():
    directory = Path(model().model._model_dir)
    digest = hashlib.sha256()
    for name in (model().model.model_description.model_file, "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "config.json"):
        path = directory / name
        if not path.is_file():
            raise ValueError(f"Missing model artifact: {name}")
        digest.update(name.encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return f"{MODEL_VERSION}-{digest.hexdigest()}"


def checked_vector(value):
    vector = np.asarray(value, dtype=np.float32)
    if vector.shape != (384,) or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
        raise ValueError("Expected a finite, nonzero 384-dimensional embedding")
    return vector


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        tokenizer = Tokenizer.from_str(model().model.tokenizer.to_str())
        tokenizer.no_truncation()
        tokenizer.no_padding()
        if any(len(tokenizer.encode(text).ids) > 512 for text in texts):
            raise ValueError("Text exceeds 512 tokens; use smaller chunks or a shorter query")
        return [checked_vector(v).tolist() for v in model().embed(texts)]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def search_semantic(query, top_k=5, source_id=None):
    if not query.strip() or len(query) > 2000 or not 1 <= top_k <= 20:
        raise ValueError("Query must contain 1-2000 characters; top_k must be 1-20")
    vector = checked_vector(LocalEmbeddings().embed_query(query))
    with connect() as connection:
        register_vector(connection)
        connection.commit()
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        state = connection.execute("""
            SELECT s.active_corpus_id, i.model_name, i.model_version
            FROM policy_retrieval_state s JOIN policy_embedding_indexes i
            ON i.corpus_id=s.active_corpus_id WHERE s.singleton
        """).fetchone()
        if not state or state["model_name"] != MODEL or state["model_version"] != model_version():
            raise ValueError("No compatible embedding index. Run scripts/build_semantic_index.py")
        rows = connection.execute("""
            SELECT c.chunk_id, c.corpus_id, c.content, c.metadata,
                   1 - (e.embedding <=> %(vector)s) AS score
            FROM policy_chunk_embeddings e JOIN policy_chunks c
              ON c.corpus_id=e.corpus_id AND c.chunk_id=e.chunk_id
            WHERE c.corpus_id=%(corpus)s
              AND (%(source)s::text IS NULL OR c.metadata->>'source_id'=%(source)s)
            ORDER BY e.embedding <=> %(vector)s, c.chunk_id LIMIT %(limit)s
        """, dict(vector=vector, corpus=state["active_corpus_id"], source=source_id, limit=top_k)).fetchall()
    return [Document(page_content=r["content"], metadata=dict(
        r["metadata"], chunk_id=r["chunk_id"], corpus_id=r["corpus_id"],
        score=float(r["score"]), retrieval_method="multilingual_cosine",
    )) for r in rows]


class SemanticPolicyRetriever(BaseRetriever):
    top_k: int = Field(default=5, ge=1, le=20)
    source_id: str | None = None

    def _get_relevant_documents(self, query, *, run_manager):
        return search_semantic(query, self.top_k, self.source_id)
