import json
import unittest
from pathlib import Path

import pet


class WakeShakeDetectorTests(unittest.TestCase):
    def test_long_left_right_shake_wakes(self):
        detector = pet.WakeShakeDetector()
        detector.start(100, now=10.0)

        self.assertFalse(detector.move(130, now=10.20))
        self.assertFalse(detector.move(90, now=10.32))
        self.assertFalse(detector.move(135, now=10.43))
        self.assertTrue(detector.move(85, now=10.55))

    def test_quick_shake_does_not_wake(self):
        detector = pet.WakeShakeDetector()
        detector.start(100, now=10.0)

        detector.move(130, now=10.05)
        detector.move(90, now=10.10)
        detector.move(135, now=10.15)
        self.assertFalse(detector.move(85, now=10.20))

    def test_one_way_drag_does_not_wake(self):
        detector = pet.WakeShakeDetector()
        detector.start(100, now=10.0)

        for index, x in enumerate((130, 165, 205, 250), start=1):
            self.assertFalse(detector.move(x, now=10.0 + index * 0.2))


class SleepAnimationAssetTests(unittest.TestCase):
    def test_sleep_animation_is_a_smooth_grounded_twelve_frame_loop(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )
        frames = sorted((animation_dir / "sleep").glob("*.png"))

        self.assertEqual(len(frames), 12)
        self.assertEqual(manifest["sleep"]["fps"], 2.4)
        self.assertTrue(manifest["sleep"]["loop"])
        self.assertEqual(manifest["sleep"]["scale"], 0.8)
        self.assertTrue(manifest["sleep"]["anchor_bottom"])


if __name__ == "__main__":
    unittest.main()
