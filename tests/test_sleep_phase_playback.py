"""三段式睡眠播放(2026-10-25):manifest 键+状态门映射钉行为。"""

import json
import os
import unittest

from petpet.app import pet_window as pw
from petpet.app.pet_window import PetWindow


class SleepPhaseTests(unittest.TestCase):
    def test_lunch_new_manifest_has_three_phase_keys(self):
        path = os.path.join(
            "assets", "runtime", "pets", "lunch_meat",
            "desktop_new", "animations", "manifest.json")
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(
            set(manifest["sleep_fall"]["frame_durations_ms"]), {125})
        self.assertTrue(len(manifest["sleep_fall"]["frame_durations_ms"]) == 8)
        self.assertFalse(manifest["sleep_fall"]["loop"])
        self.assertEqual(len(manifest["sleep_loop"]["frame_durations_ms"]), 16)
        self.assertTrue(manifest["sleep_loop"]["loop"])
        self.assertEqual(len(manifest["sleep_wake"]["frame_durations_ms"]), 8)
        self.assertFalse(manifest["sleep_wake"]["loop"])
        self.assertNotIn("sleep", manifest)

    def _shell(self):
        window = PetWindow.__new__(PetWindow)
        window.state = {"sleeping": True}
        window.dragging = False
        window.behavior = "idle"
        window._animation_override = None
        return window

    def test_gate_prefers_sleep_loop_when_loaded(self):
        window = self._shell()
        window._animation_frame_paths = {"sleep_loop": ["p"]}
        window.animation_frames = {}
        self.assertEqual(window._current_animation_name(), "sleep_loop")

    def test_gate_falls_back_to_plain_sleep(self):
        window = self._shell()
        window._animation_frame_paths = {"sleep": ["p"]}
        window.animation_frames = {}
        self.assertEqual(window._current_animation_name(), "sleep")


if __name__ == "__main__":
    unittest.main()
