import copy
import json
import math
import os
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import pet


class DebugParameterRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        self.window = pet.PetWindow(state)

    def tearDown(self):
        self.window.close()

    def test_non_finite_persisted_values_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "debug_parameters.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"pet_width": float("nan"), "gravity": float("inf")}, stream)

            with patch.object(pet, "DEBUG_PARAMETERS_PATH", path):
                values = pet.load_debug_parameters()

        self.assertTrue(math.isfinite(values["pet_width"]))
        self.assertEqual(values["pet_width"], pet.DEFAULT_DEBUG_PARAMETERS["pet_width"])
        self.assertEqual(values["gravity"], pet.DEFAULT_DEBUG_PARAMETERS["gravity"])

    def test_utf8_bom_debug_parameters_are_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "debug_parameters.json")
            with open(path, "wb") as stream:
                stream.write(
                    b"\xef\xbb\xbf" + json.dumps({
                        "animation_eat_fps": 10,
                        "animation_pet_fps": 10,
                    }).encode("utf-8")
                )

            with patch.object(pet, "DEBUG_PARAMETERS_PATH", path):
                values = pet.load_debug_parameters()

        self.assertEqual(values["animation_eat_fps"], 10.0)
        self.assertEqual(values["animation_pet_fps"], 10.0)

    def test_parameter_snapshot_reports_clamped_runtime_value(self):
        self.assertTrue(self.window.set_debug_parameter("pet_width", 20))

        self.assertEqual(self.window.PET_W, 40)
        self.assertEqual(self.window.debug_parameter_value("pet_width"), 40)

    def test_geometry_physics_animation_and_decay_targets_update(self):
        self.window.set_debug_parameter("pet_height", 280)
        self.window.set_debug_parameter("dog_height", 200)
        self.window.set_debug_parameter("gravity", 900)
        self.window.set_debug_parameter("wall_bounce", 0.72)
        self.window.set_debug_parameter("walk_speed_min", 120)
        self.window.set_debug_parameter("walk_speed_max", 260)
        self.window.set_debug_parameter("animation_eat_fps", 11)
        self.window.set_debug_parameter("decay_energy", 0.2)

        self.assertEqual((self.window.PET_H, self.window.DOG_H), (280, 200))
        self.assertEqual(self.window.size().width(), self.window.PET_W)
        self.assertEqual(self.window.size().height(), self.window.PET_H)
        self.assertEqual(self.window.debug_physics["gravity"], 900)
        self.assertEqual(self.window.debug_physics["wall_bounce"], 0.72)
        self.assertEqual(
            (self.window.walk_speed_min, self.window.walk_speed_max),
            (120, 260),
        )
        self.assertEqual(self.window.animation_specs["eat"]["fps"], 11)
        self.assertEqual(self.window.settings["decay_energy"], 0.2)

    def test_shared_progression_and_minigame_targets_update(self):
        import minigames
        import progression

        original = {
            "dig_chance": progression.DIG_DISCOVERY_CHANCE,
            "dig_cooldown": progression.DIG_COOLDOWN_SECONDS,
            "pet_gain": progression.AFFECTION_ACTION_GAINS["pettings"],
            "pet_cooldown": progression.AFFECTION_ACTION_COOLDOWNS["pettings"],
            "game_duration": minigames.CoinCatchCanvas.DURATION_SECONDS,
            "target_lifetime": minigames.CoinCatchCanvas.TARGET_LIFETIME,
        }
        try:
            self.window.set_debug_parameter("dig_discovery_chance", 0.7)
            self.window.set_debug_parameter("dig_cooldown_minutes", 2)
            self.window.set_debug_parameter("petting_affection_gain", 9)
            self.window.set_debug_parameter("petting_cooldown", 1)
            self.window.set_debug_parameter("coin_catch_duration", 12)
            self.window.set_debug_parameter("coin_target_lifetime", 0.4)

            self.assertEqual(progression.DIG_DISCOVERY_CHANCE, 0.7)
            self.assertEqual(progression.DIG_COOLDOWN_SECONDS, 120)
            self.assertEqual(progression.AFFECTION_ACTION_GAINS["pettings"], 9)
            self.assertEqual(progression.AFFECTION_ACTION_COOLDOWNS["pettings"], 1)
            self.assertEqual(minigames.CoinCatchCanvas.DURATION_SECONDS, 12)
            self.assertEqual(minigames.CoinCatchCanvas.TARGET_LIFETIME, 0.4)
        finally:
            progression.DIG_DISCOVERY_CHANCE = original["dig_chance"]
            progression.DIG_COOLDOWN_SECONDS = original["dig_cooldown"]
            progression.AFFECTION_ACTION_GAINS["pettings"] = original["pet_gain"]
            progression.AFFECTION_ACTION_COOLDOWNS["pettings"] = original["pet_cooldown"]
            minigames.CoinCatchCanvas.DURATION_SECONDS = original["game_duration"]
            minigames.CoinCatchCanvas.TARGET_LIFETIME = original["target_lifetime"]

    def test_expired_feed_behavior_returns_to_idle_without_waiting_for_autonomy(self):
        self.window.check_ai_nudge = lambda: None
        self.window.behavior = "eat"
        self.window.behavior_until = time.time() - 0.1
        self.window.next_behavior_at = time.time() + 3600

        self.window.on_autonomy()

        self.assertEqual(self.window.behavior, "idle")
        self.assertEqual(self.window.pose, pet.POSE["idle"])

    def test_feed_animation_default_is_one_point_five_seconds(self):
        self.assertEqual(
            self.window.debug_parameter_defaults()["feed_animation_duration"],
            1.5,
        )


if __name__ == "__main__":
    unittest.main()
