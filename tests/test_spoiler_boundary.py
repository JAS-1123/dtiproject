import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.aiml import answer_question, available_chunks

DATA_DIR = Path(__file__).resolve().parents[1] / "backend" / "data"
BOOK = json.loads((DATA_DIR / "book.json").read_text(encoding="utf-8"))
PRIDE = json.loads((DATA_DIR / "pride_and_prejudice.json").read_text(encoding="utf-8"))


class LoreFlowQuestionTests(unittest.TestCase):
    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_future_gate_reveal_is_blocked_before_its_passage(self):
        result = answer_question("What lies beyond the north gate?", 52, BOOK)
        self.assertTrue(result["spoiler_blocked"])
        self.assertFalse(result["can_answer"])
        self.assertEqual(result["sources"], [])
        self.assertIn("haven't heard yet", result["answer"])

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_gate_reveal_unlocks_after_source_passage(self):
        result = answer_question("What lies beyond the north gate?", 109, BOOK)
        self.assertFalse(result["spoiler_blocked"])
        self.assertTrue(result["can_answer"])
        self.assertIn("underground observatory", result["answer"])
        self.assertEqual(result["sources"][0]["id"], "p5")

    def test_unheard_chunks_never_enter_heard_context(self):
        heard = available_chunks(BOOK["chunks"], 52)
        self.assertEqual([chunk["id"] for chunk in heard], ["p1", "p2"])
        self.assertTrue(all(chunk["end_sec"] <= 52 for chunk in heard))

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_any_free_form_question_can_retrieve_relevant_passage(self):
        result = answer_question("What was Ilya carrying?", 65.5, BOOK)
        self.assertTrue(result["can_answer"])
        self.assertIn("brass key", result["answer"])
        self.assertEqual(result["sources"][0]["id"], "p3")

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_character_question_works_without_a_preset_question_list(self):
        result = answer_question("Can you explain who the captain is?", 52, BOOK)
        self.assertTrue(result["can_answer"])
        self.assertIn("Captain Mira", result["answer"])

    @patch.dict(os.environ, {"XAI_API_KEY": "test-key"})
    @patch("backend.aiml.httpx.post")
    def test_grok_receives_only_heard_passages(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"output_text": "Captain Mira commands the western guard."}

        result = answer_question("Who is Captain Mira?", 52, BOOK)
        self.assertEqual(result["mode"], "Grok API + heard-passage retrieval")
        request_json = mock_post.call_args.kwargs["json"]
        prompt_text = "\n".join(item["content"] for item in request_json["input"])
        self.assertIn("Captain Mira", prompt_text)
        self.assertNotIn("underground observatory", prompt_text)
        self.assertNotIn("star compass", prompt_text)
        self.assertFalse(request_json["store"])

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_bingley_is_blocked_before_his_name_is_heard(self):
        result = answer_question("Who is Mr. Bingley?", 22.3, PRIDE)
        self.assertTrue(result["spoiler_blocked"])
        self.assertFalse(result["can_answer"])
        self.assertEqual(result["sources"], [])

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_bingley_can_be_explained_after_his_name_is_heard(self):
        result = answer_question("Who is Mr. Bingley?", 81.0, PRIDE)
        self.assertFalse(result["spoiler_blocked"])
        self.assertTrue(result["can_answer"])
        self.assertEqual(result["sources"][0]["id"], "pp3")
        self.assertIn("young man of large fortune", result["answer"])

    @patch.dict(os.environ, {"XAI_API_KEY": ""})
    def test_opening_claim_is_answerable_from_first_passage(self):
        result = answer_question("What does the opening suggest about a wealthy unmarried man?", 22.3, PRIDE)
        self.assertTrue(result["can_answer"])
        self.assertEqual(result["sources"][0]["id"], "pp1")

    @patch.dict(os.environ, {"XAI_API_KEY": "test-key"})
    @patch("backend.aiml.httpx.post")
    def test_grok_receives_only_heard_pride_and_prejudice_passages(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"output_text": "Bingley is the wealthy new tenant at Netherfield."}

        result = answer_question("Who is Bingley?", 81.0, PRIDE)
        self.assertEqual(result["mode"], "Grok API + heard-passage retrieval")
        request_json = mock_post.call_args.kwargs["json"]
        prompt_text = "\n".join(item["content"] for item in request_json["input"])
        self.assertIn("Bingley", prompt_text)
        self.assertIn("young man of large fortune", prompt_text)
        self.assertNotIn("five grown up daughters", prompt_text)
        self.assertFalse(request_json["store"])


if __name__ == "__main__":
    unittest.main()
