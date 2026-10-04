"""Extract source text while preserving physical PDF pages or HTML sections."""

import pymupdf
from bs4 import BeautifulSoup


def extract_units(content, source):
    if source["format"] == "pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Expected PDF bytes; received a non-PDF response")
        units = []
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.needs_pass:
                raise ValueError("Encrypted PDF needs explicit handling")
            for number, page in enumerate(document, start=1):
                elements = [dict(text=block[4].strip(), bbox=list(block[:4]))
                            for block in page.get_text("blocks", sort=True)
                            if block[6] == 0 and block[4].strip()]
                text = "\n\n".join(element["text"] for element in elements)
                units.append(dict(page_number=number, locator=f"PDF page {number}",
                                  citation_url=f"{source['url']}#page={number}",
                                  text=text, elements=elements,
                                  needs_review=len(text.strip()) < 100))
        return units
    if source["format"] == "html":
        soup = BeautifulSoup(content, "html.parser")
        article = soup.select_one(source["selector"])
        if article is None:
            raise ValueError("Expected article selector missing; site structure may have changed")
        for node in article.select("script, style, nav, .share, .share-content, .tooltip"):
            node.decompose()
        # SPF exposes the reporting sections as accordion items.
        units = []
        for item in article.select(".accordion-item"):
            heading = item.select_one(".accordion-title")
            body = item.select_one(".accordion-content")
            if heading is None or body is None:
                continue
            title = heading.get_text(" ", strip=True)
            if title in ("Reporting Requirements", "How to file"):
                elements = []
                for table in body.select("table"):
                    rows = [[cell.get_text(" ", strip=True) for cell in row.select("th, td")]
                            for row in table.select("tr")]
                    rows = [row for row in rows if row]
                    if rows:
                        elements.append(dict(type="table", rows=rows))
                        width = max(len(row) for row in rows)
                        lines = ["| " + " | ".join(cell.replace("|", "\\|") for cell in row
                                 + [""] * (width - len(row))) + " |" for row in rows]
                        lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
                        table.replace_with(soup.new_string("\n".join(lines)))
                text = title + "\n\n" + body.get_text("\n", strip=True)
                units.append(dict(page_number=None, locator=title,
                                  citation_url=source["url"], text=text,
                                  elements=elements, needs_review=False))
        if not units:
            raise ValueError("Expected reporting sections missing")
        return units
    raise ValueError(f"Unsupported format: {source['format']}")


def validate_units(units, source):
    if not units or not any(unit["text"].strip() for unit in units):
        raise ValueError("No extractable text")
    identity_text = units[0]["text"] if source.get("format") == "pdf" else " ".join(unit["text"] for unit in units)
    normalized = " ".join(identity_text.split()).casefold()
    for phrase in source["expected_text"]:
        if " ".join(phrase.split()).casefold() not in normalized:
            raise ValueError(f"Document identity or version check failed: {phrase}")
