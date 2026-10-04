"""Build stable LangChain chunks without crossing citation boundaries."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.documents import extract_units


ROOT = Path(__file__).resolve().parents[2]


def content_id(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def split_units(units, metadata, chunk_size=1000, chunk_overlap=150):
    if chunk_size < 1 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True,
        strip_whitespace=False,
    )
    config = dict(splitter="RecursiveCharacterTextSplitter",
                  version=version("langchain-text-splitters"),
                  chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                  length_unit="characters", strip_whitespace=False)
    chunks = []
    for unit_index, unit in enumerate(units):
        if unit.get("needs_review"):
            raise ValueError(f"Review required before indexing: {metadata['source_id']} / {unit['locator']}")
        if not unit["text"].strip():
            raise ValueError(f"Empty source unit: {unit['locator']}")
        for chunk_index, document in enumerate(splitter.create_documents([unit["text"]])):
            start = document.metadata["start_index"]
            end = start + len(document.page_content)
            if start < 0 or unit["text"][start:end] != document.page_content:
                raise ValueError("Chunk offset does not map to source text")
            chunk_metadata = {key: metadata[key] for key in (
                "document_id", "source_id", "content_sha256", "title", "source",
                "document_version", "authority", "jurisdiction", "url",
            )}
            chunk_metadata.update(page_number=unit["page_number"], locator=unit["locator"],
                                  citation_url=unit["citation_url"], unit_index=unit_index,
                                  chunk_index=chunk_index, start_index=start, end_index=end)
            chunk_id = content_id(dict(metadata=chunk_metadata, text=document.page_content, config=config))
            chunks.append(dict(chunk_id=chunk_id, document_id=metadata["document_id"],
                               content=document.page_content, metadata=chunk_metadata))
    return config, chunks


def load_chunks(chunk_size=1000, chunk_overlap=150):
    manifest = json.loads((ROOT / "data/policies/manifest.json").read_text(encoding="utf-8"))
    chunks = []
    documents = []
    config = None
    for record in manifest["documents"]:
        raw = (ROOT / record["raw_path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["content_sha256"]:
            raise ValueError(f"Source hash mismatch: {record['source_id']}")
        parsed = json.loads((ROOT / record["parsed_path"]).read_text(encoding="utf-8"))
        for key in ("document_id", "content_sha256", "source_id"):
            if parsed["metadata"][key] != record[key]:
                raise ValueError(f"Parsed metadata mismatch: {record['source_id']}")
        if parsed["units"] != extract_units(raw, record):
            raise ValueError(f"Parsed text does not match the source snapshot: {record['source_id']}; re-run ingestion")
        config, document_chunks = split_units(parsed["units"], record, chunk_size, chunk_overlap)
        chunks.extend(document_chunks)
        documents.append(dict(document_id=record["document_id"], content_sha256=record["content_sha256"]))
    if not chunks:
        raise ValueError("No verified chunks to index; ingest policy documents first")
    corpus_id = content_id(dict(config=config, chunk_ids=sorted(chunk["chunk_id"] for chunk in chunks)))
    return dict(corpus_id=corpus_id, splitter_config=config, documents=documents, chunks=chunks)
