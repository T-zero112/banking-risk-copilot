"""LangChain retriever backed by PostgreSQL English full-text search."""

import re

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from app.sql.database import connect


def search_policy(query, top_k=5, source_id=None):
    if not query.strip() or len(query) > 2000:
        raise ValueError("Query must contain 1 to 2000 characters")
    if re.search(r"[\u3400-\u9fff]", query):
        raise ValueError("This baseline searches English documents. Use English keywords; cross-language retrieval is not enabled.")
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    with connect() as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        state = connection.execute("SELECT active_corpus_id FROM policy_retrieval_state WHERE singleton").fetchone()
        if state is None:
            raise ValueError("No active corpus. Run scripts/build_policy_index.py first")
        rows = connection.execute("""
            WITH terms AS (SELECT websearch_to_tsquery('english', %(query)s) AS query)
            SELECT c.chunk_id, c.corpus_id, c.content, c.metadata,
                   ts_rank_cd(c.search_vector, terms.query, 32) AS score
            FROM policy_chunks c CROSS JOIN terms
            WHERE c.corpus_id = %(corpus_id)s AND c.search_vector @@ terms.query
              AND (%(source_id)s::text IS NULL OR c.metadata->>'source_id' = %(source_id)s)
            ORDER BY score DESC, c.chunk_id
            LIMIT %(top_k)s
        """, dict(query=query, corpus_id=state["active_corpus_id"], source_id=source_id, top_k=top_k)).fetchall()
    return [Document(page_content=row["content"], metadata=dict(
        row["metadata"], chunk_id=row["chunk_id"], corpus_id=row["corpus_id"],
        score=float(row["score"]), retrieval_method="postgres_english_full_text",
    )) for row in rows]


class PolicyRetriever(BaseRetriever):
    top_k: int = Field(default=5, ge=1, le=20)
    source_id: str | None = None

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun):
        return search_policy(query, self.top_k, self.source_id)
