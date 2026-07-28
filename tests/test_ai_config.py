import json
import os
import tempfile
import unittest
from unittest.mock import patch

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
        self.env_patch = patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        os.environ.pop("ZHIPU_API_KEY", None)

    def test_api_key_and_model_are_persisted_without_overwriting_each_other(self):
        ai.set_api_key("  id.secret  ")
        ai.set_model("glm-4-flash")

        self.assertEqual(ai.get_api_key(), "id.secret")
        self.assertEqual(ai.get_model(), "glm-4-flash")
        self.assertEqual(ai.get_api_key_source(), "config")
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            saved = json.load(config_file)
        self.assertEqual(saved["api_key"], "id.secret")
        self.assertEqual(saved["model"], "glm-4-flash")

    def test_invalid_or_bom_config_falls_back_safely(self):
        with open(self.config_path, "w", encoding="utf-8-sig") as config_file:
            json.dump(
                {"api_key": "saved.key", "model": "not-supported"},
                config_file,
            )

        self.assertEqual(ai.get_api_key(), "saved.key")
        self.assertEqual(ai.get_model(), ai.DEFAULT_MODEL)

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
                model="glm-4-flash",
            ))

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "glm-4-flash")
        self.assertEqual(events[-1], ("done", "hi"))


if __name__ == "__main__":
    unittest.main()
