import json
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication

from parameter_tuner import (
    PARAMETER_EFFECT_TIMING,
    PARAMETER_GROUPS,
    ParameterTunerWindow,
)


class FakePet:
    def __init__(self):
        keys = [key for _, definitions in PARAMETER_GROUPS for key, *_ in definitions]
        self.values = {key: 1.0 for key in keys}
        self.values["gravity"] = 2200.0
        self.defaults = dict(self.values)
        self.calls = []
        self.reject_keys = set()
        self._animation_frame_paths = {}
        self.preview_calls = []

    def play_debug_animation(self, name):
        self.preview_calls.append(name)
        return name in self._animation_frame_paths

    def debug_parameter_value(self, key):
        return self.values[key]

    def debug_parameter_defaults(self):
        return self.defaults

    def set_debug_parameter(self, key, value):
        self.calls.append((key, value))
        if key in self.reject_keys:
            return False
        self.values[key] = value
        return True

    def debug_parameter_snapshot(self, keys):
        return {key: self.values[key] for key in keys}

    def save_debug_parameters(self, values):
        self.saved = values

    def current_screen_rect(self):
        return QRect(0, 0, 1400, 900)

    def geometry(self):
        return QRect(900, 600, 190, 220)


class ParameterTunerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pet = FakePet()
        self.window = ParameterTunerWindow(self.pet)

    def tearDown(self):
        self.window.close()

    def test_every_declared_parameter_has_controls(self):
        keys = [key for _, definitions in PARAMETER_GROUPS for key, *_ in definitions]
        self.assertEqual(set(keys), set(self.window.controls))

    def test_fixed_sleep_balance_settings_are_not_tunable(self):
        keys = [key for _, definitions in PARAMETER_GROUPS for key, *_ in definitions]

        for key in ("decay_hunger_sleeping", "decay_energy_sleeping_gain"):
            self.assertNotIn(key, keys)
            self.assertNotIn(key, PARAMETER_EFFECT_TIMING)

    def test_window_is_readable_and_clamps_to_available_screen(self):
        self.assertGreaterEqual(self.window.width(), 1000)
        self.assertGreaterEqual(self.window.height(), 880)

        self.window.show_near_pet()

        self.assertLessEqual(self.window.width(), 1400)
        self.assertLessEqual(self.window.height(), 900)
        self.window.close()

    def test_each_parameter_has_live_feedback(self):
        self.assertTrue(all(
            "feedback" in control
            for control in self.window.controls.values()
        ))

        self.window.controls["gravity"]["spin"].setValue(1234)

        feedback = self.window.controls["gravity"]["feedback"].text()
        self.assertIn("1234", feedback)
        self.assertIn("当前生效", feedback)

    def test_failed_application_is_reported(self):
        self.pet.reject_keys.add("gravity")

        self.window.controls["gravity"]["spin"].setValue(1234)

        self.assertIn("失败", self.window.status.text())

    def test_spin_and_slider_apply_immediately(self):
        self.window.controls["gravity"]["spin"].setValue(1234)
        self.assertEqual(self.pet.values["gravity"], 1234)
        self.window.controls["gravity"]["slider"].setValue(5)
        self.assertEqual(self.pet.calls[-1][0], "gravity")

    def test_snapshot_is_json_and_reset_restores_defaults(self):
        self.window.controls["gravity"]["spin"].setValue(1234)
        json.loads(self.window.parameter_text())
        self.window.reset_defaults()
        self.assertEqual(self.pet.values["gravity"], 2200.0)

    def test_save_passes_current_values(self):
        self.window.save_parameters()
        self.assertEqual(self.pet.saved, self.pet.values)

    def test_controls_preserve_runtime_values_below_ui_recommended_minimum(self):
        self.window.close()
        self.pet.values.update({"pet_width": 40.0, "gravity": 0.0})
        self.window = ParameterTunerWindow(self.pet)

        self.assertEqual(self.window.controls["pet_width"]["spin"].value(), 40.0)
        self.assertEqual(self.window.controls["gravity"]["spin"].value(), 0.0)
        self.assertIn("40", self.window.controls["pet_width"]["feedback"].text())
        self.assertIn("0", self.window.controls["gravity"]["feedback"].text())

    def test_failed_application_resynchronizes_controls_to_runtime_value(self):
        self.pet.reject_keys.add("gravity")

        self.window.controls["gravity"]["spin"].setValue(1234)

        control = self.window.controls["gravity"]
        self.assertEqual(control["spin"].value(), self.pet.values["gravity"])
        self.assertEqual(control["slider"].value(), round(self.pet.values["gravity"] / control["step"]))


class DebugAnimationPreviewTests(unittest.TestCase):
    """调参器动画预览（2026-10-06 用户需求：调试功能里可调用各种动画）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tuner(self, available):
        pet = FakePet()
        pet._animation_frame_paths = available
        return pet, ParameterTunerWindow(pet)

    def test_preview_section_builds_button_per_known_animation(self):
        from parameter_tuner import ANIMATION_PREVIEW_KEYS

        _pet, window = self._tuner({})
        buttons = window.preview_buttons
        keys = [key for key, _label in ANIMATION_PREVIEW_KEYS]
        self.assertEqual(sorted(buttons), sorted(keys))

    def test_only_available_animations_are_enabled(self):
        _pet, window = self._tuner({"idle": ["a"], "happy": ["b"]})
        self.assertTrue(window.preview_buttons["idle"].isEnabled())
        self.assertTrue(window.preview_buttons["happy"].isEnabled())
        self.assertFalse(window.preview_buttons["walk"].isEnabled())
        self.assertFalse(window.preview_buttons["drag"].isEnabled())

    def test_click_plays_animation_and_updates_status(self):
        pet, window = self._tuner({"idle": ["a"], "happy": ["b"]})
        window.preview_buttons["happy"].click()
        self.assertEqual(pet.preview_calls, ["happy"])
        self.assertIn("happy", window.status.text())

    def test_click_disabled_animation_does_not_call_pet(self):
        pet, window = self._tuner({"idle": ["a"]})
        button = window.preview_buttons["walk"]
        button.click()  # 禁用键不发射 clicked，防御断言零调用
        self.assertEqual(pet.preview_calls, [])

    def test_refresh_updates_availability_after_pet_switch(self):
        pet, window = self._tuner({"idle": ["a"]})
        self.assertFalse(window.preview_buttons["walk"].isEnabled())
        pet._animation_frame_paths = {"idle": ["a"], "walk": ["c"]}
        window.refresh_preview_buttons()
        self.assertTrue(window.preview_buttons["walk"].isEnabled())


class PetWindowPlayDebugAnimationTests(unittest.TestCase):
    """PetWindow.play_debug_animation：有帧才播，壳安全。"""

    def _shell(self, available=None):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        if available is not None:
            window._animation_frame_paths = available
        window.triggered = []
        window.trigger_animation = (
            lambda name, duration_ms=None, finished_callback=None:
            window.triggered.append(name)
        )
        return window

    def test_plays_available_animation(self):
        window = self._shell({"idle": ["a"], "happy": ["b"]})
        self.assertTrue(window.play_debug_animation("happy"))
        self.assertEqual(window.triggered, ["happy"])

    def test_missing_animation_returns_false_without_trigger(self):
        window = self._shell({"idle": ["a"]})
        self.assertFalse(window.play_debug_animation("walk"))
        self.assertEqual(window.triggered, [])

    def test_shell_without_paths_attribute_is_safe(self):
        window = self._shell()
        self.assertFalse(window.play_debug_animation("idle"))
        self.assertEqual(window.triggered, [])
