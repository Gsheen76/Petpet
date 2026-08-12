from pathlib import Path
import json
import unittest

from PyQt5.QtGui import QImage


class PackagingAssetTests(unittest.TestCase):
    def test_release_config_points_to_the_deployed_default_chat_proxy(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config.json.example").read_text(encoding="utf-8")
        )

        self.assertEqual(
            config["default_chat_proxy_url"],
            "https://petpet-default-chat.gsheen-petpet.workers.dev/v1/chat",
        )
        self.assertEqual(config["api_key"], "")

    def test_home_scene_assets_are_packaged_for_windows_and_macos(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
            contents = (root / "packaging" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn('(str(assets_root / "scenes"), "assets/scenes")', contents)

    def test_game_knowledge_is_packaged_for_windows_and_macos(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("Petpet-windows.spec", "Petpet-mac.spec"):
            contents = (root / "packaging" / filename).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                '(str(assets_root / "knowledge"), "assets/knowledge")',
                contents,
            )

    def test_home_pet_idle_and_navigation_assets_are_transparent_pngs(self):
        asset_dir = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "scenes"
            / "home"
        )
        for name in (
            "home-pet-idle-sit.png",
            "home-nav-paw.png",
            "home-nav-target.png",
            "home-nav-arrow.png",
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
            / "scenes"
            / "home"
            / "home-pet-sleep.png"
        )
        self.assertTrue(path.is_file())
        image = QImage(str(path))
        self.assertFalse(image.isNull())
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.size().width(), 1920)
        self.assertEqual(image.size().height(), 1920)


if __name__ == "__main__":
    unittest.main()
