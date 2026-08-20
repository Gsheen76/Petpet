import json
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import pet


class PettingAnimationAssetTests(unittest.TestCase):
    def test_dinosaur_outfit_has_a_sixteen_frame_idle_sequence(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )
        frames = sorted((animation_dir / "outfits" / "dinosaur" / "idle").glob("*.png"))

        self.assertEqual(len(frames), 16)
        self.assertEqual(manifest["idle_dinosaur"]["fps"], 8)
        self.assertEqual(
            manifest["idle_dinosaur"]["frame_sequence"],
            list(range(1, 17)) + list(range(7, 12)),
        )
        self.assertEqual(
            manifest["idle_dinosaur"]["frame_durations_ms"],
            [160.0, 160.0, 40.0, 40.0, 40.0]
            + [160.0] * 11,
        )
        self.assertAlmostEqual(
            sum(manifest["idle_dinosaur"]["frame_durations_ms"]),
            2200.0,
            places=3,
        )

        for frame_path in frames:
            with Image.open(frame_path) as frame:
                self.assertEqual(frame.size, (640, 640))
                self.assertEqual(frame.mode, "RGBA")

    def test_strawberry_outfit_has_a_sixteen_frame_idle_sequence(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )
        frames = sorted(
            (animation_dir / "outfits" / "strawberry" / "idle").glob("*.png")
        )

        self.assertEqual(len(frames), 16)
        self.assertEqual(manifest["idle_strawberry"]["fps"], 8)
        self.assertEqual(
            manifest["idle_strawberry"]["frame_sequence"],
            list(range(5, 17)) + list(range(8, 14)),
        )
        self.assertEqual(
            manifest["idle_strawberry"]["frame_durations_ms"],
            [160.0] * 5 + [60.0, 60.0] + [160.0] * 9,
        )
        self.assertAlmostEqual(
            sum(
                manifest["idle_strawberry"]["frame_durations_ms"][index - 1]
                for index in manifest["idle_strawberry"]["frame_sequence"]
            ),
            2680.0,
            places=3,
        )

        for frame_path in frames:
            with Image.open(frame_path) as frame:
                self.assertEqual(frame.size, (640, 640))
                self.assertEqual(frame.mode, "RGBA")

    def test_petting_animation_is_a_non_looping_24_frame_20_fps_sequence(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )
        frames = sorted((animation_dir / "pet").glob("*.png"))

        self.assertEqual(len(frames), 24)
        self.assertEqual(manifest["pet"]["fps"], 20)
        self.assertFalse(manifest["pet"]["loop"])
        self.assertEqual(manifest["pet"]["fallback"], "happy")
        self.assertTrue(manifest["pet"]["anchor_bottom"])

        for frame_path in frames:
            with Image.open(frame_path) as frame:
                self.assertEqual(frame.size, (512, 512))
                self.assertEqual(frame.mode, "RGBA")
                self.assertIsNotNone(frame.getchannel("A").getbbox())

    def test_middle_frames_show_hand_contact_above_the_dog(self):
        animation_dir = Path(pet.ANIMATIONS_DIR) / "pet"
        with Image.open(animation_dir / "012.png") as middle:
            alpha = middle.getchannel("A")
            upper_right = alpha.crop((360, 0, 512, 150))
            self.assertIsNotNone(upper_right.getbbox())

    def test_no_food_fragment_remains_between_the_front_paws(self):
        animation_dir = Path(pet.ANIMATIONS_DIR) / "pet"
        for frame_path in sorted(animation_dir.glob("*.png")):
            with Image.open(frame_path) as frame:
                between_paws = frame.getchannel("A").crop(
                    (260, 440, 300, 450)
                ).point(
                    lambda value: 255 if value > 8 else 0
                )
                self.assertIsNone(
                    between_paws.getbbox(),
                    f"food fragment remains in {frame_path.name}",
                )

    def test_interaction_animation_scales_use_the_idle_size_baseline(self):
        animation_dir = Path(pet.ANIMATIONS_DIR)
        manifest = json.loads(
            (animation_dir / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            {name: manifest[name]["scale"] for name in (
                "pet", "eat", "dig_reward", "sleep"
            )},
            {"pet": 1.0, "eat": 1.0, "dig_reward": 1.0, "sleep": 0.7},
        )


class PetClickAnimationTests(unittest.TestCase):
    def test_single_click_plays_the_complete_petting_sequence(self):
        class FakePet:
            def __init__(self):
                self.state = {"sleeping": False, "mood": 50}
                self.animations = []
                self.pose = pet.POSE["idle"]

            def say(self, *_args):
                pass

            def play_sound(self, *_args):
                pass

            def trigger_animation(self, name, duration_ms=None):
                self.animations.append((name, duration_ms))

            def refresh_pose_from_state(self):
                pass

            def add_xp(self, *_args):
                pass

        fake = FakePet()
        with patch("pet.save_state"), patch("pet.QTimer.singleShot"):
            pet.PetWindow.pet_click(fake)

        self.assertEqual(fake.animations, [("pet", None)])
        self.assertEqual(fake.state["mood"], 60)

    def test_sequence_duration_is_derived_from_frames_and_fps(self):
        fake = type("FakePet", (), {
            "animation_frames": {"pet": [object()] * 24},
            "animation_specs": {"pet": {"fps": 20}},
        })()

        duration = pet.PetWindow._animation_duration_ms(fake, "pet")

        self.assertEqual(duration, 1200)

    def test_eat_sequence_duration_covers_two_complete_cycles(self):
        fake = type("FakePet", (), {
            "animation_frames": {"eat": [object()] * 8},
            "animation_specs": {"eat": {"fps": 6}},
        })()

        duration = pet.PetWindow._animation_duration_ms(fake, "eat", cycles=2)

        self.assertEqual(duration, 2667)


if __name__ == "__main__":
    unittest.main()
