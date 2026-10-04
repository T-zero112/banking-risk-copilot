import unittest

from app.rag.documents import extract_units, validate_units


class PolicyExtractionTests(unittest.TestCase):
    def test_maintenance_html_cannot_be_imported_as_pdf(self):
        with self.assertRaisesRegex(ValueError, "non-PDF"):
            extract_units(b"<html>Maintenance</html>", {"format": "pdf"})

    def test_unexpected_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "version check"):
            validate_units([dict(text="MAS Notice 626 revised 2022")],
                           dict(expected_text=["MAS Notice 626", "30 June 2025"]))

    def test_html_sections_exclude_navigation_and_share_controls(self):
        content = b'''<main id="mainContent"><nav>Unrelated menu</nav><article>
        <div class="accordion-item"><div class="accordion-title">Reporting Requirements</div>
        <div class="accordion-content"><p>Report suspicious activity.</p>
        <div class="tooltip">Share This Content</div></div></div>
        <div class="accordion-item"><div class="accordion-title">How to file</div>
        <div class="accordion-content"><table><tr><th>Industry</th><th>Guidance</th></tr>
        <tr><td>Bank</td><td>Notice 626</td></tr></table></div></div></article></main>'''
        units = extract_units(content, dict(format="html", selector="main article", url="https://example.test/"))
        self.assertEqual([unit["locator"] for unit in units], ["Reporting Requirements", "How to file"])
        self.assertNotIn("Unrelated menu", units[0]["text"])
        self.assertNotIn("Share This Content", units[0]["text"])
        self.assertIn("| Bank | Notice 626 |", units[1]["text"])
        self.assertEqual(units[1]["elements"][0]["rows"][1], ["Bank", "Notice 626"])

    def test_old_date_in_endnotes_does_not_verify_the_cover_version(self):
        units = [dict(text="MAS Notice 626 revised 2026"), dict(text="History: 30 June 2025")]
        with self.assertRaisesRegex(ValueError, "version check"):
            validate_units(units, dict(format="pdf", expected_text=["MAS Notice 626", "30 June 2025"]))


if __name__ == "__main__":
    unittest.main()
