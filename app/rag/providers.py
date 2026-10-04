"""DeepSeek JSON-mode client shared by policy answers and customer reviews."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def deepseek_generator(schema, max_tokens=2048, *, include_raw=False):
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ValueError("Set DEEPSEEK_API_KEY in .env to enable paid LLM generation")
    from langchain_openai import ChatOpenAI
    client = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"), api_key=key,
        base_url="https://api.deepseek.com", temperature=0, timeout=60,
        max_retries=0, max_tokens=max_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )
    kwargs = {"method": "json_mode"}
    if include_raw:
        kwargs["include_raw"] = True
    return client.with_structured_output(schema, **kwargs)


def call_metadata(message):
    """Persist only allowlisted provider counters; never raw content or headers."""
    if message is None:
        return {"usage_available": False}
    response = getattr(message, "response_metadata", {}) or {}
    usage = getattr(message, "usage_metadata", {}) or {}
    raw = response.get("token_usage", {}) or {}

    def count(*values):
        return next((v for v in values if type(v) is int and v >= 0), None)

    result = dict(input_tokens=count(raw.get("prompt_tokens"), usage.get("input_tokens")),
                  output_tokens=count(raw.get("completion_tokens"), usage.get("output_tokens")),
                  total_tokens=count(raw.get("total_tokens"), usage.get("total_tokens")),
                  cache_hit_tokens=count(raw.get("prompt_cache_hit_tokens"), (usage.get("input_token_details") or {}).get("cache_read")),
                  cache_miss_tokens=count(raw.get("prompt_cache_miss_tokens")),
                  reported_model=response.get("model_name"), finish_reason=response.get("finish_reason"),
                  message_id=getattr(message, "id", None))
    result["usage_available"] = result["input_tokens"] is not None and result["output_tokens"] is not None
    return result
