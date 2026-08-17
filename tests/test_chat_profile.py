import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import buddy_ai as ai
import pet


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = {
            "pet_name": "桌桌",
            "pets": {
                "desktop": {"pet_name": "桌桌"},
                "home": {"pet_name": "豆包"},
            },
        }

    @property
    def pet_name(self):
        return self.state["pet_name"]

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()

    def say(self, _text, _duration):
        pass


class ChatProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.desktop_path = os.path.join(self.temp_dir.name, "memory.json")
        self.home_path = os.path.join(self.temp_dir.name, "memory-home.json")
        self.desktop_patch = patch.object(ai, "MEMORY_PATH", self.desktop_path)
        self.home_patch = patch.object(ai, "HOME_MEMORY_PATH", self.home_path)
        self.desktop_patch.start()
        self.home_patch.start()
        ai.save_memory(
            {**ai._default_memory(), "pet_name": "桌桌", "history": []},
            profile="desktop",
        )
        ai.save_memory(
            {**ai._default_memory(), "pet_name": "豆包", "history": []},
            profile="home",
        )
        self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.close()
        self.home_patch.stop()
        self.desktop_patch.stop()
        self.temp_dir.cleanup()

    def test_chat_window_switches_memory_and_name_with_profile(self):
        self.window = pet.ChatWindow(FakePet(), memory_profile="home")

        self.assertEqual(self.window.memory_profile, "home")
        self.assertEqual(self.window._pet_name(), "豆包")
        self.assertEqual(self.window.mem["pet_name"], "豆包")

        self.window.set_memory_profile("desktop")

        self.assertEqual(self.window.memory_profile, "desktop")
        self.assertEqual(self.window._pet_name(), "桌桌")
        self.assertEqual(self.window.mem["pet_name"], "桌桌")

    def test_home_scene_visibility_selects_home_chat_profile(self):
        visible_home = SimpleNamespace(isVisible=lambda: True)
        hidden_home = SimpleNamespace(isVisible=lambda: False)

        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=visible_home)
            ),
            "home",
        )
        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=hidden_home)
            ),
            "desktop",
        )
        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=None)
            ),
            "desktop",
        )


if __name__ == "__main__":
    unittest.main()
