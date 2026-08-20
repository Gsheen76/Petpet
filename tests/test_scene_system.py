import unittest

from PyQt5.QtCore import QPoint, QRect

import scene_system


class HomeSceneGeometryTests(unittest.TestCase):
    def test_home_viewport_uses_requested_height(self):
        self.assertEqual(scene_system.HOME_VIEWPORT_SIZE, (900, 768))

    def test_camera_tracks_dog_until_each_world_edge(self):
        self.assertEqual(scene_system.camera_x_for_dog(0, 190), 0)
        self.assertEqual(scene_system.camera_x_for_dog(900, 190), 545)
        self.assertEqual(scene_system.camera_x_for_dog(1800, 190), 900)

    def test_manual_view_pan_moves_in_fixed_steps_and_clamps(self):
        self.assertEqual(scene_system.pan_viewport_x(450, "left", 220), 230)
        self.assertEqual(scene_system.pan_viewport_x(230, "left", 220), 10)
        self.assertEqual(scene_system.pan_viewport_x(10, "left", 220), 0)
        self.assertEqual(scene_system.pan_viewport_x(800, "right", 220), 900)

    def test_home_decoration_transform_is_normalized(self):
        self.assertEqual(
            scene_system.normalize_home_decoration_transform(
                {"scale": 4, "rotation": 725}
            ),
            {"scale": 1.5, "rotation": 5.0},
        )

    def test_dog_clamp_keeps_full_dog_inside_scene_board(self):
        point = scene_system.clamp_dog_to_scene(
            QRect(-50, 600, 190, 220), QRect(100, 100, 900, 540)
        )
        self.assertEqual(point, QPoint(100, 420))

    def test_scene_rect_stays_inside_selected_screen(self):
        rect = scene_system.scene_rect_for_screen(
            QRect(1000, 40, 1920, 1080), saved_x=2800, saved_y=900
        )
        self.assertEqual(rect, QRect(2020, 352, 900, 768))

    def test_invalid_scene_state_receives_safe_defaults(self):
        state = scene_system.normalize_home_scene({
            "enabled": "yes",
            "background_visible": 0,
            "screen_index": -3,
            "viewport_x": "bad",
            "viewport_y": float("inf"),
        })
        self.assertEqual(state, {
            "enabled": True,
            "background_visible": False,
            "screen_index": 0,
            "viewport_x": 0,
            "viewport_y": 0,
            "viewport_pinned": False,
            "decorating": False,
        })

    def test_furniture_position_is_clamped_using_its_authored_size(self):
        position = scene_system.clamp_home_furniture_position(
            "home_sofa", -80, 900
        )
        self.assertEqual(position, {"x": 0, "y": 543})

    def test_decoration_selection_bounds_and_handles_cover_transformed_item(self):
        bounds = scene_system.home_decoration_bounds(
            {"x": 500, "y": 140}, (360, 225),
            {"scale": 1.0, "rotation": 30.0}, camera_x=200,
        )

        self.assertLess(bounds.left(), 300)
        self.assertGreater(bounds.right(), 660)
        handles = scene_system.home_decoration_handles(bounds)
        self.assertEqual(
            set(handles),
            {"nw", "n", "ne", "e", "se", "s", "sw", "w", "rotate"},
        )
        self.assertEqual(handles["nw"].center().toPoint(), bounds.topLeft().toPoint())
        self.assertLess(handles["rotate"].center().y(), bounds.top())

    def test_selection_handle_scale_and_rotation_match_pointer_geometry(self):
        center = QPoint(400, 300)
        self.assertEqual(
            scene_system.scale_from_handle(
                center, QPoint(670, 450), "se", (360, 200), 0.0, 1.0
            ),
            1.5,
        )
        self.assertEqual(
            scene_system.scale_from_handle(
                center, QPoint(400, 150), "n", (360, 200), 0.0, 1.0
            ),
            1.5,
        )
        self.assertEqual(scene_system.rotation_from_pointer(center, QPoint(400, 140)), 0.0)
        self.assertEqual(scene_system.rotation_from_pointer(center, QPoint(560, 300)), 90.0)


if __name__ == "__main__":
    unittest.main()
