"""Download verified official sources, extract text, and register metadata."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.rag.documents import extract_units, validate_units
from generate_synthetic_data import sql_literal

POLICIES = ROOT / "data" / "policies"


def register(documents):
    statements = ["BEGIN;"]
    for document in documents:
        fields = ("document_id", "title", "source", "document_type", "published_date",
                  "url", "document_version", "content_sha256")
        values = ", ".join(sql_literal(document[field]) for field in fields)
        statements.append(f"INSERT INTO policy_documents ({', '.join(fields)}) VALUES ({values}) "
                          "ON CONFLICT (url, content_sha256) DO NOTHING;")
    statements.append("COMMIT;")
    command = ["docker", "compose", "exec", "-T", "db", "sh", "-c",
               'exec psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"']
    subprocess.run(command, cwd=ROOT, input="\n".join(statements), text=True, check=True)


def ingest(refresh=False, offline=False, register_metadata=True):
    sources = json.loads((POLICIES / "sources.json").read_text(encoding="utf-8"))["documents"]
    manifest_path = POLICIES / "manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"documents": []}
    cached = {document["source_id"]: document for document in previous["documents"]}
    documents, failures = [], []
    for source in sources:
        try:
            old = cached.get(source["source_id"])
            if old and not refresh:
                content = (ROOT / old["raw_path"]).read_bytes()
                if hashlib.sha256(content).hexdigest() != old["content_sha256"]:
                    raise ValueError("Cached file hash mismatch")
                fetched_at = old["fetched_at"]
                fetched_url = old["fetched_url"]
            else:
                if offline:
                    raise ValueError("No cached document; offline mode does not download")
                response = requests.get(source["url"], timeout=(10, 30))
                response.raise_for_status()
                content = response.content
                fetched_url = response.url
                fetched_at = datetime.now(timezone.utc).isoformat()
            units = extract_units(content, source)
            validate_units(units, source)
            digest = hashlib.sha256(content).hexdigest()
            document_id = f"{source['source_id']}-{digest}"
            raw_path = POLICIES / "raw" / f"{document_id}.{source['format']}"
            parsed_path = POLICIES / "parsed" / f"{document_id}.json"
            for directory in (raw_path.parent, parsed_path.parent):
                directory.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(content)
            record = dict(source, document_id=document_id, content_sha256=digest,
                          fetched_at=fetched_at, fetched_url=fetched_url,
                          raw_path=raw_path.relative_to(ROOT).as_posix(),
                          parsed_path=parsed_path.relative_to(ROOT).as_posix(),
                          unit_count=len(units),
                          review_locators=[unit["locator"] for unit in units if unit["needs_review"]])
            parsed_path.write_text(json.dumps(dict(metadata=record, units=units), indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
            markdown = [f"# {source['title']}", f"Source: {source['url']}",
                        f"Version: {source['document_version']}", f"SHA-256: {digest}"]
            for unit in units:
                markdown.extend([f"## {unit['locator']}", unit["text"]])
            parsed_path.with_suffix(".md").write_text("\n\n".join(markdown) + "\n", encoding="utf-8")
            documents.append(record)
            print(f"READY {source['source_id']}: {len(units)} page(s)/section(s)", flush=True)
        except (requests.RequestException, OSError, ValueError, RuntimeError) as error:
            failures.append(dict(source_id=source["source_id"], url=source["url"], reason=str(error)))
            print(f"UNAVAILABLE {source['source_id']}: {error}", flush=True)
            # Preserve previously verified versions when a refresh fails.
            if source["source_id"] in cached:
                old = cached[source["source_id"]]
                path = ROOT / old["raw_path"]
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == old["content_sha256"]:
                    documents.append(old)
    manifest = dict(documents=documents, unavailable_sources=failures)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not documents:
        raise ValueError("No verified documents available")
    if register_metadata:
        register(documents)
    print(f"Verified documents: {len(documents)}; unavailable sources: {len(failures)}. "
          "See data/policies/manifest.json.")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch current bytes without deleting old snapshots")
    parser.add_argument("--offline", action="store_true", help="Use cached documents only")
    parser.add_argument("--no-register", action="store_true", help="Do not write database metadata")
    args = parser.parse_args()
    if args.refresh and args.offline:
        parser.error("--refresh and --offline cannot be combined")
    try:
        ingest(args.refresh, args.offline, not args.no_register)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Ingestion failed: {error}", file=sys.stderr)
        raise SystemExit(1)
