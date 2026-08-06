import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QFrame, QLabel

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
        self.assertIn("未配置", self.window.api_key_btn.text())
        self.assertIn("GLM-4-Flash", self.window.model_btn.text())
        self.assertEqual(self.window.clear_btn.objectName(), "clearTool")
        self.assertIn("清除记忆", self.window.clear_btn.text())

    def test_missing_key_uses_unconfigured_text_and_badge(self):
        self.window._refresh_ai_tool_buttons()

        self.assertIn("未配置", self.window.api_key_btn.text())
        self.assertFalse(self.window.api_key_badge.isHidden())

    def test_chat_surface_uses_warm_layered_palette(self):
        style = self.window.styleSheet()
        self.assertIn("background:#faf7f3", style)
        self.assertIn("background:#fffdfa", style)
        self.assertIn("QScrollBar::handle:vertical", style)
        self.window._set_log_messages([
            ("assistant", "你好"),
            ("user", "你好呀"),
        ])
        bubbles = [
            bubble
            for bubble in self.window.findChildren(QLabel, "chatMessage")
            if bubble.property("messageRole") in ("assistant", "user")
        ]
        self.assertEqual(len(bubbles), 2)
        assistant, user = bubbles
        self.assertEqual(assistant.property("messageRole"), "assistant")
        self.assertIn("border-radius:14px", assistant.styleSheet())
        self.assertIn("background:#f5e9df", assistant.styleSheet())
        self.assertIn("background:#fbf1ec", user.styleSheet())
        self.assertEqual(user.property("messageRole"), "user")

    def test_message_fonts_track_chat_font_setting(self):
        self.window.pet.settings["chat_font_size"] = 24
        self.window.s = self.window.pet.settings
        self.window._apply_style()
        self.window._set_log_messages([
            ("assistant", "测试消息"),
            ("user", "测试消息"),
        ])

        bubbles = self.window.findChildren(QLabel, "chatMessage")
        self.assertEqual(len(bubbles), 2)
        self.assertTrue(all(
            "font-size:24px" in bubble.styleSheet() for bubble in bubbles
        ))

    def test_saved_key_and_model_update_toolbar_status(self):
        ai.set_api_key("id.secret")
        self.window.select_model("glm-4-flash")
        self.window._refresh_ai_tool_buttons()

        self.assertIn("已配置", self.window.api_key_btn.text())
        self.assertEqual(ai.get_model(), "glm-4-flash")
        self.assertTrue(self.window.api_key_badge.isHidden())

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

    def test_long_chat_content_finishes_at_the_bottom(self):
        self.window.show()
        long_reply = "\n\n".join(
            f"第 {index} 段：" + "这是较长的回复内容。" * 12
            for index in range(30)
        )

        self.window._set_log_messages([("assistant", long_reply)])
        QApplication.processEvents()
        self.window._scroll_log_to_bottom()

        scrollbar = self.window.log.verticalScrollBar()
        self.assertEqual(scrollbar.value(), scrollbar.maximum())


if __name__ == "__main__":
    unittest.main()
