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


def test_shake_wake_during_asleep_drag_plays_wake_anim_first():
    """拖拽中摇醒(2026-10-25 用户令):三段式宠物先播起床动画再进 drag。"""
    from unittest.mock import Mock

    from PyQt5.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    window = PetWindow.__new__(PetWindow)
    window.state = {"sleeping": True, "sleep_mode": "manual"}
    window.dragging = False
    window.dragging = True
    window._wake_shake = Mock()
    window._current_pet_id = "lunch_meat"
    window.__dict__["_drag_anim_state"] = None
    window.__dict__["_dragging_asleep"] = True
    window.__dict__["_animation_frame_paths"] = {"sleep_wake": ["p"]}
    window.__dict__["animation_frames"] = {}
    window.trigger_animation = Mock()
    window._animation_override = None
    window._active_animation = None
    window._animation_override_token = 0
    window.say = Mock()
    window.play_sound = Mock()
    window.update = Mock()
    window._outfit_action_variant = Mock(return_value=None)

    class _Dep:
        def __call__(self, name):
            return lambda *a, **k: None

    from petpet.app import pet_window as pw
    original = pw._dependency

    def _fake_dep(name):
        if name == "save_state":
            return lambda st: None
        if name == "QTimer":
            qtimer = Mock()
            qtimer.singleShot = lambda *a, **k: None
            return qtimer
        if name == "POSE":
            return {"idle": 0, "drag": 1}
        if name == "sounds":
            return Mock()
        return original(name)

    pw._dependency = _fake_dep
    try:
        result = window.wake_from_shake()
    finally:
        pw._dependency = original
    assert result is not False
    assert window.state["sleeping"] is False
    window.trigger_animation.assert_called_once_with("sleep_wake")
    assert window.behavior == "drag"
