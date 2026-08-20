import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication, QMenu

import pet
import progression
import decoration_renderer


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
            [
                "records", "achievements", "shop", "minigames", "settings",
                "hide", "tutorial", "back", "quit",
            ],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.MORE_ACTIONS][-2:],
            ["back", "quit"],
        )

    def test_settings_entry_requires_badge_without_api_key(self):
        with patch("pet.ai.get_api_key_source", return_value="none"):
            self.assertTrue(pet.BubbleMenu.needs_api_key_configuration())

        with patch("pet.ai.get_api_key_source", return_value="config"):
            self.assertFalse(pet.BubbleMenu.needs_api_key_configuration())

    def test_pet_surface_requires_badge_without_api_key(self):
        with patch("pet.ai.get_api_key_source", return_value="none"):
            self.assertTrue(pet.PetWindow.needs_api_key_configuration())

        with patch("pet.ai.get_api_key_source", return_value="config"):
            self.assertFalse(pet.PetWindow.needs_api_key_configuration())

    def test_pet_outside_actual_screens_is_not_visible(self):
        fake_pet = SimpleNamespace(
            geometry=lambda: QRect(2369, 1209, 190, 220),
            screen_rect=lambda: QRect(0, 0, 3000, 1600),
        )
        screen = SimpleNamespace(geometry=lambda: QRect(0, 0, 1707, 960))

        with patch("pet.QApplication.screens", return_value=[screen]):
            self.assertFalse(pet.PetWindow.is_visible_on_screen(fake_pet))

    def test_second_launch_recalls_pet_to_a_discoverable_position(self):
        fake_pet = SimpleNamespace(
            play_scene=None,
            isVisible=Mock(return_value=True),
            recall=Mock(),
            show=Mock(),
            raise_=Mock(),
            say=Mock(),
        )
        fake_tray_app = SimpleNamespace(pet=fake_pet)

        pet.TrayApp.activate_existing_instance(fake_tray_app)

        fake_pet.recall.assert_called_once_with()

    def test_update_download_starts_after_confirmation_event_finishes(self):
        fake_pet = SimpleNamespace(pet_name="测试", say=Mock())
        fake_tray = object.__new__(pet.TrayApp)
        fake_tray.pet = fake_pet
        fake_tray._update_checking = False
        fake_tray._manual_update_check = False
        update_info = {
            "status": "update",
            "version": "1.3.2",
            "asset_name": "Petpet.exe",
            "notes": "修复更新链路",
            "download_url": "https://example.invalid/Petpet.exe",
        }
        message_box = Mock()
        message_box_type = Mock(return_value=message_box)
        message_box_type.Yes = pet.QMessageBox.Yes
        message_box_type.No = pet.QMessageBox.No
        message_box_type.Information = pet.QMessageBox.Information
        message_box.exec_.return_value = message_box_type.Yes
        message_box.button.return_value = Mock()
        with patch.object(pet, "QMessageBox", message_box_type), \
                patch.object(pet.sys, "frozen", True, create=True), \
                patch.object(pet, "IS_WINDOWS", True), \
                patch.object(pet.QTimer, "singleShot") as single_shot, \
                patch.object(fake_tray, "_start_update_download") as start:
            pet.TrayApp._on_update_result(fake_tray, update_info)
            single_shot.assert_called_once()
            self.assertEqual(single_shot.call_args.args[0], 0)
            start.assert_not_called()
            single_shot.call_args.args[1]()
            start.assert_called_once_with(update_info)


    def test_right_long_press_stats_feature_is_removed(self):
        self.assertFalse(hasattr(pet.PetWindow, "open_stats"))
        self.assertFalse(hasattr(pet.TrayApp, "_on_right_long"))

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

    def test_more_canvas_opens_minigame_hub(self):
        fake_pet = SimpleNamespace(open_minigames=Mock())
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())

        pet.BubbleMenu._run_action(fake_menu, "minigames")

        fake_pet.open_minigames.assert_called_once_with()
        fake_menu._close.assert_called_once_with()

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

    def test_equipped_collar_uses_its_own_adjustable_transform(self):
        state = progression.ensure_progression({})
        progression.purchase_decoration(state, "red_collar")
        progression.equip_decoration(state, "red_collar")
        default = progression.decoration_transform(
            state, "red_collar"
        )

        changed = progression.set_decoration_transform(
            state, "red_collar", x=default["x"] + 0.05
        )

        self.assertAlmostEqual(changed["x"], default["x"] + 0.05)
        self.assertIn("red_collar", state["decoration_adjustments"])

    def test_all_three_decorations_render_as_independent_layers(self):
        state = progression.ensure_progression({"pet_coins": 1000})
        for decoration_id in (
            "cream_beret", "red_collar", "round_glasses"
        ):
            self.assertTrue(
                progression.purchase_decoration(
                    state, decoration_id
                )["ok"]
            )
            self.assertTrue(
                progression.equip_decoration(
                    state, decoration_id
                )["ok"]
            )

        image = QImage(380, 320, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        geometries = decoration_renderer.draw_equipped_idle(
            painter,
            state,
            QRectF(0, 0, 380, 320),
            decoration_renderer.load_decoration_pixmaps(),
        )
        painter.end()

        self.assertEqual(
            set(geometries),
            {"cream_beret", "red_collar", "round_glasses"},
        )
        self.assertTrue(all(
            not geometry.isEmpty() for geometry in geometries.values()
        ))

    def test_decoration_layers_cover_all_passive_idle_states(self):
        self.assertTrue(
            pet.PetWindow._show_idle_decorations(
                "idle", pet.POSE["idle"], None
            )
        )
        self.assertTrue(
            pet.PetWindow._show_idle_decorations(
                "idle", pet.POSE["close"], None
            )
        )
        self.assertTrue(
            pet.PetWindow._show_idle_decorations(
                "ask", pet.POSE["idle"], None
            )
        )
        self.assertTrue(
            pet.PetWindow._show_idle_decorations(
                "sit", pet.POSE["idle"], None
            )
        )
        self.assertFalse(
            pet.PetWindow._show_idle_decorations(
                "walk", pet.POSE["idle"], None
            )
        )
        self.assertFalse(
            pet.PetWindow._show_idle_decorations(
                "idle", pet.POSE["happy"], None
            )
        )
        self.assertFalse(
            pet.PetWindow._show_idle_decorations(
                "idle", pet.POSE["idle"], object()
            )
        )

    def test_low_mood_keeps_idle_pose_and_prefers_mood_bubble(self):
        passive = SimpleNamespace(
            state={
                "sleeping": False,
                "mood": 5,
                "hunger": 5,
            },
            dragging=False,
            behavior="idle",
            pose=pet.POSE["sad"],
        )

        pet.PetWindow.refresh_pose_from_state(passive)

        self.assertEqual(passive.pose, pet.POSE["idle"])

        bubble_host = SimpleNamespace(
            state=passive.state,
            _interactive_bubble=None,
            _last_interactive_t=0.0,
            dragging=False,
            isVisible=Mock(return_value=True),
            say=Mock(),
        )
        with patch("pet.InteractiveBubble") as bubble_type:
            pet.PetWindow.maybe_show_interactive_bubble(bubble_host)

        bubble_type.assert_called_once_with(
            bubble_host,
            "陪我玩",
            "play",
            "#75cda8",
            "",
        )
        bubble_host.say.assert_called_once()

    def test_hunger_bubble_keeps_only_the_short_action_label(self):
        bubble_host = SimpleNamespace(
            state={
                "sleeping": False,
                "mood": 80,
                "hunger": 5,
            },
            _interactive_bubble=None,
            _last_interactive_t=0.0,
            dragging=False,
            isVisible=Mock(return_value=True),
            say=Mock(),
        )
        with patch("pet.InteractiveBubble") as bubble_type:
            pet.PetWindow.maybe_show_interactive_bubble(bubble_host)

        bubble_type.assert_called_once_with(
            bubble_host,
            "喂喂我",
            "feed",
            "#f39a68",
            "",
        )

    def test_autonomous_walking_is_much_less_likely_than_idling(self):
        self.assertLessEqual(
            pet.PetWindow.AUTONOMY_WALK_WEIGHT,
            pet.PetWindow.AUTONOMY_IDLE_WEIGHT / 8,
        )

    def test_blink_never_replaces_an_active_walk_frame(self):
        walk_frame = object()

        pose, frame = pet.PetWindow._apply_blink_frame(
            True, pet.POSE["idle"], walk_frame
        )

        self.assertEqual(pose, pet.POSE["idle"])
        self.assertIs(frame, walk_frame)

    def test_independent_decoration_assets_are_transparent_pngs(self):
        for definition in progression.DECORATION_DEFINITIONS.values():
            path = os.path.join(
                decoration_renderer.DECORATIONS_DIR,
                definition["asset"],
            )
            image = QImage(path)
            self.assertFalse(image.isNull(), definition["asset"])
            self.assertTrue(
                image.hasAlphaChannel(), definition["asset"]
            )
            self.assertGreater(image.width(), 500, definition["asset"])

    def test_hiding_pet_closes_all_detached_bubbles(self):
        speech = SimpleNamespace(
            clear_messages=Mock(),
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

        speech.clear_messages.assert_called_once_with()
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
