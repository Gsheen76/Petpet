import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QImage, QPainter
from PyQt5.QtWidgets import QApplication, QLabel, QMenu

import pet
import progression
import decoration_renderer
from petpet.ui import desktop as desktop_ui


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

    def test_overlay_position_helper_skips_unchanged_native_moves(self):
        widget = Mock()
        widget.pos.return_value = QPoint(120, 240)

        desktop_ui.move_window_if_needed(widget, 120, 240)
        widget.move.assert_not_called()

        desktop_ui.move_window_if_needed(widget, 121, 240)
        widget.move.assert_called_once_with(121, 240)

    def test_primary_and_more_bubble_actions(self):
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.PRIMARY_ACTIONS],
            ["chat", "home", "shop", "interaction", "more"],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.MORE_ACTIONS],
            [
                "records", "achievements", "minigames", "settings",
                "hide", "tutorial", "back", "quit",
            ],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.MORE_ACTIONS][-2:],
            ["back", "quit"],
        )
        self.assertEqual(
            [action for _, _, action, _ in pet.BubbleMenu.INTERACTION_ACTIONS],
            ["pet", "feed", "play", "sleep"],
        )
        self.assertEqual(pet.BubbleMenu.PAGE_COLUMNS["more"], 5)
        self.assertEqual(pet.BubbleMenu.PAGE_COLUMNS["interaction"], 4)

    def test_chat_entry_requires_badge_until_personal_setup_is_seen(self):
        with patch("pet.ai.needs_personal_setup_reminder", return_value=True):
            self.assertTrue(pet.BubbleMenu.needs_api_key_configuration())

        with patch("pet.ai.needs_personal_setup_reminder", return_value=False):
            self.assertFalse(pet.BubbleMenu.needs_api_key_configuration())

    def test_api_reminder_targets_chat_and_never_settings(self):
        self.assertTrue(pet.BubbleMenu.action_needs_attention(
            "chat", has_claimable=False, needs_personal_setup=True
        ))
        self.assertFalse(pet.BubbleMenu.action_needs_attention(
            "settings", has_claimable=False, needs_personal_setup=True
        ))

    def test_zero_stat_attention_marks_interaction_and_restoring_actions(self):
        zero_actions = {"pet", "feed", "play", "sleep"}
        for action in zero_actions | {"interaction"}:
            self.assertTrue(pet.BubbleMenu.action_needs_attention(
                action,
                has_claimable=False,
                needs_personal_setup=False,
                zero_actions=zero_actions,
            ))
        self.assertFalse(pet.BubbleMenu.action_needs_attention(
            "chat",
            has_claimable=False,
            needs_personal_setup=False,
            zero_actions=zero_actions,
        ))

    def test_desktop_pet_attention_uses_zero_attributes(self):
        host = SimpleNamespace(state={"hunger": 10, "mood": 0, "energy": 10})
        self.assertTrue(pet.PetWindow.pet_needs_stat_attention(host))
        host.state["mood"] = 1
        self.assertFalse(pet.PetWindow.pet_needs_stat_attention(host))

    def test_pet_surface_requires_badge_until_personal_setup_is_seen(self):
        with patch("pet.ai.needs_personal_setup_reminder", return_value=True):
            self.assertTrue(pet.PetWindow.needs_api_key_configuration())

        with patch("pet.ai.needs_personal_setup_reminder", return_value=False):
            self.assertFalse(pet.PetWindow.needs_api_key_configuration())

    def test_interface_anchor_uses_home_pet_while_home_is_visible(self):
        home_rect = QRect(1100, 620, 140, 126)
        home = SimpleNamespace(home_pet_global_rect=lambda: home_rect)
        harness = SimpleNamespace(
            _active_home_interface=lambda: home,
            geometry=lambda: QRect(20, 30, 190, 220),
            isVisible=lambda: False,
        )

        self.assertEqual(pet.PetWindow.interface_anchor_rect(harness), home_rect)
        self.assertTrue(pet.PetWindow.interface_anchor_visible(harness))

    def test_active_home_interface_requires_visible_non_decorating_pet(self):
        home = SimpleNamespace(
            isVisible=lambda: True,
            is_decorating=lambda: False,
            home_pet_visible=lambda: True,
        )
        harness = SimpleNamespace(home_scene_window=home)

        self.assertIs(pet.PetWindow._active_home_interface(harness), home)
        home.is_decorating = lambda: True
        self.assertIsNone(pet.PetWindow._active_home_interface(harness))

    def test_interface_anchor_falls_back_to_visible_desktop_pet(self):
        desktop = QRect(20, 30, 190, 220)
        harness = SimpleNamespace(
            _active_home_interface=lambda: None,
            geometry=lambda: desktop,
            isVisible=lambda: True,
        )

        self.assertEqual(pet.PetWindow.interface_anchor_rect(harness), desktop)
        self.assertTrue(pet.PetWindow.interface_anchor_visible(harness))

    def test_interface_window_position_prefers_space_beside_anchor(self):
        harness = SimpleNamespace(
            interface_anchor_rect=lambda: QRect(900, 500, 120, 100),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )

        point = pet.PetWindow.interface_window_position(
            harness,
            QSize(500, 700),
            gap=16,
        )

        self.assertEqual(point, QPoint(1035, 199))

    def test_open_bubble_menu_closes_old_menu_before_replacement(self):
        old = SimpleNamespace(_close=Mock())
        harness = SimpleNamespace(_bubble_menu=old)

        with patch("pet.BubbleMenu") as menu_type:
            pet.PetWindow.open_bubble_menu(harness)

        old._close.assert_called_once_with()
        self.assertIs(harness._bubble_menu, menu_type.return_value)

    def test_open_home_scene_is_idempotent_while_already_visible(self):
        scene = SimpleNamespace(
            isVisible=lambda: True,
            raise_=Mock(),
            show_scene=Mock(),
        )
        harness = SimpleNamespace(home_scene_window=scene)

        pet.PetWindow.open_home_scene(harness)

        scene.raise_.assert_called_once_with()
        scene.show_scene.assert_not_called()

    def test_toggle_sleep_delegates_to_active_home(self):
        home = SimpleNamespace(toggle_home_sleep=Mock(return_value=True))
        harness = SimpleNamespace(_active_home_interface=lambda: home)

        pet.PetWindow.toggle_sleep(harness)

        home.toggle_home_sleep.assert_called_once_with()

    def test_bubble_and_stat_menu_place_from_interface_anchor(self):
        anchor = QRect(1100, 620, 140, 126)
        screen = QRect(0, 0, 1920, 1080)
        pet_host = SimpleNamespace(
            interface_anchor_rect=lambda: anchor,
            interface_screen_rect=lambda: screen,
        )
        menu = SimpleNamespace(pet=pet_host, W=590, H=112, move=Mock())

        pet.BubbleMenu._place(menu)

        menu.move.assert_called_once_with(874, 527)

        stats = SimpleNamespace(
            pet=pet_host,
            width=lambda: 620,
            height=lambda: 416,
            move=Mock(),
        )

        pet.StatBubble._place(stats)

        stats.move.assert_called_once_with(859, 92)

    def test_say_uses_visible_home_interface_when_desktop_pet_is_hidden(self):
        speech = SimpleNamespace(isVisible=lambda: True, show_text=Mock())
        harness = SimpleNamespace(
            interface_anchor_visible=lambda: True,
            isVisible=lambda: False,
            _speech_bubble=speech,
        )

        pet.PetWindow.say(harness, "我在小屋里", 2200)

        speech.show_text.assert_called_once_with("我在小屋里", 2200)

    def test_speech_bubble_geometry_uses_interface_anchor(self):
        anchor = QRect(1100, 620, 140, 126)
        host = SimpleNamespace(
            interface_anchor_rect=lambda: anchor,
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        bubble = SimpleNamespace(pet=host)

        rect = pet.SpeechBubble._bubble_geometry(bubble, 260, 90)

        self.assertEqual(rect, QRect(1039, 589, 260, 90))
        self.assertLess(rect.bottom(), anchor.bottom())

    def test_interactive_bubble_places_beside_interface_anchor(self):
        host = SimpleNamespace(
            interface_anchor_rect=lambda: QRect(100, 200, 120, 100),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        bubble = SimpleNamespace(
            pet=host,
            width=lambda: 160,
            height=lambda: 70,
            move=Mock(),
        )

        pet.InteractiveBubble._place_above_pet(bubble)

        bubble.move.assert_called_once_with(215, 229)
        self.assertTrue(bubble._tail_on_left)

    def test_bonus_origin_uses_interface_anchor_in_home(self):
        harness = SimpleNamespace(
            interface_anchor_rect=lambda: QRect(1100, 620, 140, 126),
        )

        self.assertEqual(
            pet.PetWindow.interface_bonus_origin(harness, -10),
            (1169, 610),
        )

    def test_chat_uses_interface_window_position_and_settings_is_centered(self):
        position = QPoint(880, 240)
        pet_host = SimpleNamespace(
            settings=dict(pet.DEFAULT_SETTINGS),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            interface_window_position=Mock(return_value=position),
        )
        chat = SimpleNamespace(
            pet=pet_host,
            s=pet_host.settings,
            width=lambda: 560,
            height=lambda: 720,
            size=lambda: QSize(560, 720),
            setFixedSize=Mock(),
            move=Mock(),
            show=Mock(),
            raise_=Mock(),
            activateWindow=Mock(),
            input=SimpleNamespace(setFocus=Mock()),
        )

        pet.ChatWindow.show_near_pet(chat)

        chat.move.assert_called_once_with(position)

        settings = SimpleNamespace(
            pet=pet_host,
            size=lambda: QSize(840, 960),
            move=Mock(),
            show=Mock(),
            raise_=Mock(),
            activateWindow=Mock(),
        )

        pet.SettingsWindow.show_near_pet(settings)

        settings.move.assert_called_once_with(QPoint(540, 60))

    def test_tutorial_is_centered_on_the_pet_screen(self):
        pet_host = SimpleNamespace(
            pet_name=pet.ai.DEFAULT_PET_NAME,
            state={"tutorial_completed": False},
            interface_screen_rect=Mock(return_value=QRect(0, 0, 1920, 1080)),
        )
        tutorial = pet.TutorialWindow(pet_host, Mock())
        self.addCleanup(tutorial.close)

        tutorial.start()

        self.assertEqual(tutorial.pos(), QPoint(590, 230))
        pet_host.interface_screen_rect.assert_called_once_with()

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

    def test_interaction_replaces_primary_canvas_with_interaction_actions(self):
        fake_pet = SimpleNamespace(_bubble_menu=None)
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())
        run_action = pet.BubbleMenu._run_action
        with patch("pet.BubbleMenu") as menu_type:
            run_action(fake_menu, "interaction")
        fake_menu._close.assert_called_once_with()
        menu_type.assert_called_once_with(fake_pet, page="interaction")
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

    def test_primary_canvas_opens_home_scene(self):
        fake_pet = SimpleNamespace(open_home_scene=Mock())
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())

        pet.BubbleMenu._run_action(fake_menu, "home")

        fake_pet.open_home_scene.assert_called_once_with()
        fake_menu._close.assert_called_once_with()

    def test_desktop_auto_sleep_does_not_change_shared_state_in_home_scene(self):
        wake = Mock()
        harness = SimpleNamespace(
            home_scene_window=SimpleNamespace(isVisible=lambda: True),
            state={"sleeping": True, "sleep_mode": "auto", "energy": 100.0},
            auto_wake_energy_threshold=80.0,
            AUTO_WAKE_ENERGY_THRESHOLD=80.0,
            _auto_sleep_phase="sleeping",
            _wake_from_auto_sleep=wake,
        )

        result = pet.PetWindow._update_auto_sleep_state(harness, now=10.0)

        self.assertEqual(result, "home")
        self.assertTrue(harness.state["sleeping"])
        wake.assert_not_called()

    def test_desktop_tick_returns_before_screen_physics_in_home_scene(self):
        screen_lookup = Mock(side_effect=AssertionError("desktop physics ran"))
        harness = SimpleNamespace(
            home_scene_window=SimpleNamespace(isVisible=lambda: True),
            current_screen_rect=screen_lookup,
        )

        pet.PetWindow.on_tick(harness)

        screen_lookup.assert_not_called()

    def test_open_home_scene_does_not_create_desktop_speech_overlay(self):
        scene = Mock()
        harness = SimpleNamespace(
            state={},
            home_scene_window=None,
            vx=5,
            vy=6,
            on_ground=False,
            say=Mock(),
        )
        with patch.object(pet, "HomeSceneWindow", return_value=scene):
            pet.PetWindow.open_home_scene(harness)

        scene.show_scene.assert_called_once_with()
        harness.say.assert_not_called()

    def test_interaction_canvas_dispatches_petting(self):
        fake_pet = SimpleNamespace(pet_click=Mock())
        fake_menu = SimpleNamespace(pet=fake_pet, _close=Mock())

        pet.BubbleMenu._run_action(fake_menu, "pet")

        fake_pet.pet_click.assert_called_once_with()
        fake_menu._close.assert_called_once_with()

    def test_double_clicking_pet_opens_home_instead_of_chat(self):
        app = object.__new__(pet.TrayApp)
        app.pet = SimpleNamespace(
            open_home_scene=Mock(),
            chat=Mock(),
            mouseReleaseEvent_orig=Mock(),
        )
        app._press_button = "left"
        app._press_pos = QPoint(50, 50)
        app._press_t = time.time() - 0.1
        app._last_left_click_t = time.time() - 0.1
        app._pending_single_click = Mock()
        event = SimpleNamespace(
            button=lambda: Qt.LeftButton,
            globalPos=lambda: QPoint(50, 50),
        )

        app._wrap_release(event)

        app.pet.open_home_scene.assert_called_once_with()
        app.pet.chat.assert_not_called()

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

    def test_clicking_attribute_card_does_not_close_bubble_canvas(self):
        fake_menu = SimpleNamespace(
            _closing=False,
            isVisible=Mock(return_value=True),
            frameGeometry=Mock(return_value=QRect(20, 500, 100, 80)),
            stat_bubble=SimpleNamespace(
                isVisible=Mock(return_value=True),
                frameGeometry=Mock(return_value=QRect(20, 20, 620, 416)),
            ),
            _close=Mock(),
        )
        event = SimpleNamespace(
            type=lambda: QEvent.MouseButtonPress,
            globalPos=lambda: QPoint(340, 45),
        )

        pet.BubbleMenu.eventFilter(fake_menu, None, event)

        fake_menu._close.assert_not_called()

    def test_primary_bubble_uses_custom_outside_click_handling(self):
        host = SimpleNamespace(
            state=progression.ensure_progression({}),
            pet_name="烟花",
            interface_anchor_rect=lambda: QRect(900, 700, 190, 220),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            set_pet_name=Mock(),
        )
        menu = pet.BubbleMenu(host)
        self.addCleanup(menu._close)

        self.assertNotEqual(menu.windowType(), Qt.Popup)

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

    def test_status_card_companionship_copy_omits_ordinal_marker(self):
        self.assertEqual(
            pet.StatBubble.companionship_text(18),
            "♡ 陪伴 18 天",
        )

    def test_name_editor_applies_a_new_pet_name(self):
        saved_names = []
        dialog = pet.PetNameEditDialog("烟花", saved_names.append)
        self.addCleanup(dialog.close)
        dialog.name_input.setText("团子")

        dialog._apply()

        self.assertEqual(saved_names, ["团子"])

    def test_name_editor_limits_input_to_six_characters(self):
        dialog = pet.PetNameEditDialog("烟花", Mock())
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.name_input.maxLength(), 6)
        hints = [
            label.text() for label in dialog.findChildren(QLabel)
        ]
        self.assertIn("最多 6 个字符", hints)

    def test_status_header_keeps_title_edit_and_badges_separate(self):
        bubble = SimpleNamespace(
            width=lambda: 620,
            pet=SimpleNamespace(pet_name="十二个字的小狗名字"),
        )

        rects = pet.StatBubble.header_rects(bubble)

        self.assertLess(rects["title"].right(), rects["edit"].left())
        self.assertLess(rects["edit"].right(), rects["coin"].left())
        self.assertLess(rects["coin"].right(), rects["days"].left())
        expected_font = pet.pixel_font(9, QFont.Bold)
        self.assertEqual(
            pet.StatBubble.header_badge_font().pixelSize(),
            expected_font.pixelSize(),
        )

    def test_name_editor_centers_on_requested_screen(self):
        dialog = pet.PetNameEditDialog("烟花", Mock())
        self.addCleanup(dialog.close)
        screen = QRect(100, 50, 1200, 800)

        dialog.center_on_screen(screen)

        self.assertEqual(dialog.frameGeometry().center(), screen.center())

    def test_name_editor_clicks_are_inside_primary_bubble_canvas(self):
        host = SimpleNamespace(
            state=progression.ensure_progression({}),
            pet_name="烟花",
            interface_anchor_rect=lambda: QRect(900, 700, 190, 220),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            set_pet_name=Mock(),
        )
        menu = pet.BubbleMenu(host)
        self.addCleanup(menu._close)
        dialog = pet.PetNameEditDialog("烟花", Mock())
        self.addCleanup(dialog.close)
        dialog.move(500, 300)
        dialog.show()
        menu.stat_bubble._name_dialog = dialog
        event = Mock()
        event.type.return_value = QEvent.MouseButtonPress
        event.globalPos.return_value = dialog.frameGeometry().center()

        menu.eventFilter(dialog, event)

        self.assertFalse(menu._closing)

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

    def test_desktop_autonomy_choices_never_include_walking(self):
        host = SimpleNamespace(
            settings={
                "ask_weight_needy": 0.6,
                "ask_weight_normal": 0.2,
                "chatter_frequency_boost": 1.0,
            },
            needy=Mock(return_value=False),
            AUTONOMY_IDLE_WEIGHT=1.0,
            AUTONOMY_SIT_WEIGHT=0.4,
        )

        choices, weights = pet.PetWindow.desktop_autonomy_choices(host)

        self.assertEqual(choices, ["idle", "sit", "ask"])
        self.assertEqual(len(choices), len(weights))
        self.assertNotIn("walk", choices)

    def test_zero_stat_reminders_use_priority_and_independent_cooldowns(self):
        host = SimpleNamespace(
            state={
                "sleeping": False,
                "energy": 0,
                "hunger": 0,
                "mood": 0,
                "pending_dig_reward": 0,
            },
            _last_stat_reminder_t={
                "energy": 0.0,
                "hunger": 0.0,
                "mood": 0.0,
            },
        )

        first = pet.PetWindow.next_stat_reminder(host, now=1000)
        second = pet.PetWindow.next_stat_reminder(host, now=1000)
        third = pet.PetWindow.next_stat_reminder(host, now=1000)
        blocked = pet.PetWindow.next_stat_reminder(host, now=1000)

        self.assertEqual(first[0], "energy")
        self.assertEqual(second[0], "hunger")
        self.assertEqual(third[0], "mood")
        self.assertIsNone(blocked)

    def test_pending_treasure_suppresses_normal_stat_reminders(self):
        host = SimpleNamespace(
            state={
                "sleeping": False,
                "energy": 0,
                "hunger": 0,
                "mood": 0,
                "pending_dig_reward": 12,
            },
            _last_stat_reminder_t={
                "energy": 0.0,
                "hunger": 0.0,
                "mood": 0.0,
            },
            _interactive_bubble=SimpleNamespace(
                action_name="dig_reward",
                isVisible=lambda: True,
            ),
            _hidden_treasure_bubble=None,
        )

        self.assertIsNone(pet.PetWindow.next_stat_reminder(host, now=1000))

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

    def test_toggle_visible_hides_active_home_instead_of_showing_desktop_pet(self):
        home = SimpleNamespace(isVisible=lambda: True, hide_scene=Mock())
        pet_host = SimpleNamespace(
            play_scene=None,
            home_scene_window=home,
            isVisible=lambda: False,
            show=Mock(),
        )
        tray = SimpleNamespace(pet=pet_host)

        pet.TrayApp.toggle_visible(tray)

        home.hide_scene.assert_called_once_with()
        pet_host.show.assert_not_called()

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

    def test_debug_menu_adds_1000_pet_coins_and_saves_shared_balance(self):
        tray = self._tray_harness()
        tray.state = progression.ensure_progression({
            "pet_coins": 25,
            "player": {"pet_coins": 25},
        })
        tray.pet.state = tray.state
        tray.pet.say = Mock()
        menu = QMenu()
        with patch("pet.IS_FROZEN", False), patch("pet.save_state") as save:
            pet.TrayApp._populate_menu(tray, menu, include_status=False)
            debug = next(action.menu() for action in menu.actions() if "调试" in action.text())
            add_coins = next(action for action in debug.actions() if "1000 Pet币" in action.text())
            add_coins.trigger()

        self.assertEqual(tray.state["player"]["pet_coins"], 1025)
        self.assertEqual(tray.state["pet_coins"], 1025)
        save.assert_called_once_with(tray.state)


if __name__ == "__main__":
    unittest.main()
