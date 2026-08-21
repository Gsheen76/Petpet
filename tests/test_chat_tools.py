import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QFontMetrics, QImage, qRgb
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QLabel, QMessageBox,
)

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

    def say(self, _text, _duration):
        pass


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
        self.data_path_patch = patch.object(ai, "DATA_DIR", self.temp_dir.name)
        self.data_path_patch.start()
        self.memory_path_patch = patch.object(
            ai, "MEMORY_PATH", os.path.join(self.temp_dir.name, "memory.json")
        )
        self.memory_path_patch.start()
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        os.environ.pop("ZHIPU_API_KEY", None)
        self.window = pet.ChatWindow(FakePet())

    def tearDown(self):
        self.window.close()
        self.path_patch.stop()
        self.data_path_patch.stop()
        self.memory_path_patch.stop()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_bottom_row_uses_two_rounded_chat_mode_segments(self):
        tools = self.window.findChild(QFrame, "chatTools")

        self.assertIsNotNone(tools)
        self.assertEqual(self.window.free_mode_btn.text(), "免费")
        self.assertEqual(self.window.personal_mode_btn.text(), "自定义")
        self.assertTrue(self.window.free_mode_btn.isCheckable())
        self.assertTrue(self.window.personal_mode_btn.isCheckable())
        self.assertTrue(self.window.free_mode_btn.isChecked())
        self.assertFalse(self.window.personal_mode_btn.isChecked())
        self.assertFalse(hasattr(self.window, "api_key_btn"))
        self.assertEqual(self.window.settings_btn.objectName(), "roundTool")
        self.assertEqual(self.window.clear_btn.objectName(), "clearTool")
        self.assertEqual(self.window.image_btn.text(), "上传")
        self.assertEqual(self.window.clear_btn.text(), "DEL")
        self.assertGreaterEqual(self.window.clear_btn.minimumWidth(), 42)
        self.window.show()
        QApplication.processEvents()
        self.assertGreaterEqual(self.window.clear_btn.width(), 42)

    def test_chat_window_uses_translucent_top_level_and_rounded_card(self):
        self.assertTrue(self.window.testAttribute(Qt.WA_TranslucentBackground))
        card = self.window.findChild(QFrame, "chatCard")

        self.assertIsNotNone(card)
        self.assertIn("QFrame#chatCard", self.window.styleSheet())
        self.assertIn("border-radius:24px", self.window.styleSheet())

    def test_chat_window_render_has_transparent_outer_corners(self):
        self.window.show()
        QApplication.processEvents()

        image = self.window.grab().toImage().convertToFormat(QImage.Format_ARGB32)

        for point in ((0, 0), (image.width() - 1, 0),
                      (0, image.height() - 1),
                      (image.width() - 1, image.height() - 1)):
            self.assertEqual(image.pixelColor(*point).alpha(), 0)

    def test_free_mode_hides_personal_chat_tools(self):
        ai.set_chat_mode("default")
        self.window._refresh_ai_tool_buttons()

        self.assertTrue(self.window.model_btn.isHidden())
        self.assertTrue(self.window.settings_btn.isHidden())
        self.assertTrue(self.window.image_btn.isHidden())

    def test_mode_segments_keep_identical_geometry_when_selection_changes(self):
        self.window.show()
        QApplication.processEvents()
        before = (
            self.window.mode_frame.size(),
            self.window.free_mode_btn.geometry(),
            self.window.personal_mode_btn.geometry(),
            self.window.free_mode_btn.font().weight(),
            self.window.personal_mode_btn.font().weight(),
        )

        ai.set_api_key("id.secret")
        self.window.select_chat_mode("personal")
        QApplication.processEvents()
        after = (
            self.window.mode_frame.size(),
            self.window.free_mode_btn.geometry(),
            self.window.personal_mode_btn.geometry(),
            self.window.free_mode_btn.font().weight(),
            self.window.personal_mode_btn.font().weight(),
        )

        self.assertEqual(before, after)
        self.assertIn("background:#f8dcd7", self.window.styleSheet().lower())

    def test_mode_segments_fit_the_longer_label_without_overlap(self):
        for button in (self.window.free_mode_btn, self.window.personal_mode_btn):
            text_width = QFontMetrics(button.font()).horizontalAdvance(button.text())
            self.assertGreaterEqual(button.width(), text_width + 28)
            self.assertGreater(button.font().pixelSize(), 0)
            self.assertEqual(button.font().pointSize(), -1)

    def test_chat_controls_share_crisp_pixel_typography_and_height(self):
        self.window.show()
        QApplication.processEvents()
        controls = (
            self.window.free_mode_btn,
            self.window.personal_mode_btn,
            self.window.model_btn,
            self.window.image_btn,
            self.window.settings_btn,
            self.window.clear_btn,
        )
        for control in controls:
            self.assertGreater(control.font().pixelSize(), 0)
            self.assertEqual(control.font().pointSize(), -1)
            self.assertEqual(control.minimumHeight(), 40)

    def test_personal_reminder_dot_clears_as_soon_as_editor_is_opened(self):
        self.assertTrue(self.window.personal_setup_dot.isVisibleTo(
            self.window.personal_mode_btn
        ))
        with patch.object(self.window, "_build_api_key_dialog") as build:
            build.return_value.exec_.return_value = QDialog.Rejected
            self.window.configure_api_key(activate_personal=True)

        self.assertFalse(ai.needs_personal_setup_reminder())
        self.assertTrue(self.window.personal_setup_dot.isHidden())

    def test_personal_mode_shows_model_and_settings_tools(self):
        ai.set_api_key("id.secret")
        ai.set_chat_mode("personal")
        self.window._refresh_ai_tool_buttons()

        self.assertFalse(self.window.model_btn.isHidden())
        self.assertEqual(self.window.model_btn.text(), "GLM-4.6V")
        self.assertFalse(self.window.settings_btn.isHidden())
        self.assertFalse(self.window.image_btn.isHidden())
        self.assertFalse(self.window.free_mode_btn.isChecked())
        self.assertTrue(self.window.personal_mode_btn.isChecked())

    def test_selecting_personal_with_saved_key_switches_without_dialog(self):
        ai.set_api_key("id.secret")
        ai.set_chat_mode("default")

        with patch.object(self.window, "configure_api_key") as configure:
            self.window.select_chat_mode("personal")

        configure.assert_not_called()
        self.assertEqual(ai.get_chat_mode(), "personal")
        self.assertTrue(self.window.personal_mode_btn.isChecked())

    def test_chat_surface_uses_warm_layered_palette(self):
        style = self.window.styleSheet()
        self.assertIn("background:#faf7f3", style)
        self.assertIn("background:#fffdfa", style)
        self.assertIn("QWidget#chat", style)
        self.assertIn("border-radius:24px", style)
        self.assertIn("QFrame#chatModeSegments", style)
        self.assertIn("QPushButton#chatModeSegment:checked", style)
        self.assertIn("QPushButton#roundTool", style)
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
        self.assertIn("border-radius:18px", assistant.styleSheet())
        self.assertIn("background:#f5e9df", assistant.styleSheet())
        self.assertIn("background:#fbf1ec", user.styleSheet())
        self.assertEqual(user.property("messageRole"), "user")

    def test_busy_chat_disables_mode_switching_until_request_finishes(self):
        progression.ensure_progression(self.window.pet.state)
        ai.set_default_chat_consent(True)
        self.window.input.setText("你好")

        with patch("pet.threading.Thread"), patch("pet.save_state"):
            self.window.send()

        self.assertFalse(self.window.free_mode_btn.isEnabled())
        self.assertFalse(self.window.personal_mode_btn.isEnabled())

        self.window.on_error("default_provider_unavailable")

        self.assertTrue(self.window.free_mode_btn.isEnabled())
        self.assertTrue(self.window.personal_mode_btn.isEnabled())

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
        ai.set_chat_mode("personal")
        self.window.select_model("glm-4.6v-flash")
        self.window._refresh_ai_tool_buttons()

        self.assertTrue(self.window.personal_mode_btn.isChecked())
        self.assertEqual(self.window.model_btn.text(), "GLM-4.6V")
        self.assertEqual(ai.get_model(), "glm-4.6v-flash")

    def test_free_mode_keeps_saved_key_but_hides_image_tool(self):
        ai.set_api_key("id.secret")
        ai.set_chat_mode("default")
        self.window._refresh_ai_tool_buttons()

        self.assertTrue(self.window.free_mode_btn.isChecked())
        self.assertEqual(ai.get_api_key(), "id.secret")
        self.assertTrue(self.window.image_btn.isHidden())

    def test_image_tool_only_appears_for_visual_model(self):
        ai.set_chat_mode("default")

        self.assertTrue(self.window.image_btn.isHidden())

        ai.set_api_key("id.secret")
        ai.set_chat_mode("personal")
        self.window.select_model("glm-4.6v-flash")

        self.assertFalse(self.window.image_btn.isHidden())

    def test_selected_image_is_previewed_and_saved_with_user_message(self):
        progression.ensure_progression(self.window.pet.state)
        attachment = {
            "base64_data": "aGk=",
            "filename": "dog.png",
            "history_image": {
                "thumbnail": "chat_images/dog.png",
                "filename": "dog.png",
            },
        }
        self.window.select_model("glm-4.6v-flash")
        self.window._set_pending_image(attachment)
        self.window._pending_user = "我发送了一张图片：dog.png"

        self.assertFalse(self.window.image_preview.isHidden())
        with patch("pet.save_state"):
            self.window.on_done("汪，我看到啦！")

        self.assertEqual(
            self.window.mem["history"][-2]["image"]["filename"], "dog.png"
        )
        self.assertFalse(any(
            key == "base64_data"
            for key in self.window.mem["history"][-2]
        ))

    def test_removing_unsent_image_deletes_its_history_thumbnail(self):
        thumbnail_dir = os.path.join(self.temp_dir.name, "chat_images")
        os.makedirs(thumbnail_dir)
        thumbnail_path = os.path.join(thumbnail_dir, "pending.png")
        image = QImage(2, 2, QImage.Format_ARGB32)
        image.fill(qRgb(255, 210, 160))
        self.assertTrue(image.save(thumbnail_path, "PNG"))

        self.window.select_model("glm-4.6v-flash")
        self.window._set_pending_image({
            "base64_data": "aGk=",
            "filename": "pending.png",
            "history_image": {
                "thumbnail": "chat_images/pending.png",
                "filename": "pending.png",
            },
        })
        self.window.clear_pending_image()

        self.assertFalse(os.path.exists(thumbnail_path))
        self.assertTrue(self.window.image_preview.isHidden())

    def test_history_user_message_renders_persisted_image_thumbnail(self):
        thumbnail_dir = os.path.join(self.temp_dir.name, "chat_images")
        os.makedirs(thumbnail_dir)
        thumbnail_path = os.path.join(thumbnail_dir, "history.png")
        image = QImage(4, 2, QImage.Format_ARGB32)
        image.fill(qRgb(255, 210, 160))
        self.assertTrue(image.save(thumbnail_path, "PNG"))
        self.window.mem["history"] = [{
            "role": "user",
            "content": "今天看到这个啦",
            "image": {
                "thumbnail": "chat_images/history.png",
                "filename": "history.png",
            },
        }]

        self.window._set_log_messages(self.window._history_messages())

        thumbnails = self.window.findChildren(QLabel, "chatImage")
        self.assertEqual(len(thumbnails), 1)
        self.assertFalse(thumbnails[0].pixmap().isNull())

    def test_only_successful_reply_adds_chat_affection(self):
        progression.ensure_progression(self.window.pet.state)
        ai.set_default_chat_consent(True)
        self.window.input.setText("今天过得怎么样？")

        with patch("pet.threading.Thread") as thread_cls, \
                patch("pet.save_state"):
            self.window.send()

        self.assertEqual(
            self.window.pet.state["records"]["chats_opened"], 1
        )
        self.assertEqual(
            self.window.pet.state["affection_points"], 0
        )
        thread_cls.return_value.start.assert_called_once_with()

        with patch("pet.save_state"):
            self.window.on_done("今天也过得很好呀！")

        self.assertEqual(
            self.window.pet.state["records"]["ai_replies"], 1
        )
        self.assertEqual(
            self.window.pet.state["affection_points"], 1
        )

    def test_streaming_token_updates_last_bubble_without_rebuilding_history(self):
        self.window._pending_user = "hello"
        self.window._streaming = ""
        self.window._set_log_messages([
            ("user", "hello", None),
            ("assistant", "鈥?", None),
        ])
        pending_bubble = self.window._last_assistant_bubble

        with patch.object(
                self.window, "_set_log_messages",
                wraps=self.window._set_log_messages) as rebuild:
            self.window.on_token("world")

        rebuild.assert_not_called()
        self.assertIs(self.window._last_assistant_bubble, pending_bubble)
        self.assertIn("world", pending_bubble.text())

    def test_first_free_chat_decline_does_not_send_or_record_progress(self):
        progression.ensure_progression(self.window.pet.state)
        self.window.input.setText("你好")

        with patch.object(
                QMessageBox, "question", return_value=QMessageBox.No
        ), patch("pet.threading.Thread") as thread_cls, patch("pet.save_state"):
            self.window.send()

        thread_cls.assert_not_called()
        self.assertFalse(ai.has_default_chat_consent())
        self.assertEqual(
            self.window.pet.state["records"]["chats_opened"], 0
        )

    def test_first_free_chat_acceptance_is_saved_before_sending(self):
        progression.ensure_progression(self.window.pet.state)
        self.window.input.setText("你好")

        with patch.object(
                QMessageBox, "question", return_value=QMessageBox.Yes
        ), patch("pet.threading.Thread") as thread_cls, patch("pet.save_state"):
            self.window.send()

        self.assertTrue(ai.has_default_chat_consent())
        thread_cls.return_value.start.assert_called_once_with()

    def test_ai_thread_forwards_default_quota_error_without_pet_fallback(self):
        error_signal = Mock()
        fake_bridge = SimpleNamespace(
            token=SimpleNamespace(emit=Mock()),
            done=SimpleNamespace(emit=Mock()),
            error=SimpleNamespace(emit=error_signal),
        )

        with patch.object(pet, "bridge", fake_bridge), patch.object(
                ai, "chat_stream",
                return_value=iter([("error", "default_quota_exhausted")]),
        ), patch.object(ai, "fallback_reply") as fallback:
            self.window._ai_thread("你好")

        error_signal.assert_called_once_with("default_quota_exhausted")
        fallback.assert_not_called()

    def test_ai_thread_emits_each_default_stream_token_once(self):
        token_signal = Mock()
        done_signal = Mock()
        fake_bridge = SimpleNamespace(
            token=SimpleNamespace(emit=token_signal),
            done=SimpleNamespace(emit=done_signal),
            error=SimpleNamespace(emit=Mock()),
        )

        with patch.object(pet, "bridge", fake_bridge), patch.object(
                ai, "chat_stream",
                return_value=iter([
                    ("token", "你"),
                    ("token", "好"),
                    ("done", "你好"),
                ]),
        ):
            self.window._ai_thread("你好")

        self.assertEqual(token_signal.call_args_list, [
            call("你"),
            call("好"),
        ])
        done_signal.assert_called_once_with("你好")

    def test_quota_error_unlocks_chat_and_shows_neutral_notice(self):
        self.window.busy = True
        self.window.send_btn.setEnabled(False)
        self.window._pending_user = "你好"

        self.window.on_error("default_quota_exhausted")

        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.send_btn.isEnabled())
        self.assertIsNone(self.window._pending_user)
        self.assertFalse(self.window.chat_notice.isHidden())
        self.assertEqual(
            self.window.chat_notice.text(),
            "今日免费次数已用完，可切换自定义。",
        )
        self.assertEqual(self.window.mem["history"], [])

    def test_provider_error_uses_one_short_player_facing_sentence(self):
        self.window.busy = True
        self.window.send_btn.setEnabled(False)
        self.window._pending_user = "你好"

        self.window.on_error("default_provider_unavailable")

        self.assertEqual(
            self.window.chat_notice.text(),
            "免费聊天暂不可用，请稍后再试。",
        )

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

    def test_assistant_bubble_uses_clean_text_without_dog_emoji(self):
        self.window._set_log_messages([("assistant", "你好（摇尾巴）")])

        bubble = self.window.findChild(QLabel, "chatMessage")

        self.assertEqual(bubble.text(), "你好")

    def test_chat_title_uses_only_pet_name(self):
        self.assertEqual(self.window.title.text().strip(), "summer")

    def test_title_bar_has_player_avatar_editor(self):
        self.assertEqual(self.window.avatar_btn.text(), "头像")
        self.assertEqual(self.window.avatar_btn.toolTip(), "编辑我的头像")

    def test_message_rows_show_desktop_pet_left_and_player_right_avatars(self):
        self.window._set_log_messages([
            ("assistant", "你好"),
            ("user", "你好呀"),
        ])
        self.window.show()
        QApplication.processEvents()

        avatars = self.window.findChildren(QLabel, "chatAvatar")
        self.assertEqual(len(avatars), 2)
        by_role = {avatar.property("avatarRole"): avatar for avatar in avatars}
        self.assertEqual(set(by_role), {"assistant", "user"})
        self.assertTrue(
            by_role["assistant"].property("avatarSource").endswith(
                os.path.join(
                    "assets",
                    "runtime",
                    "pets",
                    "lunch_meat",
                    "desktop",
                    "poses",
                    "idle.png",
                )
            )
        )
        self.assertEqual(by_role["user"].property("avatarSource"), "default")
        self.assertLess(
            by_role["assistant"].geometry().left(),
            self.window.findChildren(QLabel, "chatMessage")[0].geometry().left(),
        )

    def test_custom_player_avatar_is_used_for_user_messages(self):
        avatar_path = ai.get_player_avatar_path()
        image = QImage(8, 8, QImage.Format_ARGB32)
        image.fill(qRgb(90, 150, 210))
        self.assertTrue(image.save(avatar_path, "PNG"))

        self.window._set_log_messages([("user", "你好呀")])

        avatar = self.window.findChild(QLabel, "chatAvatar")
        self.assertEqual(avatar.property("avatarRole"), "user")
        self.assertEqual(avatar.property("avatarSource"), avatar_path)

    def test_cancel_player_avatar_selection_keeps_existing_avatar(self):
        avatar_path = ai.get_player_avatar_path()
        image = QImage(8, 8, QImage.Format_ARGB32)
        image.fill(qRgb(90, 150, 210))
        self.assertTrue(image.save(avatar_path, "PNG"))

        with patch.object(
                pet.QFileDialog, "getOpenFileName", return_value=("", "")
        ):
            self.window.select_player_avatar()

        self.assertTrue(os.path.isfile(avatar_path))

    def test_select_player_avatar_saves_and_refreshes_message_rows(self):
        source_path = os.path.join(self.temp_dir.name, "portrait.png")
        image = QImage(12, 8, QImage.Format_ARGB32)
        image.fill(qRgb(90, 150, 210))
        self.assertTrue(image.save(source_path, "PNG"))
        self.window._set_log_messages([("user", "你好呀")])

        with patch.object(
                pet.QFileDialog, "getOpenFileName",
                return_value=(source_path, "图片文件 (*.png)"),
        ):
            self.window.select_player_avatar()

        avatar = self.window.findChild(QLabel, "chatAvatar")
        self.assertTrue(os.path.isfile(ai.get_player_avatar_path()))
        self.assertEqual(
            avatar.property("avatarSource"), ai.get_player_avatar_path()
        )

    def test_reset_player_avatar_restores_default_and_refreshes_rows(self):
        avatar_path = ai.get_player_avatar_path()
        image = QImage(8, 8, QImage.Format_ARGB32)
        image.fill(qRgb(90, 150, 210))
        self.assertTrue(image.save(avatar_path, "PNG"))
        self.window._set_log_messages([("user", "你好呀")])

        self.window.reset_player_avatar()

        avatar = self.window.findChild(QLabel, "chatAvatar")
        self.assertFalse(os.path.exists(avatar_path))
        self.assertEqual(avatar.property("avatarSource"), "default")

    def test_avatar_actions_use_warm_popup_instead_of_system_menu(self):
        with patch.object(pet, "PetpetPopupMenu") as popup_cls, patch.object(
                pet, "QMenu"
        ) as system_menu:
            popup = popup_cls.return_value
            self.window.show_player_avatar_menu()

        popup_cls.assert_called_once_with(self.window)
        self.assertEqual(
            [item.args[0] for item in popup.add_action.call_args_list],
            ["选择头像", "恢复默认"],
        )
        popup.popup_below.assert_called_once_with(self.window.avatar_btn)
        system_menu.assert_not_called()

    def test_warm_popup_renders_an_opaque_rounded_card(self):
        popup = pet.PetpetPopupMenu(self.window)
        popup.add_action("选择头像", lambda: None)
        popup.add_action("恢复默认", lambda: None)
        popup.popup_below(self.window.avatar_btn)
        QApplication.processEvents()

        image = popup.grab().toImage().convertToFormat(QImage.Format_ARGB32)

        self.assertGreater(image.pixelColor(
            image.width() // 2, image.height() // 2
        ).alpha(), 0)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        popup.close()

    def test_clear_memory_uses_warm_confirmation_dialog(self):
        with patch.object(pet, "PetpetConfirmDialog") as dialog_cls, patch.object(
                pet, "QMessageBox"
        ) as system_message:
            dialog_cls.return_value.exec_.return_value = QDialog.Rejected
            self.window.confirm_clear_memory()

        dialog_cls.assert_called_once()
        kwargs = dialog_cls.call_args.kwargs
        self.assertEqual(kwargs["title"], "清除记忆")
        self.assertEqual(kwargs["accept_text"], "重新相识")
        self.assertEqual(kwargs["reject_text"], "继续陪着我")
        system_message.assert_not_called()

    def test_warm_dialog_and_popup_use_the_same_crisp_control_scale(self):
        dialog = pet.PetpetConfirmDialog(
            self.window,
            title="清除记忆",
            message="主人，我会忘记你的。",
            accept_text="重新相识",
            reject_text="继续陪着我",
        )
        popup = pet.PetpetPopupMenu(self.window)
        action = popup.add_action("选择头像", lambda: None)

        title = dialog.findChild(QLabel, "petpetDialogTitle")
        body = dialog.findChild(QLabel, "petpetDialogMessage")
        self.assertEqual(title.font().pixelSize(), 21)
        self.assertEqual(body.font().pixelSize(), 18)
        self.assertEqual(dialog.accept_btn.font().pixelSize(), 17)
        self.assertEqual(dialog.accept_btn.minimumHeight(), 40)
        self.assertEqual(action.font().pixelSize(), 17)
        self.assertEqual(action.minimumHeight(), 40)
        popup.close()
        dialog.close()

    def test_api_editor_is_frameless_rounded_card_with_static_single_model(self):
        dialog = self.window._build_api_key_dialog()

        self.assertTrue(dialog.windowFlags() & Qt.FramelessWindowHint)
        self.assertTrue(dialog.testAttribute(Qt.WA_TranslucentBackground))
        self.assertIsNotNone(dialog.findChild(QFrame, "apiKeyCard"))
        self.assertIsNone(dialog.findChild(QComboBox))
        model_card = dialog.findChild(QLabel, "apiModelCard")
        self.assertIsNotNone(model_card)
        self.assertEqual(model_card.text(), "GLM-4.6V-Flash")
        self.assertIn("background:#fff1cc", dialog.styleSheet().lower())


if __name__ == "__main__":
    unittest.main()
