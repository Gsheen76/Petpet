import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QFrame

import buddy_ai as ai
import pet
import progression


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.state = {"pet_name": "summer"}

    @property
    def pet_name(self):
        return self.state["pet_name"]

    def current_screen_rect(self):
        return QApplication.primaryScreen().availableGeometry()


class ChatToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(
            ai, "CONFIG_PATH",
            os.path.join(self.temp_dir.name, "config.json"),
        )
        self.path_patch.start()
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        os.environ.pop("ZHIPU_API_KEY", None)
        self.window = pet.ChatWindow(FakePet())

    def tearDown(self):
        self.window.close()
        self.path_patch.stop()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_bottom_row_is_an_extensible_interactive_toolbar(self):
        tools = self.window.findChild(QFrame, "chatTools")

        self.assertIsNotNone(tools)
        self.assertIn("添加 API Key", self.window.api_key_btn.text())
        self.assertIn("GLM-4-Flash", self.window.model_btn.text())
        self.assertEqual(self.window.clear_btn.objectName(), "clearTool")
        self.assertIn("清除记忆", self.window.clear_btn.text())

    def test_saved_key_and_model_update_toolbar_status(self):
        ai.set_api_key("id.secret")
        self.window.select_model("glm-4-flash")
        self.window._refresh_ai_tool_buttons()

        self.assertIn("已配置", self.window.api_key_btn.text())
        self.assertEqual(ai.get_model(), "glm-4-flash")

    def test_sending_a_real_message_adds_chat_affection(self):
        progression.ensure_progression(self.window.pet.state)
        self.window.input.setText("今天过得怎么样？")

        with patch("pet.threading.Thread") as thread_cls, \
                patch("pet.save_state"):
            self.window.send()

        self.assertEqual(
            self.window.pet.state["records"]["chats_opened"], 1
        )
        self.assertEqual(
            self.window.pet.state["affection_points"], 1
        )
        thread_cls.return_value.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
