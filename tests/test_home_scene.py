import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication

import home_scene
import home_pet
import progression


class HomeSceneAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
    def test_home_assets_are_present_and_named_by_catalog(self):
        self.assertEqual(home_scene.HOME_BACKGROUND_MODE, "flattened_midground")
        self.assertTrue(os.path.isfile(home_scene.HOME_BACKGROUND_PATH))
        for path in home_scene.HOME_FURNITURE_PATHS.values():
            self.assertTrue(os.path.isfile(path))

    def test_home_pet_walk_sheet_exposes_only_its_eight_authored_frames(self):
        self.assertTrue(os.path.isfile(home_scene.HOME_PET_WALK_DOWN_PATH))
        sheet = QPixmap(home_scene.HOME_PET_WALK_DOWN_PATH)
        self.assertEqual((sheet.width(), sheet.height()), (1920, 1920))
        self.assertEqual(
            home_scene.home_pet_walk_source_rect(0),
            QRect(64, 80, 512, 464),
        )
        self.assertEqual(
            home_scene.home_pet_walk_source_rect(7),
            QRect(704, 1360, 512, 464),
        )
        self.assertEqual(
            home_scene.home_pet_walk_source_rect(8),
            QRect(64, 80, 512, 464),
        )

    def test_static_source_rect_crops_transparent_padding(self):
        pixmap = QPixmap(100, 120)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(QRect(20, 10, 60, 90), Qt.white)
        painter.end()

        self.assertEqual(
            home_scene.home_pet_static_source_rect(pixmap),
            QRect(20, 10, 60, 90),
        )

        transparent = QPixmap(40, 50)
        transparent.fill(Qt.transparent)
        self.assertEqual(
            home_scene.home_pet_static_source_rect(transparent),
            QRect(0, 0, 40, 50),
        )

    def test_animation_source_rect_unites_threshold_alpha_bounds(self):
        first_image = QImage(100, 80, QImage.Format_ARGB32)
        first_image.fill(Qt.transparent)
        first_image.setPixelColor(0, 0, QColor(255, 255, 255, 1))
        painter = QPainter(first_image)
        painter.fillRect(QRect(20, 10, 30, 40), Qt.white)
        painter.end()

        second_image = QImage(100, 80, QImage.Format_ARGB32)
        second_image.fill(Qt.transparent)
        painter = QPainter(second_image)
        painter.fillRect(QRect(40, 20, 30, 40), Qt.white)
        painter.end()

        rect = home_scene.home_pet_animation_source_rect(
            [QPixmap.fromImage(first_image), QPixmap.fromImage(second_image)]
        )

        self.assertEqual(rect, QRect(20, 10, 50, 50))
        self.assertEqual(home_scene.home_pet_animation_source_rect([]), QRect())

    def test_back_right_walk_sheet_aligns_all_eight_frames_to_one_footline(self):
        self.assertTrue(os.path.isfile(home_scene.HOME_PET_WALK_BACK_RIGHT_PATH))
        sheet = QPixmap(home_scene.HOME_PET_WALK_BACK_RIGHT_PATH)
        self.assertEqual((sheet.width(), sheet.height()), (1920, 1920))
        self.assertEqual(
            home_scene.home_pet_back_walk_source_rect(0),
            QRect(64, 68, 512, 464),
        )
        self.assertEqual(
            home_scene.home_pet_back_walk_source_rect(7),
            QRect(704, 1341, 512, 464),
        )
        self.assertEqual(
            home_scene.home_pet_back_walk_source_rect(8),
            QRect(64, 68, 512, 464),
        )

    def test_home_pet_walk_frame_advances_only_while_walking(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        self.assertEqual(scene.home_pet_walk_frame(now=0.875), 0)
        scene.home_pet.state = "manual_walk"
        self.assertEqual(scene.home_pet_walk_frame(now=0.0), 0)
        self.assertEqual(scene.home_pet_walk_frame(now=0.125), 1)
        self.assertEqual(scene.home_pet_walk_frame(now=0.999), 7)
        self.assertEqual(scene.home_pet_walk_frame(now=1.0), 0)
        scene.home_pet.state = "manual_sleep_walk"
        self.assertEqual(scene.home_pet_walk_frame(now=0.125), 1)

    def test_home_pet_sleep_sheet_exposes_only_its_eight_authored_frames(self):
        self.assertTrue(os.path.isfile(home_scene.HOME_PET_SLEEP_PATH))
        sheet = QPixmap(home_scene.HOME_PET_SLEEP_PATH)
        self.assertEqual((sheet.width(), sheet.height()), (1920, 1920))
        self.assertEqual(
            home_scene.home_pet_sleep_source_rect(0),
            QRect(24, 176, 592, 288),
        )
        self.assertEqual(
            home_scene.home_pet_sleep_source_rect(7),
            QRect(664, 1456, 592, 288),
        )
        self.assertEqual(
            home_scene.home_pet_sleep_source_rect(8),
            QRect(24, 176, 592, 288),
        )

    def test_home_pet_sleep_frame_loops_at_three_frames_per_second(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        self.assertEqual(scene.home_pet_sleep_frame(now=1.0 / 3.0), 0)
        scene.home_pet.state = "sleeping"
        self.assertEqual(scene.home_pet_sleep_frame(now=0.0), 0)
        self.assertEqual(scene.home_pet_sleep_frame(now=1.0 / 3.0), 1)
        self.assertEqual(scene.home_pet_sleep_frame(now=7.0 / 3.0), 7)
        self.assertEqual(scene.home_pet_sleep_frame(now=8.0 / 3.0), 0)

    def test_idle_uses_dedicated_sitting_art_and_falls_back_to_walk_frame(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        scene.home_pet.state = "idle"
        spec = scene.home_pet_render_spec(now=0.0)
        self.assertFalse(scene.home_pet_idle.isNull())
        self.assertEqual(spec.pixmap.cacheKey(), scene.home_pet_idle.cacheKey())
        scene.home_pet_idle = QPixmap()

        fallback = scene.home_pet_render_spec(now=0.0)

        self.assertEqual(
            fallback.pixmap.cacheKey(),
            scene.home_pet_walk_down.cacheKey(),
        )
        self.assertEqual(fallback.frame_index, 0)

    def test_sleeping_uses_the_sleep_sheet_and_falls_back_when_it_is_missing(self):
        state = progression.ensure_progression({})
        shared_sleep = QPixmap(20, 20)
        shared_sleep.fill(Qt.white)
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            shared_animation_frame=lambda: {
                "name": "sleep",
                "pixmap": shared_sleep,
                "frame_index": 0,
                "spec": {"scale": 0.7},
            },
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.state = "sleeping"

        spec = scene.home_pet_render_spec(now=1.0 / 3.0)

        self.assertFalse(scene.home_pet_sleep.isNull())
        self.assertEqual(spec.pixmap.cacheKey(), scene.home_pet_sleep.cacheKey())
        self.assertEqual(spec.source_rect, QRect(664, 176, 592, 288))
        self.assertEqual(spec.frame_index, 1)
        self.assertFalse(spec.mirrored)
        self.assertEqual(spec.visual_scale, 0.50)
        rect = scene.home_pet_render_rect(spec)
        self.assertAlmostEqual(rect.width(), 118.46, places=2)
        self.assertAlmostEqual(rect.height(), 57.63, places=2)

        scene.home_pet_sleep = QPixmap()
        self.assertIsNone(scene.home_pet_render_spec(now=1.0 / 3.0))

    def test_authored_sleep_art_uses_its_own_shadow_but_fallback_keeps_one(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.resize(900, 768)
        scene.home_pet.position = (450.0, 600.0)
        scene.home_pet.state = "sleeping"
        transparent_sheet = QPixmap(1920, 1920)
        transparent_sheet.fill(Qt.transparent)
        scene.home_pet_sleep = transparent_sheet

        authored = QImage(900, 768, QImage.Format_ARGB32_Premultiplied)
        authored.fill(Qt.transparent)
        blank = authored.copy()
        painter = QPainter(authored)
        with patch.object(scene, "home_pet_visible", return_value=True):
            scene._draw_home_pet(painter)
        painter.end()
        self.assertEqual(authored, blank)

        scene.home_pet_sleep = QPixmap()
        fallback = QImage(900, 768, QImage.Format_ARGB32_Premultiplied)
        fallback.fill(Qt.transparent)
        painter = QPainter(fallback)
        with patch.object(scene, "home_pet_visible", return_value=True):
            scene._draw_home_pet(painter)
        painter.end()
        self.assertNotEqual(fallback, blank)

    def test_idle_render_rect_preserves_asset_aspect_ratio(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.state = "idle"

        spec = scene.home_pet_render_spec(now=0.0)
        rect = scene.home_pet_render_rect(spec)

        self.assertAlmostEqual(
            rect.width() / rect.height(),
            spec.source_rect.width() / spec.source_rect.height(),
            places=3,
        )
        self.assertAlmostEqual(rect.bottom(), scene.home_pet.position[1])

    def test_shared_idle_matches_walk_height_footline_and_shadow_center(self):
        idle = QPixmap(100, 120)
        idle.fill(Qt.transparent)
        painter = QPainter(idle)
        painter.fillRect(QRect(20, 10, 60, 90), Qt.white)
        painter.end()
        state = progression.ensure_progression({"active_pet_id": "ice_cream"})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            shared_animation_frame=lambda: {
                "name": "idle",
                "pixmap": idle,
                "frame_index": 0,
                "spec": {},
            },
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.state = "idle"
        scene.home_pet.direction = "front_right"

        idle_spec = scene.home_pet_render_spec(now=0.0)
        idle_rect = scene.home_pet_render_rect(idle_spec)
        walk_rect = scene.home_pet_render_rect(
            scene.home_pet_walk_render_spec(now=0.0)
        )
        shadow = home_scene.home_pet_shadow_rect(
            idle_rect,
            (
                idle_spec.contact_center_x,
                idle_spec.contact_width,
                idle_spec.contact_foot_y,
            ),
        )

        self.assertEqual(idle_spec.source_rect, QRect(20, 10, 60, 90))
        self.assertAlmostEqual(idle_rect.height(), walk_rect.height())
        self.assertAlmostEqual(idle_rect.bottom(), walk_rect.bottom())
        self.assertAlmostEqual(shadow.center().x(), idle_rect.center().x())
        self.assertLess(shadow.bottom(), idle_rect.bottom())

    def test_shared_idle_frames_keep_one_cached_render_rect(self):
        frames = []
        for body in (QRect(20, 10, 40, 80), QRect(30, 10, 40, 80)):
            pixmap = QPixmap(100, 100)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.fillRect(body, Qt.white)
            painter.end()
            frames.append(pixmap)

        current = {"index": 0}
        state = progression.ensure_progression({"active_pet_id": "ice_cream"})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            animation_frames={"idle": frames},
            shared_animation_frame=lambda: {
                "name": "idle",
                "pixmap": frames[current["index"]],
                "frame_index": current["index"],
                "spec": {},
            },
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.state = "idle"

        first_spec = scene.home_pet_render_spec(now=0.0)
        first_rect = scene.home_pet_render_rect(first_spec)
        current["index"] = 1
        second_spec = scene.home_pet_render_spec(now=0.1)
        second_rect = scene.home_pet_render_rect(second_spec)

        self.assertEqual(first_spec.source_rect, QRect(20, 10, 50, 80))
        self.assertEqual(second_spec.source_rect, first_spec.source_rect)
        self.assertEqual(second_rect, first_rect)

    def test_refresh_pet_assets_discards_shared_animation_crop(self):
        first = QPixmap(100, 100)
        first.fill(Qt.transparent)
        painter = QPainter(first)
        painter.fillRect(QRect(20, 10, 30, 40), Qt.white)
        painter.end()

        second = QPixmap(100, 100)
        second.fill(Qt.transparent)
        painter = QPainter(second)
        painter.fillRect(QRect(10, 5, 70, 80), Qt.white)
        painter.end()

        current = {"pixmap": first}
        state = progression.ensure_progression({"active_pet_id": "ice_cream"})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            animation_frames={"idle": [first]},
            shared_animation_frame=lambda: {
                "name": "idle",
                "pixmap": current["pixmap"],
                "frame_index": 0,
                "spec": {},
            },
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.state = "idle"

        self.assertEqual(
            scene.home_pet_render_spec().source_rect,
            QRect(20, 10, 30, 40),
        )
        pet.animation_frames["idle"] = [second]
        current["pixmap"] = second
        scene.refresh_pet_assets("ice_cream")

        self.assertEqual(
            scene.home_pet_render_spec().source_rect,
            QRect(10, 5, 70, 80),
        )

    def test_back_directions_select_the_back_sheet_and_mirror_only_left(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        scene.home_pet.direction = "back_right"
        spec = scene.home_pet_walk_render_spec(now=0.0)
        self.assertEqual(spec.pixmap.cacheKey(), scene.home_pet_walk_back_right.cacheKey())
        self.assertEqual(spec.source_rect, QRect(64, 68, 512, 464))
        self.assertFalse(spec.mirrored)
        self.assertEqual(spec.frame_index, 0)
        self.assertEqual(spec.visual_scale, 1.06)

        scene.home_pet.direction = "back_left"
        spec = scene.home_pet_walk_render_spec(now=0.0)
        self.assertEqual(spec.pixmap.cacheKey(), scene.home_pet_walk_back_right.cacheKey())
        self.assertEqual(spec.source_rect, QRect(64, 68, 512, 464))
        self.assertTrue(spec.mirrored)
        self.assertEqual(spec.contact_center_x, 0.5898)

    def test_home_pet_frame_contact_mirrors_only_the_horizontal_center(self):
        right = home_scene.home_pet_frame_contact("front_right", 0)
        left = home_scene.home_pet_frame_contact("front_left", 0)

        self.assertEqual(right, (0.5547, 0.1523, 0.9784))
        self.assertEqual(left, (0.4453, 0.1523, 0.9784))

    def test_home_pet_shadow_tracks_the_current_frame_contact_patch(self):
        body = QRectF(10.0, 20.0, 100.0, 100.0)

        shadow = home_scene.home_pet_shadow_rect(body, (0.25, 0.4, 0.9))

        self.assertEqual(shadow, QRectF(12.0, 105.75, 46.0, 5.5))
        self.assertLess(shadow.bottom(), body.bottom())

    def test_home_destination_opacity_fades_out_over_350_milliseconds(self):
        self.assertEqual(home_scene.home_destination_opacity(None, 20.0), 1.0)
        self.assertEqual(home_scene.home_destination_opacity(20.0, 20.0), 1.0)
        self.assertAlmostEqual(
            home_scene.home_destination_opacity(20.0, 20.175),
            0.5,
        )
        self.assertEqual(home_scene.home_destination_opacity(20.0, 20.35), 0.0)

    def test_home_scene_controls_have_chinese_labels_and_upper_right_exit(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            raise_=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.resize(900, 768)
        self.assertLess(scene.left_view_button_rect().right(), 100)
        self.assertGreater(scene.right_view_button_rect().left(), 800)
        self.assertLess(scene.decoration_button_rect().right(), scene.exit_button_rect().left())
        self.assertLess(scene.exit_button_rect().bottom(), 80)
        self.assertEqual(scene.scene_button_label("left"), "左移")
        self.assertEqual(scene.scene_button_label("right"), "右移")
        self.assertEqual(scene.scene_button_label("decorate"), "装修")
        self.assertEqual(scene.scene_button_label("exit"), "退出")
        self.assertEqual(scene.scene_button_label("shop"), "商店")
        self.assertEqual(scene.scene_button_label("interaction"), "互动⌄")

        actions = scene.home_action_button_rects()
        self.assertNotIn("status", actions)
        ordered = [
            actions[name].left()
            for name in ("shop", "interaction", "decorate", "exit")
        ]
        self.assertEqual(ordered, sorted(ordered))

    def test_status_card_uses_a_large_live_three_stat_layout(self):
        state = progression.ensure_progression({
            "pet_name": "团子",
            "level": 2,
            "affection_level": 3,
            "hunger": 80,
            "mood": 70,
            "energy": 60,
        })

        before = home_scene.render_home_status_card(state).toImage()
        state["hunger"] = 0
        state["pet_name"] = "糯米"
        after = home_scene.render_home_status_card(state).toImage()

        self.assertFalse(before.isNull())
        self.assertEqual(before.size(), QSize(840, 540))
        self.assertEqual(before.size(), after.size())
        self.assertNotEqual(before, after)
        self.assertEqual(home_scene.HOME_STATUS_CARD_SIZE, (420, 270))
        for rect in home_scene.home_status_card_value_rects():
            self.assertGreaterEqual(rect.width(), 64)

    def test_home_action_buttons_are_compact_text_controls_with_a_shared_height(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        decorate = scene.decoration_button_rect()
        exit_button = scene.exit_button_rect()
        self.assertGreater(decorate.width(), decorate.height())
        self.assertGreater(exit_button.width(), exit_button.height())
        self.assertEqual(decorate.height(), exit_button.height())
        self.assertEqual(decorate.y(), exit_button.y())

    def test_furniture_assets_match_their_authored_scene_sizes(self):
        expected_sizes = {
            "home_rug": (440, 270),
            "home_sofa": (360, 225),
            "home_plant": (190, 340),
            "home_wall_art": (220, 285),
        }
        for decoration_id, expected_size in expected_sizes.items():
            pixmap = home_scene.QPixmap(
                home_scene.HOME_FURNITURE_PATHS[decoration_id]
            )
            self.assertEqual((pixmap.width(), pixmap.height()), expected_size)

    def test_board_geometry_uses_scene_math_and_saved_position(self):
        rect = home_scene.board_geometry(QRect(0, 0, 1920, 1080))
        self.assertEqual(rect, QRect(1020, 312, 900, 768))

    def test_decoration_sidebar_sits_outside_the_scene_canvas(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            raise_=Mock(),
            move=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()

        board = scene.scene_canvas_rect()
        panel = scene._panel_rect()
        expected_board = home_scene.board_geometry(pet.current_screen_rect())
        self.assertEqual(scene.geometry().right(), expected_board.right())
        self.assertEqual(board.width(), home_scene.HOME_VIEWPORT_SIZE[0])
        self.assertEqual(board.left(), home_scene.HOME_DECORATION_SIDEBAR_WIDTH)
        self.assertLess(panel.right(), board.left())

    def test_decoration_sidebar_matches_the_full_scene_height(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            raise_=Mock(),
            move=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()

        panel = scene._panel_rect()
        self.assertEqual(panel.y(), 0)
        self.assertEqual(panel.height(), 768)
        self.assertEqual(panel.width(), home_scene.HOME_DECORATION_SIDEBAR_WIDTH)

    def test_scene_uses_rounded_corners(self):
        self.assertEqual(home_scene.HOME_SCENE_CORNER_RADIUS, 24)

    def test_exit_button_is_inside_upper_right_corner(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            x=lambda: 400,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            raise_=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.setGeometry(QRect(1020, 312, 900, 768))

        button = scene.exit_button_rect()

        self.assertGreaterEqual(button.top(), 10)
        self.assertLess(button.bottom(), 80)
        self.assertTrue(button.right() <= scene.width() - 10)
        self.assertGreater(button.width(), 30)

        state["home_scene"]["enabled"] = True
        self.assertTrue(scene.handle_scene_click(button.center()))
        self.assertFalse(state["home_scene"]["enabled"])
        pet.raise_.assert_called()

    def test_dragged_furniture_is_saved_in_world_coordinates(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            x=lambda: 400,
            width=lambda: 190,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        scene.setGeometry(QRect(0, 0, 900, 768))
        scene._camera_x = 0
        scene.toggle_decoration_mode()

        self.assertEqual(scene.furniture_at(QPoint(230, 360)), "home_sofa")
        self.assertEqual(
            scene.move_furniture("home_sofa", QPoint(-60, 900)),
            {"x": 0, "y": 543},
        )
        save.assert_called_with(state)

    def test_furniture_cannot_move_when_decoration_mode_is_off(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        original = progression.home_decoration_position(state, "home_sofa")
        self.assertIsNone(scene.move_furniture("home_sofa", QPoint(700, 500)))
        self.assertEqual(progression.home_decoration_position(state, "home_sofa"), original)
        save.assert_not_called()

    def test_viewport_pans_only_while_decorating_then_follows_internal_pet(self):
        state = progression.ensure_progression({"home_scene_dog_world_x": 900})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            move=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
            raise_=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene._camera_x = 300

        self.assertFalse(scene.view_pan_enabled())
        self.assertEqual(scene.pan_view("right"), 300)
        scene.toggle_decoration_mode()
        self.assertTrue(scene.view_pan_enabled())
        self.assertEqual(scene.pan_view("right"), 520)
        self.assertTrue(scene._manual_camera)

        scene.toggle_decoration_mode()
        self.assertFalse(scene.view_pan_enabled())
        self.assertFalse(scene._manual_camera)
        self.assertEqual(scene.home_pet.position[0], 900.0)
        self.assertEqual(scene._camera_x, 450)

    def test_scene_tick_camera_follows_the_updated_internal_pet_position(self):
        state = progression.ensure_progression({"energy": 100.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (900.0, 600.0)
        scene.home_pet.command_move((1000.0, 600.0), now=9.0)
        scene._last_pet_tick = 9.9

        with patch.object(home_scene.time, "monotonic", return_value=10.0):
            scene._sync_scene()

        self.assertGreater(scene.home_pet.position[0], 900.0)
        self.assertEqual(
            scene._camera_x,
            home_scene.camera_x_for_dog(scene.home_pet.position[0], 0),
        )

    def test_decoration_mode_temporarily_hides_and_restores_the_pet(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            move=Mock(),
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        scene.show_scene()
        self.assertTrue(scene.home_pet_visible())
        scene.toggle_decoration_mode()
        self.assertFalse(scene.home_pet_visible())
        scene.toggle_decoration_mode()
        self.assertTrue(scene.home_pet_visible())
        pet.show.assert_not_called()

        scene.hide_scene()
        pet.show.assert_called_once_with()

    def test_home_scene_owns_internal_pet_and_migrates_legacy_position(self):
        state = progression.ensure_progression({"home_scene_dog_world_x": 900})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            hide_overlays=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        scene.show_scene()

        pet.hide.assert_called_once_with()
        self.assertEqual(
            scene.home_pet.position,
            (900.0, home_pet.HOME_DEFAULT_ENTRY[1]),
        )
        self.assertTrue(scene.home_pet_visible())

        scene.hide_scene()
        pet.show.assert_called_once_with()

    def test_home_scene_persists_only_internal_pet_position(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        scene.home_pet.position = (720.125, 610.555)

        scene._save_home_pet_position()

        self.assertEqual(
            state["home_scene"]["pet_position"],
            {"x": 720.12, "y": 610.55},
        )
        self.assertNotIn("target", state["home_scene"])
        self.assertNotIn("state", state["home_scene"])
        save.assert_called_once_with(state)

    def test_right_click_converts_canvas_point_with_camera_offset(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 500
        canvas = scene.scene_canvas_rect()
        point = QPoint(canvas.left() + 200, 600)

        self.assertTrue(scene.command_home_pet(point, now=10.0))

        self.assertEqual(scene.home_pet.target, (700.0, 600.0))
        self.assertEqual(scene.home_pet.state, "manual_walk")
        self.assertEqual(scene._manual_destination, (700.0, 600.0))
        self.assertIsNone(scene._destination_fade_started_at)

    def test_manual_destination_fades_after_arrival_then_clears(self):
        state = progression.ensure_progression({"energy": 100.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 0
        scene.home_pet.position = (500.0, 600.0)
        scene._last_pet_tick = 9.9
        target = QPoint(scene.scene_canvas_rect().left() + 501, 600)

        self.assertTrue(scene.command_home_pet(target, now=10.0))
        self.assertEqual(scene._advance_home_pet(now=10.0), ("arrived",))
        self.assertEqual(scene._destination_fade_started_at, 10.0)
        self.assertAlmostEqual(
            home_scene.home_destination_opacity(
                scene._destination_fade_started_at,
                10.175,
            ),
            0.5,
        )

        scene._advance_home_pet(now=10.35)

        self.assertIsNone(scene._manual_destination)
        self.assertIsNone(scene._destination_fade_started_at)

    def test_auto_sleep_walk_does_not_create_a_manual_destination(self):
        state = progression.ensure_progression({"energy": 10.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        scene._advance_home_pet(now=10.0)

        self.assertEqual(scene.home_pet.state, "auto_sleep_walk")
        self.assertIsNone(scene._manual_destination)

    def test_right_click_is_ignored_over_controls_outside_canvas_or_decorating(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()

        self.assertFalse(
            scene.command_home_pet(scene.exit_button_rect().center(), now=1.0)
        )
        self.assertFalse(scene.command_home_pet(QPoint(20, 600), now=1.5))
        scene.toggle_decoration_mode()
        self.assertFalse(
            scene.command_home_pet(scene.scene_canvas_rect().center(), now=2.0)
        )
        self.assertIsNone(scene.home_pet.target)

    def test_left_button_press_dispatches_one_home_move_command(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        point = QPoint(scene.scene_canvas_rect().left() + 400, 600)
        event = SimpleNamespace(
            button=lambda: Qt.LeftButton,
            pos=lambda: point,
            accept=Mock(),
        )

        scene.mousePressEvent(event)

        self.assertEqual(scene.home_pet.target, (400.0, 600.0))
        event.accept.assert_called_once_with()

    def test_right_click_never_opens_the_desktop_menu_inside_home(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            open_bubble_menu=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (900.0, 600.0)
        scene._camera_x = 450
        inside = scene.home_pet_draw_rect().center().toPoint()
        outside = scene.scene_canvas_rect().topLeft() + QPoint(30, 100)

        self.assertFalse(scene.open_home_pet_menu(inside))
        pet.open_bubble_menu.assert_not_called()
        self.assertFalse(scene.open_home_pet_menu(outside))
        pet.open_bubble_menu.assert_not_called()

        scene.toggle_decoration_mode()
        self.assertFalse(scene.open_home_pet_menu(inside))
        pet.open_bubble_menu.assert_not_called()

    def test_zero_stat_attention_marks_header_pet_and_restoring_actions(self):
        state = progression.ensure_progression({
            "hunger": 0,
            "mood": 0,
            "energy": 0,
        })
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        self.assertTrue(scene.home_pet_needs_attention())
        self.assertTrue(scene.interaction_header_needs_attention())
        self.assertEqual(
            scene.interaction_actions_needing_attention(),
            {"pet", "feed", "play", "sleep"},
        )

    def test_home_interaction_button_dispatches_existing_pet_actions(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            pet_click=Mock(),
            feed=Mock(),
            play=Mock(),
            toggle_sleep=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        for action, method in (
            ("pet", pet.pet_click),
            ("feed", pet.feed),
            ("play", pet.play),
            ("sleep", pet.toggle_sleep),
        ):
            self.assertTrue(scene.trigger_home_interaction(action))
            method.assert_called_once_with()

    def test_home_pet_global_rect_maps_the_rendered_body_from_scene_window(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (900.0, 600.0)
        scene._camera_x = 450
        local = scene.home_pet_hit_rect().toAlignedRect()

        result = scene.home_pet_global_rect()

        self.assertEqual(result.topLeft(), scene.mapToGlobal(local.topLeft()))
        self.assertEqual(result.size(), local.size())

    def test_home_sync_repositions_visible_pet_overlays(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            follow_interface_overlays=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        pet.follow_interface_overlays.reset_mock()

        scene._sync_scene()

        pet.follow_interface_overlays.assert_called_once_with()

    def test_entering_decoration_and_hiding_home_clear_interface_overlays(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            hide_overlays=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        pet.hide_overlays.reset_mock()

        scene.toggle_decoration_mode()

        pet.hide_overlays.assert_called_once_with()

        pet.hide_overlays.reset_mock()
        scene.toggle_decoration_mode()
        scene.hide_scene()

        pet.hide_overlays.assert_called_once_with()

    def test_home_sleep_target_prefers_placed_rug_center_and_tracks_moves(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_rug")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        self.assertEqual(scene.home_sleep_target(), (840.0, 565.0))

        progression.set_home_decoration_position(
            state,
            "home_rug",
            700,
            430,
        )
        self.assertEqual(scene.home_sleep_target(), (920.0, 565.0))

    def test_home_sleep_target_falls_back_when_rug_is_stored(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_rug")
        progression.store_home_decoration(state, "home_rug")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)

        self.assertEqual(
            scene.home_sleep_target(),
            home_pet.HOME_DEFAULT_SLEEP_POINT,
        )

    def test_home_pet_sleep_tick_syncs_shared_sleep_and_wake_state(self):
        state = progression.ensure_progression({"energy": 10.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        scene.home_pet.position = home_pet.HOME_DEFAULT_SLEEP_POINT
        scene._last_pet_tick = 9.9

        events = scene._advance_home_pet(now=10.0)

        self.assertEqual(events, ("arrived", "sleep_started"))
        self.assertTrue(state["sleeping"])
        self.assertEqual(state["sleep_mode"], "auto")
        self.assertEqual(scene.home_pet.state, "sleeping")

        state["energy"] = 80.0
        scene._advance_home_pet(now=10.1)

        self.assertFalse(state["sleeping"])
        self.assertIsNone(state["sleep_mode"])
        self.assertEqual(scene.home_pet.state, "idle")
        self.assertGreaterEqual(save.call_count, 2)

    def test_home_pet_does_not_auto_wake_shared_manual_sleep(self):
        state = progression.ensure_progression(
            {
                "energy": 100.0,
                "sleeping": True,
                "sleep_mode": "manual",
            }
        )
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene._last_pet_tick = 9.9

        scene._advance_home_pet(now=10.0)

        self.assertTrue(state["sleeping"])
        self.assertEqual(state["sleep_mode"], "manual")
        self.assertEqual(scene.home_pet.state, "sleeping")

    def test_home_manual_sleep_walks_to_rug_before_shared_sleep_starts(self):
        state = progression.ensure_progression(
            {"energy": 100.0, "pet_coins": 500}
        )
        progression.purchase_home_decoration(state, "home_rug")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (600.0, 600.0)
        target = scene.home_sleep_target()

        self.assertTrue(scene.toggle_home_sleep(now=10.0))

        self.assertEqual(scene.home_pet.state, "manual_sleep_walk")
        self.assertEqual(scene.home_pet.target, target)
        self.assertFalse(state["sleeping"])
        self.assertEqual(scene._manual_destination, target)

    def test_home_manual_sleep_replaces_an_active_move_target(self):
        state = progression.ensure_progression({"energy": 100.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.command_move((700.0, 600.0), now=9.0)

        self.assertTrue(scene.toggle_home_sleep(now=10.0))

        self.assertEqual(scene.home_pet.state, "manual_sleep_walk")
        self.assertEqual(scene.home_pet.target, home_pet.HOME_DEFAULT_SLEEP_POINT)

    def test_home_manual_sleep_records_only_after_arrival(self):
        state = progression.ensure_progression({"energy": 100.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (250.0, 610.0)

        scene.toggle_home_sleep(now=10.0)
        self.assertEqual(state["records"]["manual_sleeps"], 0)
        scene._last_pet_tick = 9.9
        events = scene._advance_home_pet(now=10.0)

        self.assertEqual(events, ("arrived", "manual_sleep_started"))
        self.assertTrue(state["sleeping"])
        self.assertEqual(state["sleep_mode"], "manual")
        self.assertEqual(state["records"]["manual_sleeps"], 1)
        self.assertEqual(scene.home_pet.state, "sleeping")
        save.assert_called()

    def test_home_sleep_toggle_wakes_manual_sleep_in_place(self):
        state = progression.ensure_progression({
            "energy": 100.0,
            "sleeping": True,
            "sleep_mode": "manual",
        })
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        position = scene.home_pet.position

        self.assertTrue(scene.toggle_home_sleep(now=10.0))

        self.assertFalse(state["sleeping"])
        self.assertIsNone(state["sleep_mode"])
        self.assertEqual(scene.home_pet.state, "idle")
        self.assertEqual(scene.home_pet.position, position)

    def test_reentering_home_resets_targets_and_runtime_sleep_cooldown(self):
        state = progression.ensure_progression({"energy": 100.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            raise_=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.request_auto_sleep((300.0, 600.0), now=10.0)
        scene.home_pet.command_move((700.0, 600.0), now=20.0)
        self.assertEqual(scene.home_pet.sleep_retry_until, 80.0)

        scene.hide_scene()
        scene.show_scene()

        self.assertEqual(scene.home_pet.state, "idle")
        self.assertIsNone(scene.home_pet.target)
        self.assertEqual(scene.home_pet.sleep_retry_until, 0.0)

    def test_home_pet_sleep_tick_does_not_override_manual_or_decoration_state(self):
        state = progression.ensure_progression({"energy": 10.0})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.home_pet.command_move((700.0, 600.0), now=1.0)

        scene._advance_home_pet(now=2.0)

        self.assertEqual(scene.home_pet.state, "manual_walk")
        scene.toggle_decoration_mode()
        stopped_position = scene.home_pet.position
        scene._advance_home_pet(now=3.0)
        self.assertEqual(scene.home_pet.position, stopped_position)
        self.assertEqual(scene.home_pet.state, "idle")

    def test_home_pet_draw_rect_keeps_foreground_size_at_every_depth(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 500
        canvas_left = scene.scene_canvas_rect().left()

        scene.home_pet.position = (900.0, 460.0)
        far_rect = scene.home_pet_draw_rect()
        scene.home_pet.position = (900.0, 730.0)
        near_rect = scene.home_pet_draw_rect()
        enlarged_rect = scene.home_pet_draw_rect(visual_scale=1.06)

        self.assertEqual(far_rect.size(), near_rect.size())
        self.assertAlmostEqual(
            near_rect.width() / near_rect.height(),
            512.0 / 464.0,
            places=2,
        )
        self.assertAlmostEqual(far_rect.bottom(), 460.0)
        self.assertAlmostEqual(near_rect.bottom(), 730.0)
        self.assertAlmostEqual(enlarged_rect.bottom(), 730.0)
        self.assertAlmostEqual(enlarged_rect.width(), near_rect.width() * 1.06)
        self.assertAlmostEqual(enlarged_rect.height(), near_rect.height() * 1.06)
        expected_center = canvas_left + 900.0 - 500.0
        self.assertAlmostEqual(far_rect.center().x(), expected_center)
        self.assertAlmostEqual(near_rect.center().x(), expected_center)

    def test_scene_render_entries_sort_pet_between_floor_and_depth_furniture(self):
        state = progression.ensure_progression({"pet_coins": 2000})
        for item_id in (
            "home_rug",
            "home_sofa",
            "home_plant",
            "home_wall_art",
        ):
            progression.purchase_home_decoration(state, item_id)
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()

        scene.home_pet.position = (900.0, 500.0)
        far_order = [entry[2] for entry in scene._scene_render_entries()]
        self.assertLess(far_order.index("home_wall_art"), far_order.index("home_rug"))
        self.assertLess(far_order.index("home_rug"), far_order.index("home_pet"))
        self.assertLess(far_order.index("home_pet"), far_order.index("home_sofa"))

        scene.home_pet.position = (900.0, 700.0)
        near_order = [entry[2] for entry in scene._scene_render_entries()]
        self.assertLess(near_order.index("home_sofa"), near_order.index("home_pet"))
        self.assertLess(near_order.index("home_plant"), near_order.index("home_pet"))

    def test_home_pet_placeholder_draws_pixels_and_is_hidden_during_decoration(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            auto_sleep_energy_threshold=30.0,
            auto_wake_energy_threshold=80.0,
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (900.0, 600.0)
        scene._camera_x = 450
        image = QImage(scene.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            scene._draw_home_pet(painter)
        finally:
            painter.end()

        center = scene.home_pet_draw_rect().center().toPoint()
        self.assertGreater(image.pixelColor(center).alpha(), 0)
        scene.toggle_decoration_mode()
        self.assertNotIn(
            "home_pet",
            [entry[2] for entry in scene._scene_render_entries()],
        )

    def test_navigation_feedback_hides_passed_footprints_without_reflowing_route(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 450
        scene.home_pet.position = (600.0, 600.0)
        scene._set_manual_destination((900.0, 600.0))
        first = scene.navigation_feedback(now=10.0)
        scene.home_pet.position = (750.0, 600.0)
        second = scene.navigation_feedback(now=10.0)

        self.assertEqual(first["end"], second["end"])
        self.assertGreater(len(first["footprints"]), len(second["footprints"]))
        first_route = tuple(
            (
                footprint["rect"].center(),
                footprint["angle"],
                footprint["mirrored"],
            )
            for footprint in first["footprints"]
        )
        second_route = tuple(
            (
                footprint["rect"].center(),
                footprint["angle"],
                footprint["mirrored"],
            )
            for footprint in second["footprints"]
        )
        self.assertEqual(second_route, first_route[-len(second_route):])

    def test_new_manual_destination_replaces_the_fixed_route_snapshot(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (600.0, 600.0)

        scene._set_manual_destination((900.0, 600.0))
        first_route = scene._manual_route
        scene._set_manual_destination((450.0, 540.0))

        self.assertIsNot(scene._manual_route, first_route)
        self.assertEqual(scene._manual_route["start"], (600.0, 600.0))
        self.assertEqual(scene._manual_route["end"], (450.0, 540.0))
        self.assertEqual(
            scene.navigation_feedback(now=10.0)["end"],
            QPointF(
                scene._scene_content_offset() - scene._camera_x + 450.0,
                540.0,
            ),
        )

    def test_navigation_feedback_uses_fixed_image_geometry(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 450
        scene.home_pet.position = (600.0, 600.0)
        scene._manual_destination = (900.0, 600.0)

        feedback = scene.navigation_feedback(now=10.0)

        self.assertGreater(len(feedback["footprints"]), 1)
        self.assertAlmostEqual(
            feedback["target_rect"].width()
            / feedback["target_rect"].height(),
            2.1,
            delta=0.1,
        )
        self.assertNotEqual(feedback["arrow_rect"], feedback["target_rect"])
        self.assertNotIn("depth_scale", feedback)
        later = scene.navigation_feedback(now=10.225)
        self.assertNotEqual(feedback["arrow_offset"], later["arrow_offset"])

        unpulsed = scene.navigation_feedback(now=0.0)
        self.assertAlmostEqual(unpulsed["target_rect"].height(), 24.0)
        self.assertLess(unpulsed["arrow_rect"].height(), 31.0)

    def test_navigation_layer_sits_above_rug_and_below_pet_and_sofa(self):
        state = progression.ensure_progression({"pet_coins": 1000})
        progression.purchase_home_decoration(state, "home_rug")
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._manual_destination = (900.0, 600.0)

        order = [entry[2] for entry in scene._scene_render_entries()]

        self.assertLess(order.index("home_rug"), order.index("home_navigation"))
        self.assertLess(order.index("home_navigation"), order.index("home_pet"))
        self.assertLess(order.index("home_navigation"), order.index("home_sofa"))

    def test_navigation_feedback_draws_image_footprints_target_and_arrow(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene._camera_x = 450
        scene.home_pet.position = (600.0, 600.0)
        scene._manual_destination = (900.0, 600.0)
        feedback = scene.navigation_feedback(now=10.0)
        image = QImage(scene.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            scene._draw_navigation_feedback(painter, now=10.0)
        finally:
            painter.end()

        footprint = feedback["footprints"][0]["rect"].toAlignedRect()
        path_pixels = sum(
            image.pixelColor(x, y).alpha() > 0
            for x in range(footprint.left(), footprint.right() + 1)
            for y in range(footprint.top(), footprint.bottom() + 1)
        )
        target = feedback["target_rect"].toAlignedRect()
        marker_pixels = sum(
            image.pixelColor(x, y).alpha() > 0
            for x in range(target.left(), target.right() + 1)
            for y in range(target.top(), target.bottom() + 1)
        )
        arrow = feedback["arrow_rect"].toAlignedRect()
        arrow_pixels = sum(
            image.pixelColor(x, y).alpha() > 0
            for x in range(arrow.left(), arrow.right() + 1)
            for y in range(arrow.top(), arrow.bottom() + 1)
        )
        self.assertGreater(path_pixels, 0)
        self.assertGreater(marker_pixels, 20)
        self.assertGreater(arrow_pixels, 10)

    def test_missing_navigation_images_do_not_block_movement_or_rendering(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            hide=Mock(),
            show=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.home_pet.position = (600.0, 600.0)
        scene.home_pet.command_move((900.0, 600.0), now=10.0)
        scene._manual_destination = (900.0, 600.0)
        scene.home_nav_paw = QPixmap()
        scene.home_nav_target = QPixmap()
        scene.home_nav_arrow = QPixmap()
        image = QImage(scene.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        try:
            scene._draw_navigation_feedback(painter, now=10.0)
        finally:
            painter.end()

        before = scene.home_pet.position
        scene.home_pet.advance(0.1)

        self.assertGreater(scene.home_pet.position[0], before[0])

    def test_decoration_panel_is_a_left_sidebar_with_image_cards(self):
        state = progression.ensure_progression({"pet_coins": 1000})
        progression.purchase_home_decoration(state, "home_sofa")
        progression.purchase_home_decoration(state, "home_plant")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.toggle_decoration_mode()

        panel = scene._panel_rect()
        self.assertGreaterEqual(panel.x(), 0)
        self.assertLess(panel.width(), scene.scene_canvas_rect().width() // 2)
        cards = scene._item_card_rects()
        self.assertEqual(set(cards), {"home_sofa", "home_plant"})
        for item_id, card in cards.items():
            thumbnail = scene._item_thumbnail_rect(card)
            self.assertGreater(thumbnail.width(), 0)
            self.assertGreaterEqual(thumbnail.height(), 72)
            preview = scene.furniture_preview_rect(item_id, card)
            source = scene.furniture[item_id]
            self.assertTrue(thumbnail.contains(preview))
            self.assertAlmostEqual(
                preview.width() / preview.height(),
                source.width() / source.height(),
                delta=0.03,
            )
            action = scene._item_action_rect(card)
            self.assertTrue(card.contains(action))
            self.assertGreater(action.width(), card.width() // 2)
        self.assertTrue(all(rect.y() >= panel.y() for rect in scene._category_rects().values()))

    def test_selection_overlay_uses_warm_rounded_controls(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.resize(900, 768)
        scene.toggle_decoration_mode()
        scene.select_furniture("home_sofa")

        image = QImage(scene.size(), QImage.Format_ARGB32)
        image.fill(home_scene.QColor("#ffffff"))
        painter = QPainter(image)
        scene._draw_selection(painter, "home_sofa")
        painter.end()

        blue_pixels = 0
        warm_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = home_scene.QColor(image.pixel(x, y))
                if color.blue() > 130 and color.blue() > color.red() * 1.35:
                    blue_pixels += 1
                if color.red() > 100 and color.red() > color.blue() * 1.15:
                    warm_pixels += 1
        self.assertEqual(blue_pixels, 0)
        self.assertGreater(warm_pixels, 20)

    def test_decoration_panel_is_a_left_sidebar_with_compact_two_column_cards(self):
        state = progression.ensure_progression({"pet_coins": 2000})
        for item_id in ("home_rug", "home_sofa", "home_plant", "home_wall_art"):
            progression.purchase_home_decoration(state, item_id)
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.toggle_decoration_mode()

        panel = scene._panel_rect()
        self.assertLess(panel.width(), scene.scene_canvas_rect().width() // 2)
        self.assertGreaterEqual(panel.x(), 0)
        self.assertGreaterEqual(panel.y(), 0)
        cards = scene._item_card_rects()
        self.assertEqual(len({rect.y() for rect in cards.values()}), 2)
        self.assertTrue(all(rect.width() < 180 for rect in cards.values()))
        self.assertTrue(all(rect.right() <= panel.right() for rect in cards.values()))

    def test_decoration_panel_close_button_exits_editing_without_leaving_home(self):
        state = progression.ensure_progression({})
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
            show=Mock(),
            raise_=Mock(),
            move=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.show_scene()
        scene.toggle_decoration_mode()

        close_button = scene.decoration_panel_close_button_rect()
        self.assertTrue(close_button.top() <= 16)
        self.assertTrue(all(
            rect.top() > close_button.bottom()
            for rect in scene._category_rects().values()
        ))
        self.assertTrue(scene.handle_scene_click(close_button.center()))
        self.assertFalse(scene.is_decorating())
        self.assertTrue(state["home_scene"]["enabled"])
        self.assertTrue(scene.isVisible())

    def test_selected_furniture_supports_ppt_style_move_scale_and_rotation(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            move=Mock(),
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.toggle_decoration_mode()
        scene.select_furniture("home_sofa")
        bounds = scene.selection_bounds("home_sofa")
        center = bounds.center().toPoint()

        self.assertTrue(scene.begin_furniture_gesture(center))
        scene.update_furniture_gesture(center + QPoint(40, -20))
        scene.end_furniture_gesture(center + QPoint(40, -20))
        self.assertEqual(
            progression.home_decoration_position(state, "home_sofa"),
            {"x": 250, "y": 340},
        )

        bounds = scene.selection_bounds("home_sofa")
        handles = scene.selection_handles("home_sofa")
        self.assertTrue(scene.begin_furniture_gesture(handles["se"].center().toPoint()))
        scene.end_furniture_gesture(bounds.center().toPoint() + QPoint(216, 135))
        self.assertAlmostEqual(
            progression.home_decoration_transform(state, "home_sofa")["scale"], 1.2
            , places=2
        )

        bounds = scene.selection_bounds("home_sofa")
        handles = scene.selection_handles("home_sofa")
        self.assertTrue(scene.begin_furniture_gesture(handles["rotate"].center().toPoint()))
        scene.end_furniture_gesture(bounds.center().toPoint() + QPoint(160, 0))
        self.assertAlmostEqual(
            progression.home_decoration_transform(state, "home_sofa")["rotation"], 90.0
            , places=0
        )

        scene.toggle_decoration_mode()
        self.assertFalse(scene.begin_furniture_gesture(center))

    def test_decoration_mode_can_store_and_transform_owned_furniture(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        save = Mock()
        scene = home_scene.HomeSceneWindow(pet, save)
        self.addCleanup(scene.close)
        scene.toggle_decoration_mode()
        self.assertTrue(scene.is_decorating())
        self.assertTrue(scene.store_furniture("home_sofa"))
        self.assertIn("home_sofa", state["home_stored_decorations"])
        self.assertTrue(scene.place_furniture("home_sofa"))
        scene.select_furniture("home_sofa")
        self.assertEqual(scene.adjust_selected_furniture("scale", 0.1), {"scale": 1.1, "rotation": 0.0})
        self.assertEqual(scene.adjust_selected_furniture("rotation", 15), {"scale": 1.1, "rotation": 15.0})
        scene.toggle_decoration_mode()
        self.assertFalse(scene.is_decorating())

    def test_owned_furniture_can_be_rendered_with_a_transform(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.toggle_decoration_mode()
        scene.select_furniture("home_sofa")
        scene.adjust_selected_furniture("rotation", 15)
        canvas = QPixmap(900, 768)
        canvas.fill(Qt.transparent)
        painter = QPainter(canvas)
        scene._draw_furniture(
            painter,
            "home_sofa",
            state["home_decoration_positions"]["home_sofa"],
        )
        painter.end()
        self.assertFalse(canvas.isNull())

    def test_decoration_draws_bottom_panel_and_selected_handles(self):
        state = progression.ensure_progression({"pet_coins": 500})
        progression.purchase_home_decoration(state, "home_sofa")
        pet = SimpleNamespace(
            state=state,
            width=lambda: 190,
            height=lambda: 220,
            current_screen_rect=lambda: QRect(0, 0, 1280, 720),
            move=Mock(),
        )
        scene = home_scene.HomeSceneWindow(pet, Mock())
        self.addCleanup(scene.close)
        scene.resize(900, 768)
        scene.toggle_decoration_mode()
        scene.select_furniture("home_sofa")
        canvas = QPixmap(900, 768)
        canvas.fill(Qt.transparent)
        scene.render(canvas)
        image = canvas.toImage()
        self.assertGreater(image.pixelColor(scene._panel_rect().center()).alpha(), 0)
        handle = scene.selection_handles("home_sofa")["rotate"].center().toPoint()
        self.assertGreater(image.pixelColor(handle).alpha(), 0)


if __name__ == "__main__":
    unittest.main()
