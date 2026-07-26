import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import buddy_ai as ai
import pet


class FakeTutorialPet:
    def __init__(self, completed=False, name="Sheen"):
        self.state = {
            "tutorial_completed": completed,
            "pet_name": name,
        }

    @property
    def pet_name(self):
        return ai.normalize_pet_name(self.state.get("pet_name"))

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()


class OnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_default_state_requires_tutorial_and_has_default_name(self):
        self.assertFalse(pet.DEFAULT_STATE["tutorial_completed"])
        self.assertEqual(pet.DEFAULT_STATE["pet_name"], "Sheen")

    def test_tutorial_font_is_independent_from_pet_surface_scale(self):
        self.assertEqual(pet.tutorial_font_px(30), 30)
        self.assertEqual(pet.font_px(30), 60)

    def test_tutorial_no_longer_mentions_right_long_press(self):
        tutorial_copy = "\n".join(
            text
            for page in pet.TutorialWindow.PAGES
            for text in page
        )
        self.assertNotIn("长按右键", tutorial_copy)

    def test_pet_name_normalization(self):
        self.assertEqual(ai.normalize_pet_name("  小 团子  "), "小 团子")
        self.assertEqual(ai.normalize_pet_name("团子\n坏指令!"), "团子 坏指令")
        self.assertEqual(ai.normalize_pet_name("!@#"), "Sheen")
        self.assertEqual(ai.normalize_pet_name("abcdefghijklmnop"), "abcdefghijkl")

    def test_ai_persona_uses_custom_pet_name(self):
        memory = ai._default_memory()
        messages = ai._build_messages(
            "你好", memory, pet_name="团子"
        )
        prompt = messages[0]["content"]
        self.assertIn("名叫 团子", prompt)
        self.assertNotIn("Sheen", prompt)
        self.assertIn(
            "团子",
            ai.fallback_reply("随便聊聊", "no_api_key", pet_name="团子"),
        )

    def test_tutorial_requires_name_and_completes_with_valid_name(self):
        completed = []
        window = pet.TutorialWindow(
            FakeTutorialPet(), completed.append
        )
        self.addCleanup(window.close)
        self.assertEqual((window.width(), window.height()), (800, 680))
        self.assertIn("QLabel#tutorialBody", window.styleSheet())
        self.assertIn("font-size:28px", window.styleSheet())
        window.page_index = len(window.PAGES) - 1
        window._refresh_page()
        window.name_input.setText("!!!")
        window._next()
        self.assertEqual(completed, [])
        self.assertTrue(window.name_hint.text())

        window.name_input.setText("团子")
        window._next()
        self.assertEqual(completed, ["团子"])

    def test_open_chat_memory_tracks_renamed_pet(self):
        fake_pet = FakeTutorialPet()
        fake_pet.settings = dict(pet.DEFAULT_SETTINGS)
        fake_pet.chat_win = pet.ChatWindow(fake_pet)
        self.addCleanup(fake_pet.chat_win.close)
        fake_pet.state["pet_name"] = "团子"

        fake_pet.chat_win.refresh_pet_name()

        self.assertEqual(fake_pet.chat_win.mem["pet_name"], "团子")
        self.assertIn("团子", fake_pet.chat_win.title.text())


if __name__ == "__main__":
    unittest.main()
