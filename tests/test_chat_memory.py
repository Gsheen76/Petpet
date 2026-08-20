import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import buddy_ai as ai
from petpet.chat import api
from petpet.chat import memory


def default_memory():
    return {
        "user_profile": "unknown",
        "history": [],
        "born": 100.0,
        "pet_name": "Sheen",
    }


class ChatMemoryStoreTests(unittest.TestCase):
    def test_pet_memories_use_separate_files(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(api, "DATA_DIR", folder):
                lunch = {
                    "pet_name": "午餐肉",
                    "history": [{"role": "user", "content": "肉松"}],
                }
                ice = {
                    "pet_name": "冰淇淋",
                    "history": [{"role": "user", "content": "甜筒"}],
                }

                api.save_memory(lunch, "lunch_meat")
                api.save_memory(ice, "ice_cream")

                self.assertEqual(
                    api.load_memory("lunch_meat")["history"][0]["content"],
                    "肉松",
                )
                self.assertEqual(
                    api.load_memory("ice_cream")["history"][0]["content"],
                    "甜筒",
                )
                self.assertTrue((Path(folder) / "memory.json").exists())
                self.assertTrue((Path(folder) / "memory-ice_cream.json").exists())

    def test_old_home_memory_is_migrated_to_lunch_meat(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(api, "DATA_DIR", folder):
                (Path(folder) / "memory-home.json").write_text(
                    '{"history": [{"role": "assistant", "content": "旧记录"}]}',
                    encoding="utf-8",
                )

                self.assertIn("旧记录", str(api.load_memory("lunch_meat")))
                self.assertEqual(
                    api.load_memory("lunch_meat")["history"][0]["content"],
                    "旧记录",
                )
                self.assertTrue((Path(folder) / "memory.json").exists())

    def test_pet_id_normalization_preserves_registered_ids_and_aliases(self):
        self.assertEqual(api.normalize_memory_pet_id("lunch_meat"), "lunch_meat")
        self.assertEqual(api.normalize_memory_pet_id("ice_cream"), "ice_cream")
        self.assertEqual(api.normalize_memory_pet_id("desktop"), "lunch_meat")
        self.assertEqual(api.normalize_memory_pet_id("home"), "lunch_meat")
        self.assertEqual(api.normalize_memory_pet_id("unknown"), "lunch_meat")

    def test_set_pet_name_updates_only_selected_pet_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(api, "DATA_DIR", folder):
                api.set_pet_name("肉松", "lunch_meat")
                api.set_pet_name("甜筒", "ice_cream")

                self.assertEqual(api.load_memory("lunch_meat")["pet_name"], "肉松")
                self.assertEqual(api.load_memory("ice_cream")["pet_name"], "甜筒")

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

    def test_old_profile_keyword_aliases_lunch_meat(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(api, "DATA_DIR", folder):
                api.save_memory(
                    {**default_memory(), "history": [{"role": "user", "content": "旧入口"}]},
                    profile="home",
                )

                self.assertEqual(
                    api.load_memory(profile="desktop")["history"][0]["content"],
                    "旧入口",
                )


class BuddyAiMemoryCompatibilityTests(unittest.TestCase):
    def test_pet_id_aware_append_keeps_histories_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(ai, "DATA_DIR", folder):
                lunch = ai.load_memory(pet_id="lunch_meat")
                ice = ai.load_memory(pet_id="ice_cream")
                ai.append_history(lunch, "user", "午餐肉消息", pet_id="lunch_meat")
                ai.append_history(ice, "user", "冰淇淋消息", pet_id="ice_cream")

                saved_lunch = ai.load_memory(pet_id="lunch_meat")
                saved_ice = ai.load_memory(pet_id="ice_cream")

            self.assertEqual(
                [item["content"] for item in saved_lunch["history"]],
                ["午餐肉消息"],
            )
            self.assertEqual(
                [item["content"] for item in saved_ice["history"]],
                ["冰淇淋消息"],
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
