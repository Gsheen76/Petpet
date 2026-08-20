import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QSlider

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
        for key in (
            "remind_drink_min", "remind_rest_min", "remind_stand_min",
            "needy_speak_chance", "ask_weight_normal", "ask_weight_needy",
            "nudge_idle_min", "nudge_gap_min",
        ):
            self.assertNotIn(key, self.window.inputs)
        self.assertIsInstance(
            self.window.inputs["health_level"], pet.ThreeLevelSlider
        )
        self.assertIsInstance(
            self.window.inputs["personality_level"], pet.ThreeLevelSlider
        )
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

    def test_health_presets_have_three_confirmed_levels(self):
        self.assertEqual(
            pet.SettingsWindow.HEALTH_PRESETS,
            (
                {"remind_drink_min": 120, "remind_rest_min": 180,
                 "remind_stand_min": 90},
                {"remind_drink_min": 60, "remind_rest_min": 90,
                 "remind_stand_min": 45},
                {"remind_drink_min": 40, "remind_rest_min": 60,
                 "remind_stand_min": 30},
            ),
        )

    def test_personality_presets_keep_default_in_the_middle(self):
        presets = pet.SettingsWindow.PERSONALITY_PRESETS
        self.assertEqual(len(presets), 3)
        for key in (
            "needy_speak_chance", "ask_weight_normal", "ask_weight_needy",
            "nudge_idle_min", "nudge_gap_min",
        ):
            self.assertEqual(presets[1][key], pet.DEFAULT_SETTINGS[key])
        self.assertEqual(presets[0]["nudge_idle_min"], 3600)
        self.assertEqual(presets[0]["nudge_gap_min"], 21600)
        self.assertEqual(presets[2]["nudge_idle_min"], 900)
        self.assertEqual(presets[2]["nudge_gap_min"], 3600)

    def test_nearest_preset_maps_old_values_to_closest_level(self):
        self.pet.settings.update({
            "remind_drink_min": 45,
            "remind_rest_min": 65,
            "remind_stand_min": 35,
        })
        window = pet.SettingsWindow(self.pet)
        self.addCleanup(window.close)

        self.assertEqual(window._nearest_preset_index(
            ("remind_drink_min", "remind_rest_min", "remind_stand_min"),
            window.HEALTH_PRESETS,
        ), 2)

    def test_nearest_preset_uses_the_same_scale_for_every_candidate(self):
        self.pet.settings.update({
            "remind_drink_min": 80,
            "remind_rest_min": 120,
            "remind_stand_min": 60,
        })
        window = pet.SettingsWindow(self.pet)
        self.addCleanup(window.close)

        self.assertEqual(window._nearest_preset_index(
            ("remind_drink_min", "remind_rest_min", "remind_stand_min"),
            window.HEALTH_PRESETS,
        ), 1)

    def test_three_level_slider_has_only_three_snap_positions(self):
        control = pet.ThreeLevelSlider(("文静", "适中", "活泼"))
        self.addCleanup(control.close)
        slider = control.findChild(QSlider, "threeLevelSlider")

        self.assertIsNotNone(slider)
        self.assertEqual((slider.minimum(), slider.maximum()), (0, 2))
        control.setValue(99)
        self.assertEqual(control.value(), 2)
        control.setValue(-5)
        self.assertEqual(control.value(), 0)
        self.assertEqual(
            [button.text() for button in control.level_buttons],
            ["文静", "适中", "活泼"],
        )
        self.assertTrue(all(
            button.objectName() == "threeLevelOption"
            for button in control.level_buttons
        ))

    def test_apply_updates_every_control(self):
        self.window.chat_size_combo.setCurrentIndex(0)
        self.window.inputs["chat_font_size"].setValue(18)
        self.window.inputs["always_on_top"].setChecked(False)
        self.window.inputs["health_level"].setValue(2)
        self.window.inputs["personality_level"].setValue(2)
        with patch("petpet.ui.settings.save_settings"):
            self.window.apply()
        self.assertEqual(self.pet.settings["chat_width"], 480)
        self.assertEqual(self.pet.settings["chat_height"], 620)
        self.assertEqual(self.pet.settings["chat_font_size"], 18)
        self.assertFalse(self.pet.settings["always_on_top"])
        for key, value in self.window.HEALTH_PRESETS[2].items():
            self.assertEqual(self.pet.settings[key], value)
        for key, value in self.window.PERSONALITY_PRESETS[2].items():
            self.assertEqual(self.pet.settings[key], value)
        self.assertEqual(len(self.pet.applied), 1)

    def test_reset_restores_all_defaults_in_data_and_controls(self):
        self.window.chat_size_combo.setCurrentIndex(4)
        self.window.inputs["chat_font_size"].setValue(31)
        self.window.inputs["sound_enabled"].setChecked(False)
        self.window.inputs["health_level"].setValue(0)
        self.window.inputs["personality_level"].setValue(2)
        with patch("petpet.ui.settings.save_settings"):
            self.window.reset_defaults()
        self.assertEqual(self.pet.settings, pet.DEFAULT_SETTINGS)
        self.assertEqual(self.window.chat_size_combo.currentData(), (640, 820))
        self.assertEqual(self.window.inputs["health_level"].value(), 1)
        self.assertEqual(self.window.inputs["personality_level"].value(), 1)
        for key, control in self.window.inputs.items():
            if key in {"health_level", "personality_level"}:
                continue
            default = pet.DEFAULT_SETTINGS[key]
            if isinstance(control, pet.ToggleSwitch):
                self.assertEqual(control.isChecked(), bool(default))
            else:
                self.assertAlmostEqual(control.value(), default)

    def test_settings_window_uses_real_rounded_card_and_transparent_corners(self):
        self.assertTrue(self.window.testAttribute(Qt.WA_TranslucentBackground))
        self.assertIsNotNone(self.window.findChild(QFrame, "settingsCard"))
        self.window.show()
        QApplication.processEvents()
        image = self.window.grab().toImage().convertToFormat(QImage.Format_ARGB32)
        for point in ((0, 0), (image.width() - 1, 0),
                      (0, image.height() - 1),
                      (image.width() - 1, image.height() - 1)):
            self.assertEqual(image.pixelColor(*point).alpha(), 0)

    def test_settings_typography_uses_crisp_pixel_hierarchy(self):
        title = self.window.findChild(QLabel, "settingsTitle")
        subtitle = self.window.findChild(QLabel, "settingsSubtitle")
        group_titles = self.window.findChildren(QLabel, "settingsGroupTitle")
        self.assertEqual(title.font().pixelSize(), 31)
        self.assertEqual(subtitle.font().pixelSize(), 20)
        self.assertTrue(group_titles)
        self.assertTrue(all(label.font().pixelSize() == 25
                            for label in group_titles))
        self.assertEqual(self.window.font().pixelSize(), 23)

    def test_settings_font_control_scales_the_whole_pixel_hierarchy(self):
        self.window.inputs["ui_font_size"].setValue(30)
        with patch("petpet.ui.settings.save_settings"):
            self.window.apply()

        title = self.window.findChild(QLabel, "settingsTitle")
        subtitle = self.window.findChild(QLabel, "settingsSubtitle")
        group = self.window.findChildren(QLabel, "settingsGroupTitle")[0]
        self.assertEqual(title.font().pixelSize(), 39)
        self.assertEqual(group.font().pixelSize(), 31)
        self.assertEqual(subtitle.font().pixelSize(), 25)


if __name__ == "__main__":
    unittest.main()
