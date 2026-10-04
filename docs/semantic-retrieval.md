# Multilingual retrieval and answers

Install: `.venv\Scripts\python.exe -m pip install -r requirements-semantic.txt`.
Build: `.venv\Scripts\python.exe scripts/build_semantic_index.py`.
Search: `.venv\Scripts\python.exe scripts/search_policies.py "什么情况下需要提交可疑交易报告？" --method semantic`.
Evidence: `.venv\Scripts\python.exe scripts/ask_policy.py "存款后立即提现有什么风险？"`.

The local FastEmbed multilingual MiniLM model produces 384-dimensional vectors.
The first run downloads model files into ignored `data/models/`; CPU inference
does not call a paid embedding API. The index builder rejects chunks reaching
the 512-token limit (texts exceeding it are rejected). Vectors are published in a single database transaction;
retrieval refuses indexes built for another corpus/model configuration.
Small-corpus searches use exact pgvector cosine distance, not an ANN index.
The English lexical baseline remains available with `--method lexical`.

LangGraph runs retrieve -> generate -> validate. Default `evidence` mode returns
verbatim excerpts, not generated answers or Chinese translations. To generate
Chinese answers, configure `OPENAI_API_KEY` and `MODEL_NAME` in local `.env`,
then pass `--mode openai`. This sends the question and retrieved public excerpts
to OpenAI and incurs API charges. Never send customer data or credentials.

## DeepSeek

Set `DEEPSEEK_API_KEY` in the ignored local `.env`. `DEEPSEEK_MODEL` defaults to
`deepseek-flash` (the current official example); change it to a model your account
supports. Do not put a DeepSeek key into `OPENAI_API_KEY`. Use:

```powershell
.\.venv\Scripts\python.exe scripts/ask_policy.py "什么情况下需要提交可疑交易报告？" --mode deepseek
```

This explicitly selects the official `https://api.deepseek.com` endpoint using
the existing LangChain OpenAI-compatible client. JSON mode plus local Pydantic
and citation checks are used; JSON validity alone does not guarantee grounding.
Thinking is disabled, output is capped at 2048 tokens, timeout is 60 seconds,
and automatic retries are disabled to avoid duplicate paid calls. A truncated
or empty response fails validation, rather than becoming an accepted answer.
Public evidence and the question leave this machine and API fees apply.
No live request is made by setup or unit tests. The customer review command
remains deterministic by default; explicitly pass `--mode deepseek` to generate
a review explanation. See [customer review](customer-review.md).

Official references: [API setup](https://api-docs.deepseek.com/zh-cn/),
[JSON output](https://api-docs.deepseek.com/guides/json_mode/).

Citation validation checks identifier membership, not whether claims logically
follow from evidence. Similarity is not confidence: top-k semantic retrieval
can return irrelevant chunks for unrelated questions. Evidence mode must not
be interpreted as a relevance judgement; LLM mode is instructed to abstain,
but that is not a reliable safety boundary. A calibrated relevance gate and
human-reviewed answer evaluations are future work.

The corpus still contains only two SPF documents, not unavailable MAS/FATF
documents. Red flags are indicators, not automatic findings of money laundering.
This prototype does not supply legal advice or execute generated banking SQL.
Model and tokenizer artifact SHA-256 fingerprints are stored with each index;
retrieval refuses a changed artifact until the index is rebuilt. Preserve the
local cache when comparing experimental results.

Three Chinese, source-filtered smoke cases passed at top-5; the rapid-withdrawal
target ranked fifth, not first. Heading-only chunks can rank highly. These tests
do not measure unfiltered retrieval or answer accuracy. Run
`scripts/evaluate_semantic_retrieval.py` and retain the lexical baseline tests.
