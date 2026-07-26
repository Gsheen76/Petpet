import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter
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

    def test_any_non_left_click_closes_bubble_canvas(self):
        fake_menu = SimpleNamespace(_close=Mock())
        event = SimpleNamespace(button=lambda: Qt.RightButton)

        pet.BubbleMenu.mousePressEvent(fake_menu, event)

        fake_menu._close.assert_called_once_with()

    def test_losing_application_focus_closes_bubble_canvas(self):
        fake_menu = SimpleNamespace(
            isVisible=Mock(return_value=True),
            _close=Mock(),
        )

        pet.BubbleMenu._on_application_state_changed(
            fake_menu, Qt.ApplicationInactive
        )

        fake_menu._close.assert_called_once_with()

    def test_click_outside_closes_bubble_canvas(self):
        fake_menu = SimpleNamespace(
            _closing=False,
            isVisible=Mock(return_value=True),
            frameGeometry=Mock(return_value=QRect(20, 20, 100, 80)),
            stat_bubble=None,
            _close=Mock(),
        )
        event = SimpleNamespace(
            type=lambda: QEvent.MouseButtonPress,
            globalPos=lambda: QPoint(300, 300),
        )
        with patch.object(QTimer, "singleShot",
                          side_effect=lambda _delay, callback: callback()):
            pet.BubbleMenu.eventFilter(fake_menu, None, event)

        fake_menu._close.assert_called_once_with()

    def test_stat_icons_are_drawn_without_emoji_fonts(self):
        image = QImage(132, 44, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        for index, kind in enumerate(("hunger", "mood", "energy")):
            pet.StatBubble._draw_stat_icon(
                painter, QRectF(index * 44 + 6, 6, 32, 32),
                kind, "#ef8fa2",
            )
        painter.end()

        colored = sum(
            1
            for y in range(image.height())
            for x in range(image.width())
            if QColor.fromRgba(image.pixel(x, y)).alpha() > 0
        )
        self.assertGreater(colored, 180)

    def test_hiding_pet_closes_all_detached_bubbles(self):
        speech = SimpleNamespace(
            _hide_timer=SimpleNamespace(stop=Mock()),
            hide=Mock(),
        )
        interactive = SimpleNamespace(close=Mock())
        menu = SimpleNamespace(_close=Mock())
        bonus = SimpleNamespace(close=Mock())
        fake_pet = SimpleNamespace(
            _speech_bubble=speech,
            _interactive_bubble=interactive,
            _bubble_menu=menu,
            _last_bonus=bonus,
        )

        pet.PetWindow.hide_overlays(fake_pet)

        speech._hide_timer.stop.assert_called_once_with()
        speech.hide.assert_called_once_with()
        interactive.close.assert_called_once_with()
        menu._close.assert_called_once_with()
        bonus.close.assert_called_once_with()
        self.assertIsNone(fake_pet._interactive_bubble)
        self.assertIsNone(fake_pet._bubble_menu)
        self.assertIsNone(fake_pet._last_bonus)

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
