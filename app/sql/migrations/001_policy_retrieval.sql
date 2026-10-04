-- Applied transactionally by scripts/build_policy_index.py.
CREATE TABLE IF NOT EXISTS policy_corpora (
    corpus_id TEXT PRIMARY KEY,
    splitter_config JSONB NOT NULL,
    chunk_count INTEGER NOT NULL CHECK (chunk_count > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL REFERENCES policy_corpora(corpus_id),
    document_id TEXT NOT NULL REFERENCES policy_documents(document_id),
    content TEXT NOT NULL CHECK (length(content) > 0),
    metadata JSONB NOT NULL CHECK (jsonb_typeof(metadata) = 'object'),
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    PRIMARY KEY (corpus_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS policy_retrieval_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    active_corpus_id TEXT NOT NULL REFERENCES policy_corpora(corpus_id)
);

CREATE INDEX IF NOT EXISTS idx_policy_chunks_search ON policy_chunks USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_policy_chunks_document ON policy_chunks (document_id);
