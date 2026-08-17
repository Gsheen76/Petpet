import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import buddy_ai as ai
from petpet.chat import memory


def default_memory():
    return {
        "user_profile": "unknown",
        "history": [],
        "born": 100.0,
        "pet_name": "Sheen",
    }


class ChatMemoryStoreTests(unittest.TestCase):
    def test_first_home_load_seeds_desktop_memory_once(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop_path = Path(folder) / "memory.json"
            home_path = Path(folder) / "memory-home.json"
            memory.save_memory(
                str(desktop_path),
                {
                    **default_memory(),
                    "pet_name": "团子",
                    "history": [{"role": "user", "content": "你好"}],
                },
            )

            home = memory.load_memory(
                str(home_path), default_memory, seed_path=str(desktop_path)
            )

            self.assertEqual(home["pet_name"], "团子")
            self.assertEqual(home["history"][0]["content"], "你好")
            self.assertTrue(home_path.exists())

    def test_existing_home_memory_is_not_replaced_by_desktop_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop_path = Path(folder) / "memory.json"
            home_path = Path(folder) / "memory-home.json"
            memory.save_memory(
                str(desktop_path),
                {**default_memory(), "pet_name": "桌桌", "history": []},
            )
            home = memory.load_memory(
                str(home_path), default_memory, seed_path=str(desktop_path)
            )
            home["pet_name"] = "豆包"
            home["history"].append({"role": "user", "content": "回家啦"})
            memory.save_memory(str(home_path), home)
            memory.save_memory(
                str(desktop_path),
                {**default_memory(), "pet_name": "新桌桌", "history": []},
            )

            reloaded = memory.load_memory(
                str(home_path), default_memory, seed_path=str(desktop_path)
            )

            self.assertEqual(reloaded["pet_name"], "豆包")
            self.assertEqual(reloaded["history"][0]["content"], "回家啦")

    def test_invalid_profile_falls_back_to_desktop(self):
        self.assertEqual(memory.normalize_profile("home"), "home")
        self.assertEqual(memory.normalize_profile("desktop"), "desktop")
        self.assertEqual(memory.normalize_profile("unknown"), "desktop")
        self.assertEqual(memory.normalize_profile(None), "desktop")


class BuddyAiMemoryCompatibilityTests(unittest.TestCase):
    def test_profile_aware_append_keeps_histories_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop_path = str(Path(folder) / "memory.json")
            home_path = str(Path(folder) / "memory-home.json")
            with (
                patch.object(ai, "MEMORY_PATH", desktop_path),
                patch.object(ai, "HOME_MEMORY_PATH", home_path, create=True),
            ):
                desktop = ai.load_memory(profile="desktop")
                home = ai.load_memory(profile="home")
                ai.append_history(
                    desktop, "user", "桌面消息", profile="desktop"
                )
                ai.append_history(home, "user", "小屋消息", profile="home")

                saved_desktop = ai.load_memory(profile="desktop")
                saved_home = ai.load_memory(profile="home")

            self.assertEqual(
                [item["content"] for item in saved_desktop["history"]],
                ["桌面消息"],
            )
            self.assertEqual(
                [item["content"] for item in saved_home["history"]],
                ["小屋消息"],
            )

    def test_removing_one_memory_only_deletes_its_own_thumbnails(self):
        with tempfile.TemporaryDirectory() as folder:
            image_dir = Path(folder) / "chat_images"
            image_dir.mkdir()
            desktop_image = image_dir / "desktop.png"
            home_image = image_dir / "home.png"
            desktop_image.write_bytes(b"desktop")
            home_image.write_bytes(b"home")
            desktop = {
                "history": [
                    {
                        "role": "user",
                        "content": "图片",
                        "image": {
                            "thumbnail": "chat_images/desktop.png",
                            "filename": "desktop.png",
                        },
                    }
                ]
            }

            with patch.object(ai, "DATA_DIR", folder):
                ai.remove_memory_thumbnails(desktop)

            self.assertFalse(desktop_image.exists())
            self.assertTrue(home_image.exists())


if __name__ == "__main__":
    unittest.main()
