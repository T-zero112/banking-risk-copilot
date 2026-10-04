# Public Policy Corpus

The first corpus contains two verified Singapore Police Force / STRO sources:

| Source | Coverage | Locator |
| --- | --- | --- |
| [Red Flag Indicators for Bank](https://www.police.gov.sg/-/media/SPF/Advisories/Bank-Indicators_upd.pdf) | Transaction patterns and contextual warning signs | 7 physical PDF pages |
| [Suspicious Transaction Reporting](https://www.police.gov.sg/Advisories/Commercial-Crimes/Suspicious-Transaction-Reporting-Office/Suspicious-Transaction-Reporting) | Reporting Requirements and How to file | 2 named HTML sections |

The bank indicators are an aid to review, not proof of wrongdoing. For example,
rapid incoming/outgoing transfers in the C003 fixture can motivate further
review, but the data does not establish whether the customer has a plausible
business explanation. The reporting page is guidance, not a substitute for the
underlying legislation.

## Download Status

Source metadata was checked on 2026-10-01. Three sources are catalogued but could
not be downloaded from this machine during setup:

- [MAS Notice 626](https://www.mas.gov.sg/regulation/notices/notice-626): official
  PDF link returned an HTML maintenance page with HTTP 200.
- [Guidelines to MAS Notice 626](https://www.mas.gov.sg/regulation/guidelines/guidelines-to-notice-626-on-prevention-of-money-laundering-and-cft-for-banks):
  official PDF link returned the same maintenance page. The landing page says
  last revised 30 June 2025, while the linked PDF cover viewed through the web
  research tool says 1 July 2025; the catalogue preserves this discrepancy.
- [FATF Recommendations](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html):
  the official page and linked PDF indicate June 2026, but direct download returned
  HTTP 403. The filename still contains 2012, which is not its revision date.

These three documents are not in the downloaded corpus or `policy_documents`.
The current corpus supports an initial transaction-pattern explanation demo,
but does not yet cover the full MAS customer due diligence requirements.
FATF standards must retain their international scope when added; they must not
be represented as Singapore bank-specific rules.

## Reproduce

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-policy.txt
.\.venv\Scripts\python.exe scripts/ingest_policy_documents.py
.\.venv\Scripts\python.exe scripts/verify_policy_documents.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The running Compose database is required for metadata registration. Use
`--no-register` for local-only extraction. Use `--offline` to reprocess verified
cached files; missing sources remain unavailable. Use `--refresh` to retry
downloads and check current source bytes. It retains older snapshots and never
relabels a maintenance page as policy text.

- `data/policies/sources.json`: tracked official URLs, expected identity/version
  phrases, authority, jurisdiction, and source dates. Unknown publication dates
  are NULL; they are not inferred from download times.
- `data/policies/raw/`: downloaded PDF/HTML snapshots named using SHA-256.
- `data/policies/parsed/`: UTF-8 Markdown and JSON with source metadata, text,
  physical pages/section names, citation URLs, and PDF block bounding boxes.
- `data/policies/manifest.json`: verified files and explicit download failures.
- `policy_documents`: version metadata registered idempotently by URL and hash.

PDF identity/version checks use the first page to avoid matching an obsolete date
in endnotes. HTML extraction selects reporting content and removes navigation and
share controls; tables preserve rows in JSON and Markdown.

## Quality and Boundaries

The pdf-parser skill classified the bank indicator PDF as four text pages and
three mixed-layout pages, with no pages needing vision transcription. Its local
Markdown/JSON outputs are under `data/policies/qa/`. Pages 1, 5, and 7 were rendered
and spot-checked against extracted text; no OCR or vision transcription was used.
The production loader uses PyMuPDF; this QA skill is not a runtime dependency.

Raw documents, extracted text, and QA outputs are ignored by Git. Public access
does not imply an open-source redistribution license. The repository tracks the
download code and source catalogue rather than republishing entire documents.

The ingestion step does not create embeddings, vector indexes, or LLM answers. No
model API key or paid model call is required. [Policy retrieval](policy-retrieval.md)
now chunks verified units with document IDs, content hashes, page/section locators,
and authority metadata, and builds an English text-search index. New formats or complex PDFs require layout review;
short text pages are marked `needs_review` rather than silently accepted.
