"""Verify local source hashes, citation locators, and database registration."""

import hashlib
import json
from pathlib import Path

from verify_database import query, require

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / "data" / "policies" / "manifest.json").read_text(encoding="utf-8"))
    require(bool(manifest["documents"]), "No verified documents")
    registered = {row["document_id"]: row for row in query(
        "SELECT document_id, content_sha256, url FROM policy_documents"
    )}
    for document in manifest["documents"]:
        digest = hashlib.sha256((ROOT / document["raw_path"]).read_bytes()).hexdigest()
        require(digest == document["content_sha256"], "Source hash mismatch")
        parsed = json.loads((ROOT / document["parsed_path"]).read_text(encoding="utf-8"))
        require(parsed["metadata"]["document_id"] == document["document_id"], "Parsed metadata mismatch")
        require(len(parsed["units"]) == document["unit_count"], "Page/section count mismatch")
        require(document["document_id"] in registered, "Database registration missing")
        row = registered[document["document_id"]]
        require(row["content_sha256"] == digest and row["url"] == document["url"], "Database metadata mismatch")
        for unit in parsed["units"]:
            require(bool(unit["text"].strip()) and bool(unit["locator"]), "Empty source unit")
            if document["format"] == "pdf":
                require(unit["page_number"] >= 1 and f"#page={unit['page_number']}" in unit["citation_url"],
                        "PDF citation locator missing")
        print(f"PASS {document['source_id']}: {document['unit_count']} page(s)/section(s)")
    print(f"Unavailable sources: {len(manifest['unavailable_sources'])}; they are not part of the downloaded corpus.")


if __name__ == "__main__":
    main()
