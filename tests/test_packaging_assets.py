from pathlib import Path
import json
import unittest

from PyQt5.QtGui import QImage


class PackagingAssetTests(unittest.TestCase):
    def test_release_config_points_to_the_free_chat_routes(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config.json.example").read_text(encoding="utf-8")
        )

        self.assertEqual(
            config["default_chat_fallback_url"],
            "https://petpet-default-chat.gsheen-petpet.workers.dev/v1/chat",
        )
        self.assertEqual(
            config["default_chat_primary_url"],
            "https://petpet-yun-chat-zqblnbrnfs.cn-hangzhou.fcapp.run/v1/chat",
        )
        self.assertEqual(config["api_key"], "")

    def test_home_scene_assets_are_packaged_for_windows_and_macos(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
            contents = (root / "packaging" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                '(str(runtime_assets_root), "assets/runtime")', contents
            )
            self.assertNotIn("assets/source", contents)

    def test_game_knowledge_is_packaged_for_windows_and_macos(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
            contents = (root / "packaging" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                '(str(runtime_assets_root), "assets/runtime")',
                contents,
            )

    def test_home_pet_idle_and_navigation_assets_are_transparent_pngs(self):
        asset_dir = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "runtime"
            / "pets"
            / "ice_cream"
            / "home"
            / "poses"
        )
        for name in (
            "home-pet-idle-sit.png",
        ):
            with self.subTest(name=name):
                path = asset_dir / name
                self.assertTrue(path.is_file(), name)
                image = QImage(str(path))
                self.assertFalse(image.isNull(), name)
                self.assertTrue(image.hasAlphaChannel(), name)
                self.assertEqual(image.pixelColor(0, 0).alpha(), 0, name)
                self.assertGreater(image.width(), 128, name)
                self.assertGreater(image.height(), 128, name)

    def test_home_pet_sleep_animation_is_a_transparent_three_by_three_sheet(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "runtime"
            / "pets"
            / "ice_cream"
            / "home"
            / "poses"
            / "home-pet-sleep.png"
        )
        self.assertTrue(path.is_file())
        image = QImage(str(path))
        self.assertFalse(image.isNull())
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.size().width(), 1920)
        self.assertEqual(image.size().height(), 1920)

    def test_navigation_and_furniture_assets_have_runtime_domains(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "runtime"
        for path in (
            root / "scenes/home/home-nav-paw.png",
            root / "scenes/home/home-nav-target.png",
            root / "scenes/home/home-nav-arrow.png",
            root / "furniture/home/rug.png",
            root / "furniture/home/sofa.png",
        ):
            self.assertTrue(path.is_file(), str(path))

    def test_animation_source_art_is_not_in_runtime_assets(self):
        root = Path(__file__).resolve().parents[1] / "assets"
        self.assertTrue((root / "source/spritesheets").is_dir())
        self.assertFalse(
            (root / "runtime/pets/lunch_meat/desktop/animations/sources").exists()
        )

    def test_legacy_shared_pet_directories_do_not_exist(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "runtime" / "pets"
        self.assertFalse((root / "desktop").exists())
        self.assertFalse((root / "home").exists())


if __name__ == "__main__":
    unittest.main()
