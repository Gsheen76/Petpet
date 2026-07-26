import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMenu

import pet


class FakePet:
    def chat(self):
        pass

    def feed(self):
        pass

    def play(self):
        pass

    def toggle_sleep(self):
        pass

    def recall(self):
        pass

    def open_settings(self):
        pass


class MenuUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tray_harness(self):
        tray = object.__new__(pet.TrayApp)
        tray.state = {"autostart": False}
        tray.pet = FakePet()
        return tray

    def test_primary_and_more_bubble_actions(self):
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.PRIMARY_ACTIONS],
            ["chat", "feed", "play", "sleep", "more"],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.MORE_ACTIONS],
            ["settings", "hide", "tutorial", "back", "quit"],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.MORE_ACTIONS][-2:],
            ["back", "quit"],
        )

    def test_more_replaces_primary_canvas(self):
        fake_pet = SimpleNamespace(_bubble_menu=None)
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())
        run_action = pet.BubbleMenu._run_action
        with patch("pet.BubbleMenu") as menu_type:
            run_action(fake_menu, "more")
        fake_menu._close.assert_called_once_with()
        menu_type.assert_called_once_with(fake_pet, page="more")
        self.assertIs(fake_pet._bubble_menu, menu_type.return_value)

    def test_back_restores_primary_canvas(self):
        fake_pet = SimpleNamespace(_bubble_menu=None)
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())
        run_action = pet.BubbleMenu._run_action
        with patch("pet.BubbleMenu") as menu_type:
            run_action(fake_menu, "back")
        fake_menu._close.assert_called_once_with()
        menu_type.assert_called_once_with(fake_pet, page="primary")
        self.assertIs(fake_pet._bubble_menu, menu_type.return_value)

    def test_more_canvas_forwards_app_actions(self):
        callback = Mock()
        fake_pet = SimpleNamespace(_app_action_cb=callback)
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())
        pet.BubbleMenu._run_action(fake_menu, "hide")
        fake_menu._close.assert_called_once_with()
        callback.assert_called_once_with("hide")

    def test_tray_omits_status_and_data_folder(self):
        tray = self._tray_harness()
        menu = QMenu()
        with patch("pet.IS_FROZEN", True):
            pet.TrayApp._populate_menu(tray, menu, include_status=False)
        labels = [action.text() for action in menu.actions()]
        self.assertNotIn("📊 状态页", labels)
        self.assertNotIn("📁 打开数据文件夹", labels)
        self.assertFalse(any("调试" in label for label in labels))

    def test_tray_menu_uses_larger_layout_and_font(self):
        self.assertIn("min-width:310px", pet.WARM_MENU_STYLE)
        self.assertIn("font-size:17px", pet.WARM_MENU_STYLE)
        self.assertIn("padding:12px 40px 12px 18px", pet.WARM_MENU_STYLE)

    def test_debug_menu_is_local_source_only(self):
        tray = self._tray_harness()
        menu = QMenu()
        with patch("pet.IS_FROZEN", False):
            pet.TrayApp._populate_menu(tray, menu, include_status=False)
        labels = [action.text() for action in menu.actions()]
        self.assertTrue(any("调试" in label for label in labels))


if __name__ == "__main__":
    unittest.main()
