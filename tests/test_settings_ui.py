import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton

import pet


class FakePet:
    def __init__(self):
        self.settings = dict(pet.DEFAULT_SETTINGS)
        self.applied = []
        self.messages = []

    def apply_runtime_settings(self, previous):
        self.applied.append((previous, dict(self.settings)))

    def say(self, text, _duration):
        self.messages.append(text)


class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pet = FakePet()
        self.window = pet.SettingsWindow(self.pet)

    def tearDown(self):
        self.window.close()

    def test_uses_size_dropdown_and_switches(self):
        self.assertEqual(self.window.windowTitle(), "温馨设置")
        self.assertEqual(self.window.chat_size_combo.currentData(), (640, 820))
        self.assertNotIn("chat_bubble_max", self.window.inputs)
        self.assertNotIn("decay_hunger", self.window.inputs)
        self.assertNotIn("decay_energy", self.window.inputs)
        self.assertNotIn("decay_mood", self.window.inputs)
        self.assertIsInstance(
            self.window.inputs["always_on_top"], pet.ToggleSwitch
        )
        self.assertIsInstance(
            self.window.inputs["sound_enabled"], pet.ToggleSwitch
        )
        self.assertIsInstance(
            self.window.inputs["auto_check_updates"], pet.ToggleSwitch
        )
        close_button = self.window.findChild(QPushButton, "closeButton")
        self.assertIsNotNone(close_button)
        self.assertEqual(close_button.text(), "×")

    def test_apply_updates_every_control(self):
        self.window.chat_size_combo.setCurrentIndex(0)
        self.window.inputs["chat_font_size"].setValue(18)
        self.window.inputs["always_on_top"].setChecked(False)
        self.window.inputs["needy_speak_chance"].setValue(0.3)
        with patch("pet.save_settings"):
            self.window.apply()
        self.assertEqual(self.pet.settings["chat_width"], 480)
        self.assertEqual(self.pet.settings["chat_height"], 620)
        self.assertEqual(self.pet.settings["chat_font_size"], 18)
        self.assertFalse(self.pet.settings["always_on_top"])
        self.assertAlmostEqual(self.pet.settings["needy_speak_chance"], 0.3)
        self.assertEqual(len(self.pet.applied), 1)

    def test_reset_restores_all_defaults_in_data_and_controls(self):
        self.window.chat_size_combo.setCurrentIndex(4)
        self.window.inputs["chat_font_size"].setValue(31)
        self.window.inputs["sound_enabled"].setChecked(False)
        with patch("pet.save_settings"):
            self.window.reset_defaults()
        self.assertEqual(self.pet.settings, pet.DEFAULT_SETTINGS)
        self.assertEqual(self.window.chat_size_combo.currentData(), (640, 820))
        for key, control in self.window.inputs.items():
            default = pet.DEFAULT_SETTINGS[key]
            if isinstance(control, pet.ToggleSwitch):
                self.assertEqual(control.isChecked(), bool(default))
            else:
                self.assertAlmostEqual(control.value(), default)


if __name__ == "__main__":
    unittest.main()
