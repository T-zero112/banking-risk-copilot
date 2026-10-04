"""Retrieve evidence locally or generate a cited answer using OpenAI/DeepSeek."""

import argparse
import json
import sys
import psycopg
from openai import APIConnectionError, APIStatusError
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.answering import build_answer_graph


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["evidence", "openai", "deepseek"], default="evidence")
    args = parser.parse_args()
    result = build_answer_graph(args.mode).invoke({"question": args.question})
    print(json.dumps(dict(mode=result["mode"], answer=result["answer"].model_dump(),
                          sources=[d.metadata for d in result["documents"]]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except APIStatusError as error:
        print(f"Model API request failed (HTTP {error.status_code}). Check key, balance and model access.", file=sys.stderr)
        raise SystemExit(1)
    except APIConnectionError:
        print("Model API connection failed. Check network access or retry later.", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, psycopg.Error) as error:
        print(f"Answer failed: {error}", file=sys.stderr)
        raise SystemExit(1)
