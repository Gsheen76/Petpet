import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import QApplication

import pet
from petpet.app.pets import pet_asset_path


class AnimationColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_color_correction_reduces_saturation_and_preserves_alpha(self):
        image = QImage(4, 4, QImage.Format_ARGB32)
        image.fill(QColor(240, 60, 30, 128))
        original = QPixmap.fromImage(image)

        corrected = pet.adjust_animation_colors(
            original, saturation=0.8, brightness=0.95
        ).toImage().convertToFormat(QImage.Format_ARGB32)
        pixel = QColor.fromRgba(corrected.pixel(1, 1))

        self.assertEqual(pixel.alpha(), 128)
        self.assertLess(pixel.red(), 240)
        self.assertLess(pixel.red() - pixel.green(), 240 - 60)

    def test_eat_manifest_uses_subtle_correction(self):
        manifest_path = (
            Path(pet.ANIMATIONS_DIR) / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["eat"]["fps"], 20)
        # 2026-10-07 统一轮：颜色已在像素层对齐 idle，渲染期滤镜恒等
        self.assertEqual(manifest["eat"]["saturation"], 1.0)
        self.assertEqual(manifest["eat"]["brightness"], 1.0)

    def test_desktop_asset_lookup_uses_active_pet(self):
        self.assertTrue(
            pet_asset_path("ice_cream", "desktop", "idle").endswith(
                "pets/ice_cream/desktop/poses/idle.png"
            )
        )

    def test_missing_ice_cream_action_returns_ice_cream_idle(self):
        self.assertTrue(
            pet_asset_path("ice_cream", "desktop", "play").endswith(
                "pets/ice_cream/desktop/poses/idle.png"
            )
        )


if __name__ == "__main__":
    unittest.main()


class PlayAnimationScaleTests(unittest.TestCase):
    """陪我出场 play 动画尺寸（2026-09-18 用户定稿：缩小）。

    实测（真平台 grab）：scale 1.3 时 play 峰值主体 130×148px vs idle
    最宽 88 / 恒高 143——宽度 +47% 即「太大」主因。交互动画惯例与
    eat/pet/dig_reward 对齐取 1.0。
    """

    def test_lunch_meat_play_scale_matches_interaction_convention(self):
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "assets" / "runtime" / "pets" / "lunch_meat"
            / "desktop" / "animations" / "manifest.json"
        )
        with open(manifest_path, encoding="utf-8") as stream:
            manifest = json.load(stream)

        self.assertEqual(
            manifest["play"].get("scale", 1.0),
            1.12,  # 2026-10-07 用户微调轮：玩耍放大
            "陪我出场 play 动画 scale（用户定稿 1.12）",
        )
