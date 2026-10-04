# Policy Chunking and Retrieval

This milestone uses LangChain's `RecursiveCharacterTextSplitter` and a LangChain
`BaseRetriever` backed by PostgreSQL English full-text search. It requires no
embedding API key or model calls. This is a lexical retrieval baseline, not vector
similarity search or a complete RAG answer generator.

## Run

With the local database running and public documents already ingested:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
.\.venv\Scripts\python.exe scripts/build_policy_index.py
.\.venv\Scripts\python.exe scripts/search_policies.py "withdrawn immediately deposited" --top-k 3
.\.venv\Scripts\python.exe scripts/search_policies.py "reasonable grounds suspect" --source spf-str-reporting
.\.venv\Scripts\python.exe scripts/search_policies.py "matching payments credits" --json
.\.venv\Scripts\python.exe scripts/evaluate_policy_retrieval.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The two current sources produce 30 chunks with the default settings. The index
script applies `app/sql/migrations/001_policy_retrieval.sql` to the existing
database; it does not rerun the initial schema or delete banking data.

Connection settings use environment variables or `.env`. A SQLAlchemy-style
`postgresql+psycopg://` DATABASE_URL is accepted, as is a plain `postgresql://`
URL. Without DATABASE_URL, the existing local Compose settings are used.

## Chunk and Citation Contract

Each original PDF page or HTML section is split separately with a maximum of
1,000 characters and target overlap of 150 characters. These are character
counts, not tokens. Recursive paragraph/line boundaries mean overlap can be less
than its target. These starting settings are not a tuned optimum.

Chunks retain document ID, original file SHA-256, source ID, title, version,
authority, jurisdiction, citation URL, physical PDF page or named HTML section,
and exact start/end character offsets in that unit. Printed page labels can
differ from physical PDF pages. A chunk never crosses a source-unit boundary.
Pages marked `needs_review` block indexing until reviewed.

Before indexing, raw file hashes are checked and parsed units are compared with
fresh extraction from the same local source bytes. Parser behavior changes may
require re-running ingestion. Content and splitting settings determine stable
chunk and corpus IDs; repeated builds do not duplicate rows.

`policy_corpora` records corpus settings. `policy_chunks` stores text, metadata,
and a generated English tsvector indexed with GIN. `policy_retrieval_state` points
to the active corpus. The build inserts a corpus and activates it in one
transaction. Old corpus rows are preserved; searches query only the active one.
Refreshing downloads alone does not rebuild or switch the search index.

## Retrieval Behavior

Queries use `websearch_to_tsquery('english', ...)` and `ts_rank_cd`. Ordinary
keywords are combined with AND; quoted phrases and OR are supported. Long natural
language questions can miss evidence because they require too many words to
match. Try concise English keywords. Chinese queries are rejected with a clear
message; no translation or cross-language semantic model is configured.

`--top-k` is limited to 1-20. `--source` narrows to a catalogue source ID. A query
with no matches returns an empty result rather than unrelated fallback text.
Ranks are search scores, not probabilities or calibrated confidence. Overlapping
chunks can return similar passages.

The Python interface returns LangChain Documents:

```python
from app.rag.retrieval import PolicyRetriever

retriever = PolicyRetriever(top_k=3, source_id="spf-bank-red-flags")
documents = retriever.invoke("matching payments credits")
for document in documents:
    print(document.page_content)
    print(document.metadata["citation_url"])
```

The retrieval SQL is fixed and parameterized. Query text and source filters are
bound as values. Retrieval runs in a read-only transaction with a five-second
statement timeout using banking_reader. Runtime role isolation is documented in
[database permissions](database-permissions.md); there is still no free-form
LLM-generated SQL executor. The customer review API uses this fixed-query baseline.

## Verification and Next Stage

The evaluation checks expected phrases and citation locations in the top three
results, unrelated queries, unavailable sources, and SQL-like query/filter
inputs. It also compares every indexed chunk and citation metadata with the
source-derived chunks. It is a small deterministic smoke suite, not an estimate
of performance on unseen banking questions.

The MAS/FATF files remain unavailable and are not searched. Current corpus scope
does not support a full MAS KYC compliance analysis. See `docs/policy-corpus.md`.

Next, add semantic embeddings and benchmark them against this baseline, then
connect SQL evidence and retrieved policy Documents in LangGraph. Selecting an
embedding model must also settle language support, dimensionality, cost, and
document-processing requirements.

References: [LangChain recursive splitting](https://docs.langchain.com/oss/python/integrations/splitters/recursive_text_splitter),
[PostgreSQL text search](https://www.postgresql.org/docs/17/textsearch-controls.html),
and [Psycopg query parameters](https://www.psycopg.org/psycopg3/docs/basic/params.html).
