import json
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication

from parameter_tuner import PARAMETER_GROUPS, ParameterTunerWindow


class FakePet:
    def __init__(self):
        keys = [key for _, definitions in PARAMETER_GROUPS for key, *_ in definitions]
        self.values = {key: 1.0 for key in keys}
        self.values["gravity"] = 2200.0
        self.defaults = dict(self.values)
        self.calls = []
        self.reject_keys = set()

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
