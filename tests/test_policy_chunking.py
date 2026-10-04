import unittest

from app.rag.chunking import split_units


METADATA = dict(document_id="doc-123", source_id="fixture", content_sha256="a" * 64,
                title="Fixture", source="Test", document_version="v1", authority="official_guidance",
                jurisdiction="SG", url="https://example.test/document.pdf")


def unit(text, page=1, review=False):
    return dict(text=text, page_number=page, locator=f"PDF page {page}",
                citation_url=f"https://example.test/document.pdf#page={page}", needs_review=review)


class PolicyChunkTests(unittest.TestCase):
    def test_chunks_preserve_source_offsets_and_page_boundaries(self):
        units = [unit("Incoming funds are deposited. " * 30), unit("Outgoing transfers need context. " * 30, page=2)]
        _, chunks = split_units(units, METADATA, 160, 30)
        self.assertGreater(len(chunks), 2)
        for chunk in chunks:
            metadata = chunk["metadata"]
            original = units[metadata["unit_index"]]
            self.assertEqual(chunk["content"], original["text"][metadata["start_index"]:metadata["end_index"]])
            self.assertEqual(metadata["page_number"], original["page_number"])
            self.assertLessEqual(len(chunk["content"]), 160)
            self.assertEqual(metadata["content_sha256"], METADATA["content_sha256"])

    def test_chunk_identity_is_stable_and_changes_with_configuration(self):
        units = [unit("Repeated paragraph. " * 50)]
        _, first = split_units(units, METADATA, 200, 40)
        _, repeated = split_units(units, METADATA, 200, 40)
        _, changed = split_units(units, METADATA, 200, 20)
        self.assertEqual(first, repeated)
        self.assertNotEqual([chunk["chunk_id"] for chunk in first], [chunk["chunk_id"] for chunk in changed])

    def test_unreviewed_pages_and_invalid_settings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Review required"):
            split_units([unit("Unreviewed scan", review=True)], METADATA)
        for size, overlap in ((0, 0), (100, -1), (100, 100)):
            with self.subTest(size=size, overlap=overlap), self.assertRaises(ValueError):
                split_units([unit("text")], METADATA, size, overlap)


if __name__ == "__main__":
    unittest.main()
