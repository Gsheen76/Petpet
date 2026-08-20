import json
import os
import tempfile
import unittest


class ChatConfigBoundaryTests(unittest.TestCase):
    def test_package_normalizes_legacy_and_invalid_values(self):
        from petpet.chat import config

        normalized = config.normalize_config(
            {"api_key": "  saved.key  ", "model": "glm-4.7-flash"},
            env_api_key="",
        )

        self.assertEqual(normalized["api_key"], "saved.key")
        self.assertEqual(normalized["chat_mode"], "personal")
        self.assertEqual(normalized["model"], config.VISION_MODEL)

    def test_package_persists_config_atomically_and_reads_bom(self):
        from petpet.chat import config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            config.save_config(
                path,
                {"api_key": " key ", "chat_mode": "personal", "model": config.VISION_MODEL},
            )
            with open(path, "r", encoding="utf-8") as file:
                saved = json.load(file)
            self.assertEqual(saved["api_key"], "key")
            self.assertFalse(os.path.exists(path + ".tmp"))

            with open(path, "w", encoding="utf-8-sig") as file:
                json.dump(saved, file)
            self.assertEqual(config.load_config(path)["api_key"], "key")

    def test_package_resolves_endpoint_precedence(self):
        from petpet.chat import config

        public = {"default_chat_primary_url": "https://public.example/chat"}
        local = {"default_chat_primary_url": "https://local.example/chat"}

        self.assertEqual(
            config.default_chat_primary_url(local, public),
            "https://local.example/chat",
        )
        self.assertEqual(
            config.default_chat_primary_url({}, public),
            "https://public.example/chat",
        )

    def test_package_quota_counts_request_once_and_resets_by_day(self):
        from petpet.chat import config

        request_id = "123e4567-e89b-42d3-a456-426614174000"
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "quota.json")
            self.assertTrue(config.record_quota_success(path, request_id, "2026-08-15", limit=1))
            self.assertFalse(config.record_quota_success(path, request_id, "2026-08-15", limit=1))
            self.assertFalse(config.quota_available(path, "2026-08-15", limit=1))
            self.assertTrue(config.quota_available(path, "2026-08-16", limit=1))

    def test_buddy_ai_keeps_legacy_configuration_facade(self):
        import buddy_ai
        from petpet.chat import config

        self.assertEqual(buddy_ai.VISION_MODEL, config.VISION_MODEL)
        self.assertTrue(callable(buddy_ai.load_config))
        self.assertTrue(callable(buddy_ai.get_default_chat_primary_url))


if __name__ == "__main__":
    unittest.main()
