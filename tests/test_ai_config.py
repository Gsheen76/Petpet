import json
import os
import tempfile
import unittest
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

from PyQt5.QtGui import QImage, qRgb

import buddy_ai as ai


class FakeStreamResponse:
    def __init__(self):
        self._chunks = [
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
            b"data: [DONE]\n\n",
            b"",
        ]

    def read(self, _size):
        return self._chunks.pop(0)


class EmptyStreamResponse:
    def __init__(self):
        self._chunks = [b"data: [DONE]\n\n", b""]

    def read(self, _size):
        return self._chunks.pop(0)


class FakeLineStreamResponse:
    def __init__(self, lines):
        self._lines = iter(lines)

    def readline(self):
        return next(self._lines, b"")


class FakeRequestsStreamResponse:
    def __init__(self, lines, status_code=200, payload=None):
        self._lines = lines
        self.status_code = status_code
        self._payload = payload or {}

    def iter_lines(self):
        return iter(self._lines)

    def json(self):
        return self._payload

    def close(self):
        pass


class FakeJsonResponse:
    def read(self):
        return b'{"choices":[{"message":{"content":"likes dogs"}}]}'


class AiConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = os.path.join(
            self.temp_dir.name, "config.json"
        )
        self.path_patch = patch.object(ai, "CONFIG_PATH", self.config_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.data_path_patch = patch.object(ai, "DATA_DIR", self.temp_dir.name)
        self.data_path_patch.start()
        self.addCleanup(self.data_path_patch.stop)
        self.memory_path_patch = patch.object(
            ai, "MEMORY_PATH", os.path.join(self.temp_dir.name, "memory.json")
        )
        self.memory_path_patch.start()
        self.addCleanup(self.memory_path_patch.stop)
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        os.environ.pop("ZHIPU_API_KEY", None)
        self.image_path = os.path.join(self.temp_dir.name, "dog.png")
        image = QImage(2, 2, QImage.Format_ARGB32)
        image.fill(qRgb(255, 210, 160))
        self.assertTrue(image.save(self.image_path, "PNG"))

    def test_api_key_and_model_are_persisted_without_overwriting_each_other(self):
        ai.set_api_key("  id.secret  ")
        ai.set_chat_mode("personal")
        ai.set_model("glm-4.6v-flash")

        self.assertEqual(ai.get_api_key(), "id.secret")
        self.assertEqual(ai.get_model(), "glm-4.6v-flash")
        self.assertEqual(ai.get_api_key_source(), "config")
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
        self.assertEqual(saved["api_key"], "id.secret")
        self.assertEqual(saved["model"], "glm-4.6v-flash")

    def test_personal_setup_reminder_is_cleared_after_first_open_even_without_key(self):
        self.assertTrue(ai.needs_personal_setup_reminder())

        ai.mark_personal_setup_seen()

        self.assertFalse(ai.needs_personal_setup_reminder())
        self.assertEqual(ai.get_api_key(), "")
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
        self.assertTrue(saved["personal_setup_seen"])
        self.assertEqual(saved["api_key"], "")

    def test_invalid_or_bom_config_falls_back_safely(self):
        with open(self.config_path, "w", encoding="utf-8-sig") as config_file:
            json.dump(
                {"api_key": "saved.key", "model": "not-supported"},
                config_file,
            )

        self.assertEqual(ai.get_api_key(), "saved.key")
        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_environment_key_has_priority_without_being_exposed(self):
        ai.set_api_key("saved.key")
        os.environ["ZHIPU_API_KEY"] = "env.key"

        self.assertEqual(ai.get_api_key(), "env.key")
        self.assertEqual(ai.get_api_key_source(), "environment")

    def test_stream_request_uses_the_selected_model_value(self):
        memory = ai._default_memory()
        response = FakeStreamResponse()
        with patch(
            "buddy_ai.urllib.request.urlopen", return_value=response
        ) as urlopen:
            events = list(ai._stream_once(
                "hello", memory, "id.secret", None, 5,
                model="glm-4.7-flash",
            ))

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "glm-4.7-flash")
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(events[-1], ("done", "hi"))

    def test_legacy_model_is_migrated_to_new_text_model(self):
        with open(self.config_path, "w", encoding="utf-8") as config_file:
            json.dump({"model": "glm-4-flash"}, config_file)

        self.assertEqual(ai.get_model(), ai.FREE_MODEL)

    def test_visual_model_request_contains_image_and_text_content(self):
        response = FakeStreamResponse()
        attachment = {
            "base64_data": "aGk=",
            "filename": "dog.png",
        }
        with patch(
            "buddy_ai.urllib.request.urlopen", return_value=response
        ) as urlopen:
            list(ai._stream_once(
                "看看它", ai._default_memory(), "id.secret", None, 5,
                model="glm-4.6v-flash", image_attachment=attachment,
            ))

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["messages"][-1]["content"]
        self.assertEqual(body["model"], "glm-4.6v-flash")
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(
            content[0]["image_url"]["url"], attachment["base64_data"]
        )
        self.assertEqual(content[1], {"type": "text", "text": "看看它"})

    def test_text_model_request_keeps_user_content_as_text(self):
        response = FakeStreamResponse()
        with patch(
            "buddy_ai.urllib.request.urlopen", return_value=response
        ) as urlopen:
            list(ai._stream_once(
                "只聊天", ai._default_memory(), "id.secret", None, 5,
                model="glm-4.7-flash",
            ))

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["messages"][-1]["content"], "只聊天")

    def test_stream_ending_without_text_is_reported_as_empty_response(self):
        with patch(
            "buddy_ai.urllib.request.urlopen", return_value=EmptyStreamResponse()
        ):
            events = list(ai._stream_once(
                "你好", ai._default_memory(), "id.secret", None, 5,
                model="glm-4.7-flash",
            ))

        self.assertEqual(events, [("error", "empty_response")])

    def test_known_chat_errors_use_friendly_pet_replies(self):
        for error_code in ("rate_limit", "empty_response"):
            with self.subTest(error_code=error_code):
                reply = ai.fallback_reply(
                    "今天在写报告", err=error_code, pet_name="烟花"
                )

                self.assertNotIn(error_code, reply)
                self.assertIn("烟花", reply)

    def test_image_attachment_creates_history_thumbnail_without_base64(self):
        attachment = ai.prepare_image_attachment(self.image_path)
        memory = ai._default_memory()

        ai.append_history(
            memory, "user", "我拍到了", image=attachment["history_image"]
        )

        record = memory["history"][-1]
        self.assertNotIn("base64_data", record)
        self.assertEqual(record["image"]["filename"], "dog.png")
        self.assertTrue(os.path.exists(
            ai.resolve_history_image(record["image"]["thumbnail"])
        ))

    def test_image_attachment_rejects_unsupported_file(self):
        text_path = os.path.join(self.temp_dir.name, "not-an-image.txt")
        with open(text_path, "w", encoding="utf-8") as text_file:
            text_file.write("not an image")

        with self.assertRaisesRegex(ValueError, "图片"):
            ai.prepare_image_attachment(text_path)

    def test_reply_cleaner_removes_parenthetical_actions_but_keeps_dialogue(self):
        reply = ai.clean_assistant_reply(
            "我在呀（摇摇尾巴）！(凑近一点)你想聊什么？"
        )

        self.assertEqual(reply, "我在呀！你想聊什么？")

    def test_reply_cleaner_hides_an_incomplete_streamed_action(self):
        self.assertEqual(
            ai.clean_assistant_reply("我在呀（摇摇"), "我在呀"
        )

    def test_game_question_injects_matched_knowledge_only(self):
        entry = {
            "title": "小屋与家具",
            "content": "进入小屋后可以装修家具。",
        }
        with patch.object(
                ai.game_knowledge,
                "find_relevant_entries",
                return_value=[entry],
        ) as find_entries:
            system = ai._build_messages(
                "怎么装修家具", ai._default_memory()
            )[0]["content"]

        find_entries.assert_called_once_with("怎么装修家具")
        self.assertIn("# 游戏资料", system)
        self.assertIn("进入小屋后可以装修家具。", system)

    def test_no_key_requires_default_chat_consent(self):
        ai.set_default_chat_consent(False)
        self.assertEqual(
            list(ai.chat_stream("你好", ai._default_memory())),
            [("error", "default_consent_required")],
        )

    def test_legacy_text_model_without_key_migrates_to_free_chat(self):
        with open(self.config_path, "w", encoding="utf-8") as config_file:
            json.dump({"model": "glm-4.7-flash"}, config_file)

        self.assertEqual(ai.get_model(), ai.FREE_MODEL)

    def test_personal_model_is_used_only_after_explicit_mode_selection(self):
        ai.set_api_key("id.secret")
        self.assertEqual(ai.get_model(), ai.FREE_MODEL)

        ai.set_chat_mode("personal")
        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

        ai.set_api_key("")

        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_personal_model_can_be_selected_before_key_is_saved(self):
        ai.set_chat_mode("personal")
        ai.set_model(ai.VISION_MODEL)

        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_chat_mode_is_explicit_and_preserves_saved_personal_key(self):
        self.assertEqual(ai.get_chat_mode(), "default")

        ai.set_api_key("id.secret")
        self.assertEqual(ai.get_chat_mode(), "default")

        ai.set_chat_mode("personal")
        self.assertEqual(ai.get_chat_mode(), "personal")

        ai.set_chat_mode("default")

        self.assertEqual(ai.get_chat_mode(), "default")
        self.assertEqual(ai.get_api_key(), "id.secret")

    def test_legacy_config_without_mode_migrates_by_key_presence(self):
        with open(self.config_path, "w", encoding="utf-8") as config_file:
            json.dump({"api_key": "saved.key", "model": ai.VISION_MODEL}, config_file)

        self.assertEqual(ai.get_chat_mode(), "personal")

    def test_personal_mode_does_not_silently_fall_back_without_key(self):
        ai.set_chat_mode("personal")

        self.assertEqual(ai.get_chat_mode(), "personal")
        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_environment_key_is_used_after_selecting_personal_mode(self):
        os.environ["ZHIPU_API_KEY"] = "env.secret"
        ai.set_chat_mode("personal")

        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_saved_key_ignores_stale_free_model_value(self):
        with open(self.config_path, "w", encoding="utf-8") as config_file:
            json.dump({
                "api_key": "id.secret",
                "model": ai.FREE_MODEL,
            }, config_file)

        self.assertEqual(ai.get_chat_mode(), "personal")
        self.assertEqual(ai.get_model(), ai.VISION_MODEL)

    def test_personal_mode_without_key_returns_stable_configuration_error(self):
        ai.set_chat_mode("personal")

        self.assertEqual(
            list(ai.chat_stream("hello", ai._default_memory())),
            [("error", "personal_api_key_required")],
        )

    def test_proxy_url_falls_back_to_public_release_configuration(self):
        public_config = os.path.join(self.temp_dir.name, "public-config.json")
        with open(public_config, "w", encoding="utf-8") as config_file:
            json.dump({
                "default_chat_proxy_url": "https://release.example/v1/chat"
            }, config_file)

        with patch.object(ai, "DEFAULT_CONFIG_PATH", public_config):
            self.assertEqual(
                ai.get_default_chat_proxy_url(),
                "https://release.example/v1/chat",
            )

    def test_profile_refresh_uses_personal_visual_model_not_free_placeholder(self):
        ai.set_api_key("id.secret")
        ai.set_chat_mode("personal")
        memory = ai._default_memory()
        memory["history"] = [{"role": "user", "content": "I like dogs"}]

        with patch(
            "buddy_ai.urllib.request.urlopen", return_value=FakeJsonResponse()
        ) as urlopen:
            ai._refresh_user_profile(memory)

        body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["model"], ai.VISION_MODEL)

    def test_free_mode_never_uses_saved_personal_key_for_profile_refresh(self):
        ai.set_api_key("id.secret")
        ai.set_chat_mode("default")

        with patch("buddy_ai.urllib.request.urlopen") as urlopen:
            ai._refresh_user_profile(ai._default_memory())

        urlopen.assert_not_called()

    def test_default_proxy_preserves_system_prompt_and_limits_message_count(self):
        ai.set_default_chat_consent(True)
        ai.set_default_chat_proxy_url("https://chat.example/v1/chat")
        memory = ai._default_memory()
        memory["history"] = [
            {"role": "user" if index % 2 == 0 else "assistant",
             "content": f"turn-{index}"}
            for index in range(10)
        ]
        response = FakeRequestsStreamResponse([
            b'data: {"choices":[{"delta":{"content":"hi"}}]}\n',
            b'data: [DONE]\n',
        ])

        with patch("buddy_ai.requests.post", return_value=response) as post:
            events = list(ai.chat_stream("hello", memory, timeout=5))

        body = json.loads(post.call_args.kwargs["data"].decode("utf-8"))
        self.assertLessEqual(len(body["messages"]), 7)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][-1], {
            "role": "user", "content": "hello",
        })
        self.assertEqual(events, [("token", "hi"), ("done", "hi")])

    def test_default_proxy_uses_requests_streaming_transport(self):
        ai.set_default_chat_consent(True)
        ai.set_default_chat_proxy_url("https://chat.example/v1/chat")
        response = FakeRequestsStreamResponse([
            b'data: {"choices":[{"delta":{"content":"hi"}}]}',
            b'data: [DONE]',
        ])

        with patch("buddy_ai.requests.post", return_value=response) as post, patch(
            "buddy_ai.urllib.request.urlopen"
        ) as urlopen:
            events = list(ai.chat_stream("hello", ai._default_memory(), timeout=5))

        self.assertEqual(events, [("token", "hi"), ("done", "hi")])
        self.assertTrue(post.call_args.kwargs["stream"])
        urlopen.assert_not_called()

    def test_default_proxy_does_not_duplicate_system_prompt_with_short_history(self):
        ai.set_default_chat_consent(True)
        ai.set_default_chat_proxy_url("https://chat.example/v1/chat")
        memory = ai._default_memory()
        response = FakeRequestsStreamResponse([b'data: [DONE]'])

        with patch("buddy_ai.requests.post", return_value=response) as post:
            list(ai.chat_stream("hello", memory, timeout=5))

        body = json.loads(post.call_args.kwargs["data"].decode("utf-8"))
        system_contents = [
            message["content"] for message in body["messages"]
            if message["role"] == "system"
        ]
        self.assertEqual(len(system_contents), len(set(system_contents)))

    def test_default_proxy_uses_role_limits_without_losing_system_ends(self):
        ai.set_default_chat_consent(True)
        ai.set_default_chat_proxy_url("https://chat.example/v1/chat")
        memory = ai._default_memory()
        original_build = ai._build_messages

        def long_messages(*args, **kwargs):
            messages = original_build(*args, **kwargs)
            messages[0]["content"] = "persona-start " + ("中" * 5000) + " knowledge-end"
            messages[-1]["content"] = "turn-start " + ("问" * 1600) + " turn-end"
            return messages

        response = FakeRequestsStreamResponse([b'data: [DONE]'])
        with patch.object(ai, "_build_messages", side_effect=long_messages), patch(
                "buddy_ai.requests.post", return_value=response
        ) as post:
            list(ai.chat_stream("hello", memory, timeout=5))

        body = json.loads(post.call_args.kwargs["data"].decode("utf-8"))
        system = body["messages"][0]["content"]
        self.assertLessEqual(len(system), 4000)
        self.assertTrue(system.startswith("persona-start"))
        self.assertTrue(system.endswith("knowledge-end"))
        turn = body["messages"][-1]["content"]
        self.assertLessEqual(len(turn), 1200)
        self.assertTrue(turn.startswith("turn-start"))
        self.assertTrue(turn.endswith("turn-end"))
        self.assertLessEqual(len(post.call_args.kwargs["data"]), 16384)

    def test_default_proxy_maps_http_quota_error(self):
        ai.set_default_chat_consent(True)
        ai.set_default_chat_proxy_url("https://chat.example/v1/chat")
        response = FakeRequestsStreamResponse(
            [], status_code=429,
            payload={"error": "default_quota_exhausted"},
        )

        with patch("buddy_ai.requests.post", return_value=response):
            events = list(ai.chat_stream("hello", ai._default_memory()))

        self.assertEqual(events, [("error", "default_quota_exhausted")])

    def test_chat_diagnostic_log_excludes_message_and_credentials(self):
        log_path = os.path.join(self.temp_dir.name, "chat_diagnostic.log")
        with patch.object(ai, "CHAT_DIAGNOSTIC_LOG_PATH", log_path):
            ai._log_chat_diagnostic(
                "default_proxy_http_error", status=503,
                exception_type="HTTPError", secret="must-not-appear",
                message="private-message-must-not-appear",
            )

        with open(log_path, encoding="utf-8") as log_file:
            entry = json.loads(log_file.readline())
        self.assertEqual(entry["event"], "default_proxy_http_error")
        self.assertEqual(entry["status"], 503)
        self.assertEqual(entry["exception_type"], "HTTPError")
        self.assertNotIn("secret", entry)
        self.assertNotIn("message", entry)

    def test_prepare_player_avatar_center_crops_and_saves_png(self):
        source_path = os.path.join(self.temp_dir.name, "wide.png")
        source = QImage(6, 4, QImage.Format_ARGB32)
        source.fill(qRgb(220, 80, 80))
        for y in range(4):
            for x in range(1, 5):
                source.setPixel(x, y, qRgb(80, 180, 110))
        self.assertTrue(source.save(source_path, "PNG"))

        saved_path = ai.prepare_player_avatar(source_path)
        saved = QImage(saved_path)

        self.assertEqual(saved_path, ai.get_player_avatar_path())
        self.assertTrue(os.path.isfile(saved_path))
        self.assertEqual(saved.size().width(), 256)
        self.assertEqual(saved.size().height(), 256)
        center = saved.pixelColor(128, 128)
        self.assertGreater(center.green(), center.red())

    def test_prepare_player_avatar_rejects_invalid_image_without_overwrite(self):
        avatar_path = ai.get_player_avatar_path()
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)
        original = QImage(2, 2, QImage.Format_ARGB32)
        original.fill(qRgb(90, 120, 180))
        self.assertTrue(original.save(avatar_path, "PNG"))
        invalid_path = os.path.join(self.temp_dir.name, "invalid.png")
        with open(invalid_path, "w", encoding="utf-8") as invalid:
            invalid.write("not an image")

        with self.assertRaises(ValueError):
            ai.prepare_player_avatar(invalid_path)

        self.assertFalse(QImage(avatar_path).isNull())

    def test_clear_player_avatar_removes_saved_file(self):
        avatar_path = ai.get_player_avatar_path()
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)
        image = QImage(2, 2, QImage.Format_ARGB32)
        image.fill(qRgb(220, 160, 120))
        self.assertTrue(image.save(avatar_path, "PNG"))

        ai.clear_player_avatar()

        self.assertFalse(os.path.exists(avatar_path))


if __name__ == "__main__":
    unittest.main()
