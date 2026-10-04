import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.rag.answering import Answer, Claim, build_answer_graph, validate_answer
from app.rag.semantic import checked_vector


class FakeRetriever:
    def invoke(self, query):
        return [Document(page_content="Report suspicious transactions.", metadata={"title": "Policy", "locator": "Section 1"})]


class SemanticTests(unittest.TestCase):
    def test_missing_deepseek_key(self):
        with patch("app.rag.answering.load_dotenv"), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "", "OPENAI_API_KEY": "unrelated"}):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                build_answer_graph("deepseek", FakeRetriever())

    def test_deepseek_config_uses_own_key_and_json_mode(self):
        with patch("app.rag.answering.load_dotenv"), patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only", "DEEPSEEK_MODEL": "test-model"}), patch("langchain_openai.ChatOpenAI") as chat:
            build_answer_graph("deepseek", FakeRetriever())
            self.assertEqual(chat.call_args.kwargs["api_key"], "test-only")
            self.assertEqual(chat.call_args.kwargs["base_url"], "https://api.deepseek.com")
            self.assertEqual(chat.call_args.kwargs["model"], "test-model")
            chat.return_value.with_structured_output.assert_called_once_with(Answer, method="json_mode")

    def test_invalid_vectors(self):
        for vector in ([1], [0] * 384, [float("nan")] * 384):
            with self.assertRaises(ValueError):
                checked_vector(vector)

    def test_fabricated_citation(self):
        with self.assertRaises(ValueError):
            validate_answer(Answer(claims=[Claim(text="Claim", citations=[2])], insufficient_evidence=False), [object()])

    def test_no_evidence(self):
        with self.assertRaises(ValueError):
            validate_answer(Answer(claims=[Claim(text="Claim", citations=[1])], insufficient_evidence=False), [])

    def test_evidence_graph(self):
        result = build_answer_graph(retriever=FakeRetriever()).invoke({"question": "STR?"})
        self.assertEqual(result["answer"].claims[0].citations, [1])
        self.assertEqual(result["mode"], "evidence")

    def test_injected_generator(self):
        class FakeGenerator:
            def invoke(self, messages):
                return Answer(claims=[Claim(text="Supported answer", citations=[1])], insufficient_evidence=False)
        result = build_answer_graph("openai", FakeRetriever(), FakeGenerator()).invoke({"question": "STR?"})
        self.assertEqual(result["answer"].claims[0].text, "Supported answer")
