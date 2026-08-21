import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLabel

import buddy_ai as ai
import pet


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = {
            "active_pet_id": "lunch_meat",
            "pet_name": "豆包",
            "pets": {
                "lunch_meat": {"pet_name": "豆包"},
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
        self.desktop_patch = patch.object(ai, "MEMORY_PATH", self.desktop_path)
        self.desktop_patch.start()
        self.data_path_patch = patch.object(ai, "DATA_DIR", self.temp_dir.name)
        self.data_path_patch.start()
        self.home_patch = None
        ai.save_memory(
            {**ai._default_memory(), "pet_name": "豆包", "history": []},
            pet_id="lunch_meat",
        )
        self.window = None

    def tearDown(self):
        if self.window is not None:
            self.window.close()
        if self.home_patch is not None:
            self.home_patch.stop()
        self.data_path_patch.stop()
        self.desktop_patch.stop()
        self.temp_dir.cleanup()

    def test_chat_window_profile_aliases_share_lunch_meat_memory(self):
        self.window = pet.ChatWindow(FakePet(), memory_profile="home")

        self.assertEqual(self.window.memory_profile, "lunch_meat")
        self.assertEqual(self.window.pet_id, "lunch_meat")
        self.assertEqual(self.window._pet_name(), "豆包")
        self.assertEqual(self.window.mem["pet_name"], "豆包")

        self.window.set_memory_profile("desktop")

        self.assertEqual(self.window.memory_profile, "lunch_meat")
        self.assertEqual(self.window.pet_id, "lunch_meat")
        self.assertEqual(self.window._pet_name(), "豆包")
        self.assertEqual(self.window.mem["pet_name"], "豆包")

    def test_chat_profile_alias_ignores_home_scene_visibility(self):
        visible_home = SimpleNamespace(isVisible=lambda: True)
        hidden_home = SimpleNamespace(isVisible=lambda: False)

        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=visible_home)
            ),
            "lunch_meat",
        )
        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=hidden_home)
            ),
            "lunch_meat",
        )
        self.assertEqual(
            pet.PetWindow.active_chat_profile(
                SimpleNamespace(home_scene_window=None)
            ),
            "lunch_meat",
        )

    def test_busy_chat_rejects_pet_switch_and_saves_inflight_reply_to_original_pet(self):
        self.window = pet.ChatWindow(FakePet(), pet_id="lunch_meat")
        self.window.busy = True
        self.window._pending_user = "来自午餐肉"

        self.assertFalse(self.window.set_pet_id("ice_cream"))
        self.assertEqual(self.window.pet_id, "lunch_meat")

        self.window.on_done("午餐肉的回复")

        lunch_history = ai.load_memory(pet_id="lunch_meat")["history"]
        ice_history = ai.load_memory(pet_id="ice_cream")["history"]
        self.assertEqual(
            [entry["content"] for entry in lunch_history],
            ["来自午餐肉", "午餐肉的回复"],
        )
        self.assertEqual(ice_history, [])

    def test_ice_cream_identity_updates_title_and_existing_assistant_avatar(self):
        self.window = pet.ChatWindow(FakePet(), pet_id="ice_cream")
        self.window.pet.state["pet_name"] = "冰淇淋"
        self.window.refresh_pet_name()
        self.assertEqual(self.window.title.text().strip(), "冰淇淋")

        self.window.pet.state["pet_name"] = "奶油"
        self.window.refresh_pet_name()
        self.assertEqual(self.window.title.text().strip(), "奶油（冰淇淋）")

        ai.save_memory(
            {**ai._default_memory(), "pet_name": "奶油", "history": [
                {"role": "assistant", "content": "你好"},
            ]},
            pet_id="ice_cream",
        )
        self.window.set_pet_id("ice_cream")

        avatar = self.window.findChild(QLabel, "chatAvatar")
        self.assertEqual(avatar.property("avatarRole"), "assistant")
        self.assertTrue(avatar.property("avatarSource").endswith(
            os.path.join(
                "assets", "runtime", "pets", "ice_cream", "desktop",
                "poses", "idle.png",
            )
        ))


if __name__ == "__main__":
    unittest.main()
