import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt5.QtCore import QPointF, QRect, Qt
from PyQt5.QtGui import QColor, QImage, QPainter
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


class AutoSleepBehaviorTests(unittest.TestCase):
    def test_energy_below_thirty_starts_auto_sleep_walk(self):
        fake = SimpleNamespace(
            state={
                "sleeping": False,
                "sleep_mode": None,
                "energy": 29.9,
            },
            _auto_sleep_phase=None,
            _auto_sleep_snooze_until=0.0,
            AUTO_SLEEP_ENERGY_THRESHOLD=30.0,
            AUTO_WAKE_ENERGY_THRESHOLD=80.0,
            _begin_auto_sleep=Mock(return_value=True),
        )

        result = pet.PetWindow._update_auto_sleep_state(fake, now=100.0)

        self.assertEqual(result, "walking")
        fake._begin_auto_sleep.assert_called_once_with(100.0)

    def test_energy_at_thirty_does_not_start_auto_sleep(self):
        fake = SimpleNamespace(
            state={
                "sleeping": False,
                "sleep_mode": None,
                "energy": 30.0,
            },
            _auto_sleep_phase=None,
            _auto_sleep_snooze_until=0.0,
            AUTO_SLEEP_ENERGY_THRESHOLD=30.0,
            AUTO_WAKE_ENERGY_THRESHOLD=80.0,
            _begin_auto_sleep=Mock(return_value=True),
        )

        result = pet.PetWindow._update_auto_sleep_state(fake, now=100.0)

        self.assertIsNone(result)
        fake._begin_auto_sleep.assert_not_called()

    def test_auto_sleep_wakes_only_above_eighty(self):
        fake = SimpleNamespace(
            state={
                "sleeping": True,
                "sleep_mode": "auto",
                "energy": 80.0,
            },
            _auto_sleep_phase="sleeping",
            _auto_sleep_target_x=None,
            AUTO_SLEEP_ENERGY_THRESHOLD=30.0,
            AUTO_WAKE_ENERGY_THRESHOLD=80.0,
            _wake_from_auto_sleep=Mock(return_value=True),
        )

        result = pet.PetWindow._update_auto_sleep_state(fake, now=100.0)
        self.assertEqual(result, "sleeping")
        fake._wake_from_auto_sleep.assert_not_called()

        fake.state["energy"] = 80.1
        result = pet.PetWindow._update_auto_sleep_state(fake, now=101.0)
        self.assertEqual(result, "woke")
        fake._wake_from_auto_sleep.assert_called_once_with()

    def test_manual_sleep_never_uses_auto_wake(self):
        fake = SimpleNamespace(
            state={
                "sleeping": False,
                "sleep_mode": None,
                "energy": 100.0,
            },
            _auto_sleep_phase=None,
            _auto_sleep_target_x=None,
            _auto_sleep_snooze_until=0.0,
            behavior="idle",
            target_vx=0,
            vx=0,
            say=Mock(),
            play_sound=Mock(),
            refresh_pose_from_state=Mock(),
            AUTO_SLEEP_ENERGY_THRESHOLD=30.0,
            AUTO_WAKE_ENERGY_THRESHOLD=80.0,
            _wake_from_auto_sleep=Mock(return_value=True),
        )
        with patch("pet.save_state"):
            pet.PetWindow.toggle_sleep(fake)

        self.assertTrue(fake.state["sleeping"])
        self.assertEqual(fake.state["sleep_mode"], "manual")
        result = pet.PetWindow._update_auto_sleep_state(fake, now=100.0)
        self.assertEqual(result, "sleeping")
        fake._wake_from_auto_sleep.assert_not_called()

    def test_nearest_bottom_corner_is_selected(self):
        fake = SimpleNamespace(
            AUTO_SLEEP_CORNER_MARGIN=18,
            current_screen_rect=Mock(return_value=QRect(0, 0, 1000, 700)),
            width=Mock(return_value=190),
            x=Mock(return_value=800),
        )

        self.assertEqual(
            pet.PetWindow._auto_sleep_corner_x(fake), 792.0
        )
        fake.x.return_value = 40
        self.assertEqual(
            pet.PetWindow._auto_sleep_corner_x(fake), 18.0
        )

    def test_low_state_icons_are_drawn_without_emoji_fonts(self):
        image = QImage(80, 40, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        for index, action in enumerate(("feed", "play")):
            fake = SimpleNamespace(action_name=action)
            pet.InteractiveBubble._draw_action_icon(
                fake,
                painter,
                QPointF(index * 40 + 20, 20),
                QColor("#c56f54"),
            )
        painter.end()

        colored = sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if QColor.fromRgba(image.pixel(x, y)).alpha() > 0
        )
        self.assertGreater(colored, 90)


if __name__ == "__main__":
    unittest.main()
