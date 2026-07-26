import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFrame, QPushButton

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
        self.assertGreaterEqual(
            self.window.width(), pet.SettingsWindow.COMPACT_MIN_WIDTH
        )
        self.assertGreaterEqual(
            self.window.height(), pet.SettingsWindow.COMPACT_MIN_HEIGHT
        )
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
        self.assertEqual(close_button.cursor().shape(), Qt.PointingHandCursor)
        title_bar = self.window.findChild(QFrame, "settingsTitleBar")
        self.assertIsNotNone(title_bar)
        self.assertEqual(title_bar.cursor().shape(), Qt.ArrowCursor)

    def test_settings_font_value_twenty_preserves_previous_visual_size(self):
        self.assertEqual(pet.DEFAULT_SETTINGS["ui_font_size"], 24)
        self.assertEqual(pet.settings_font_px(20), 22)
        field = next(item for item in pet.SettingsWindow.FIELDS
                     if item[0] == "ui_font_size")
        self.assertEqual(field[2:4], (20, 40))

    def test_settings_window_is_twenty_percent_larger(self):
        self.assertEqual(pet.SettingsWindow.PREFERRED_WIDTH, 840)
        self.assertEqual(pet.SettingsWindow.PREFERRED_HEIGHT, 960)
        self.assertEqual(pet.SettingsWindow.COMPACT_MIN_WIDTH, 648)
        self.assertEqual(pet.SettingsWindow.COMPACT_MIN_HEIGHT, 708)

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
