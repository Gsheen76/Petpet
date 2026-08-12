import json
import os
import tempfile
import unittest
from unittest.mock import patch

import game_knowledge as knowledge
from version import VERSION


class GameKnowledgeTests(unittest.TestCase):
    def test_knowledge_file_is_current_and_player_facing(self):
        entries = knowledge.load_game_knowledge()

        self.assertEqual(knowledge.knowledge_version(), VERSION)
        self.assertGreaterEqual(len(entries), 6)
        self.assertTrue(all(
            entry["id"] and entry["title"] and entry["keywords"] and entry["content"]
            for entry in entries
        ))

    def test_game_questions_select_only_relevant_entries(self):
        matches = knowledge.find_relevant_entries("小屋里怎么装修家具？")

        self.assertEqual(matches[0]["id"], "home_and_decoration")
        self.assertLessEqual(len(matches), 3)
        self.assertEqual(knowledge.find_relevant_entries("今天有点累"), [])

    def test_current_knowledge_describes_v141_chat_and_preferences(self):
        combined = "\n".join(
            entry["content"] for entry in knowledge.load_game_knowledge()
        )

        self.assertIn("免费", combined)
        self.assertIn("GLM-4.6V-Flash", combined)
        self.assertIn("图片", combined)
        self.assertIn("文静", combined)
        self.assertIn("活泼", combined)
        self.assertNotIn("GLM-4.7", combined)

    def test_real_minigame_names_match_the_minigame_entry(self):
        for question in ("金币雨怎么玩？", "幸运爪爪在哪里？"):
            matches = knowledge.find_relevant_entries(question)
            self.assertTrue(matches)
            self.assertEqual(matches[0]["id"], "mini_games")

    def test_invalid_or_outdated_knowledge_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_path = os.path.join(temp_dir, "game_knowledge.json")
            with open(bad_path, "w", encoding="utf-8") as knowledge_file:
                json.dump({"version": "0.0.0", "entries": []}, knowledge_file)

            with patch.object(knowledge, "KNOWLEDGE_PATH", bad_path):
                self.assertEqual(knowledge.load_game_knowledge(), [])
                self.assertEqual(knowledge.find_relevant_entries("小屋"), [])


if __name__ == "__main__":
    unittest.main()
