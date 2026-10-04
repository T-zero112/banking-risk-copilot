CREATE TABLE IF NOT EXISTS policy_embedding_indexes (
    corpus_id TEXT PRIMARY KEY REFERENCES policy_corpora(corpus_id),
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS policy_chunk_embeddings (
    corpus_id TEXT NOT NULL REFERENCES policy_embedding_indexes(corpus_id),
    chunk_id TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    PRIMARY KEY (corpus_id, chunk_id),
    FOREIGN KEY (corpus_id, chunk_id) REFERENCES policy_chunks(corpus_id, chunk_id)
);
