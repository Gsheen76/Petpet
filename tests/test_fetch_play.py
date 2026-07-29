import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt5.QtCore import QPoint, QPointF, QRect
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

import pet


class FakeScenePet:
    def __init__(self):
        animation_dir = Path(pet.ANIMATIONS_DIR) / "play"
        self.settings = {"always_on_top": True}
        self.animation_frames = {
            "play": [
                QPixmap(str(path))
                for path in sorted(animation_dir.glob("*.png"))
            ]
        }
        self.animation_specs = {"play": {"fps": 14}}
        self.pose_pixmaps = {}

    def current_screen_rect(self):
        return QRect(0, 0, 1000, 700)

    def geometry(self):
        return QRect(690, 430, 190, 220)


class FetchAnimationAssetTests(unittest.TestCase):
    def test_fetch_animation_is_a_non_looping_24_frame_sequence(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )
        frames = sorted((animation_dir / "play").glob("*.png"))

        self.assertEqual(len(frames), 24)
        self.assertEqual(manifest["play"]["fps"], 14)
        self.assertFalse(manifest["play"]["loop"])
        self.assertTrue(manifest["play"]["anchor_bottom"])
        self.assertTrue(
            (Path(pet.PROPS_DIR) / "fetch_ball.png").exists()
        )

        for frame in frames:
            with Image.open(frame) as image:
                bounds = image.convert("RGBA").getchannel("A").getbbox()
            self.assertIsNotNone(bounds)
            self.assertGreater(bounds[0], 0)
            self.assertGreater(bounds[1], 0)
            self.assertLess(bounds[2], 512)
            self.assertLess(bounds[3], 512)


class FetchPlaySceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.finished = Mock()
        self.scene = pet.FetchPlayScene(
            FakeScenePet(), self.finished
        )

    def tearDown(self):
        if not self.scene._finishing:
            self.scene.cancel(notify=False)

    def test_scene_has_clickable_area_and_three_second_countdown(self):
        self.scene._phase = "aim"
        self.scene._countdown_deadline = 103.0

        self.assertGreater(self.scene.target_rect.width(), 150)
        self.assertGreater(self.scene.target_rect.height(), 100)
        self.assertTrue(
            self.scene.target_rect.contains(self.scene._dog_start)
        )
        self.assertAlmostEqual(
            self.scene._throw_origin.x(), self.scene._dog_start.x()
        )
        self.assertLess(
            self.scene._default_target.y(), self.scene._dog_start.y()
        )
        self.assertEqual(self.scene.countdown_value(now=100.0), 3)
        self.assertEqual(self.scene.countdown_value(now=101.1), 2)
        self.assertEqual(self.scene.countdown_value(now=102.1), 1)

    def test_click_target_starts_manual_throw(self):
        target = QPointF(self.scene.target_rect.center())
        self.scene._phase = "aim"

        self.scene.start_throw(target, automatic=False, now=20.0)

        self.assertEqual(self.scene._phase, "fetch")
        self.assertFalse(self.scene.last_throw_was_automatic)
        self.assertAlmostEqual(self.scene._target.x(), target.x())
        self.assertAlmostEqual(self.scene._target.y(), target.y())
        self.assertEqual(
            self.scene._ball_position(0), self.scene._throw_origin
        )

    def test_timeout_throws_automatically_from_default_point(self):
        self.scene._phase = "aim"
        self.scene._countdown_deadline = 30.0

        self.scene._advance(30.0)

        self.assertEqual(self.scene._phase, "fetch")
        self.assertTrue(self.scene.last_throw_was_automatic)
        self.assertEqual(self.scene._target, self.scene._default_target)
        self.assertEqual(
            self.scene._ball_position(0), self.scene._throw_origin
        )

    def test_ball_and_puppy_meet_on_the_same_final_frame(self):
        target = QPointF(
            self.scene.target_rect.right() - 36,
            self.scene.target_rect.center().y(),
        )
        self.scene._phase = "aim"
        self.scene.start_throw(target, automatic=False, now=20.0)
        last_frame = len(self.scene.frames) - 1
        dog_size = 122.0

        ball_end = self.scene._ball_position(last_frame)
        dog_end = self.scene._fetch_dog_baseline(
            last_frame, dog_size
        )

        self.assertAlmostEqual(ball_end.x(), target.x())
        self.assertAlmostEqual(ball_end.y(), target.y())
        self.assertAlmostEqual(dog_end.x(), target.x())
        self.assertAlmostEqual(
            dog_end.y()
            - dog_size * self.scene.CATCH_BASELINE_RATIO,
            target.y(),
        )
        self.assertNotEqual(
            self.scene._ball_position(last_frame - 1), target
        )
        self.assertNotEqual(
            self.scene._fetch_dog_baseline(
                last_frame - 1, dog_size
            ),
            dog_end,
        )

    def test_fetch_holds_final_frame_for_one_second_before_finishing(self):
        self.scene._phase = "fetch"
        self.scene._target = QPointF(self.scene._default_target)
        self.scene._phase_started_at = 50.0
        duration = len(self.scene.frames) / self.scene.fps

        self.scene._advance(50.0 + duration - 0.01)
        self.assertEqual(self.scene._frame_index, 23)
        self.finished.assert_not_called()

        self.scene._advance(50.0 + duration + 0.01)
        self.assertEqual(self.scene._phase, "celebrate")
        self.assertEqual(self.scene._frame_index, 23)
        self.finished.assert_not_called()

        celebration_started = self.scene._phase_started_at
        self.scene._advance(
            celebration_started
            + self.scene.CELEBRATION_SECONDS - 0.01
        )
        self.finished.assert_not_called()

        self.scene._advance(
            celebration_started
            + self.scene.CELEBRATION_SECONDS + 0.01
        )
        self.finished.assert_called_once_with(self.scene, True)


class PetPlayEntryTests(unittest.TestCase):
    def test_play_opens_scene_and_updates_stats_once(self):
        fake = SimpleNamespace(
            state={
                "sleeping": False,
                "energy": 60,
                "mood": 50,
                "hunger": 80,
            },
            play_scene=None,
            behavior="walk",
            target_vx=200,
            vx=100,
            vy=-50,
            on_ground=False,
            _play_return_pos=None,
            _on_play_scene_finished=Mock(),
            play_sound=Mock(),
            add_xp=Mock(),
            pos=Mock(return_value=QPoint(120, 180)),
            hide=Mock(),
        )
        scene = Mock()
        with patch("pet.FetchPlayScene", return_value=scene) as scene_type, \
                patch("pet.save_state"):
            pet.PetWindow.play(fake)

        self.assertEqual(fake.state["mood"], 70)
        self.assertEqual(fake.state["energy"], 48)
        self.assertEqual(fake.state["hunger"], 75)
        self.assertEqual(fake._play_return_pos, QPoint(120, 180))
        self.assertIs(fake.play_scene, scene)
        fake.hide.assert_called_once_with()
        scene.start.assert_called_once_with()
        scene_type.assert_called_once_with(
            fake, fake._on_play_scene_finished
        )


if __name__ == "__main__":
    unittest.main()
