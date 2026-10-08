# -*- coding: utf-8 -*-
"""套装互动动画装备感知路由（2026-10-09 恐龙套装全动作）。"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from petpet.progression import core as progression
from petpet.app.pet_window import PetWindow


def _state(equipped="dinosaur_suit"):
    return {
        "pets": {"lunch_meat": {}},
        "owned_pet_ids": ["lunch_meat"],
        "active_pet_id": "lunch_meat",
        "owned_outfits": ["dinosaur_suit"],
        "equipped_outfit": equipped,
    }


class OutfitActionVariantTests(unittest.TestCase):
    def test_dinosaur_action_animations_declared(self):
        d = progression.OUTFIT_DEFINITIONS["dinosaur_suit"]
        self.assertEqual(
            d["action_animations"],
            {"pet": "pet_dinosaur", "eat": "eat_dinosaur",
             "play": "play_dinosaur", "dig_reward": "dig_dinosaur",
             "happy": "happy_dinosaur", "sleep": "sleep_dinosaur"},
        )

    def test_helper_returns_variant_when_equipped(self):
        self.assertEqual(
            progression.equipped_outfit_action_animation(_state(), "pet"),
            "pet_dinosaur",
        )

    def test_helper_returns_none_without_outfit(self):
        self.assertIsNone(
            progression.equipped_outfit_action_animation(_state(None), "pet")
        )

    def test_helper_returns_none_for_unknown_action(self):
        self.assertIsNone(
            progression.equipped_outfit_action_animation(_state(), "dance")
        )

    def test_window_variant_requires_frames_loaded(self):
        w = PetWindow.__new__(PetWindow)
        w.state = _state()
        w.__dict__["animation_frames"] = {}
        w.__dict__["_animation_frame_paths"] = {"pet_dinosaur": ["x"]}
        self.assertEqual(w._outfit_action_variant("pet"), "pet_dinosaur")
        self.assertIsNone(w._outfit_action_variant("eat"))  # 帧缺失回落素狗

    def test_sleep_state_routes_to_outfit_variant(self):
        w = PetWindow.__new__(PetWindow)
        w.state = _state()
        w.state["sleeping"] = True
        w._animation_override = None
        w.dragging = False
        w.behavior = "idle"
        w.__dict__["animation_frames"] = {"sleep_dinosaur": [object()]}
        w.__dict__["_animation_frame_paths"] = {}
        self.assertEqual(w._current_animation_name(), "sleep_dinosaur")

    def test_trigger_animation_swaps_in_outfit_variant(self):
        w = PetWindow.__new__(PetWindow)
        w.state = _state()
        w.__dict__["animation_frames"] = {"pet_dinosaur": [object()] * 24}
        w.__dict__["_animation_frame_paths"] = {}
        w.animation_specs = {"pet_dinosaur": {"fps": 8, "loop": False,
                                              "frame_durations_ms": [110.0] * 24}}
        w._animation_override = None
        w._animation_override_token = 0
        w._active_animation = None
        w._animation_started_at = 0.0
        w.refresh_pose_from_state = lambda: None
        w.update = lambda: None

        import petpet.app.pet_window as pw
        with unittest.mock.patch.object(pw.time, "monotonic", return_value=1.0):
            w.trigger_animation("pet")
        self.assertEqual(w._animation_override, "pet_dinosaur")


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
