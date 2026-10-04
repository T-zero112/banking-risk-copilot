import unittest
from unittest.mock import patch

from app.rag.retrieval import PolicyRetriever, search_policy


class PolicyRetrievalTests(unittest.TestCase):
    def test_invalid_queries_do_not_open_a_database_connection(self):
        with patch("app.rag.retrieval.connect") as connect:
            for query, top_k in (("", 3), (" " * 5, 3), ("a" * 2001, 3),
                                 ("funds", 0), ("funds", 21), ("\u4ea4\u6613\u98ce\u9669", 3)):
                with self.subTest(query=query[:10], top_k=top_k), self.assertRaises(ValueError):
                    search_policy(query, top_k)
            connect.assert_not_called()

    def test_langchain_adapter_uses_configured_filter_and_limit(self):
        with patch("app.rag.retrieval.search_policy", return_value=[]) as search:
            result = PolicyRetriever(top_k=2, source_id="spf-bank-red-flags").invoke("funds")
            self.assertEqual(result, [])
            search.assert_called_once_with("funds", 2, "spf-bank-red-flags")


if __name__ == "__main__":
    unittest.main()
