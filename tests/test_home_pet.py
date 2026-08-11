import math
import unittest

import home_pet


class HomePetGeometryTests(unittest.TestCase):
    def test_points_outside_floor_are_projected_to_walkable_polygon(self):
        self.assertEqual(
            home_pet.clamp_to_walkable((900.0, 100.0)),
            (900.0, 460.0),
        )
        x, y = home_pet.clamp_to_walkable((-200.0, 900.0))
        self.assertGreaterEqual(x, 0.0)
        self.assertLessEqual(y, 730.0)

    def test_four_directions_follow_screen_space_target_delta(self):
        self.assertEqual(home_pet.direction_for_delta(-10, 10), "front_left")
        self.assertEqual(home_pet.direction_for_delta(10, 10), "front_right")
        self.assertEqual(home_pet.direction_for_delta(-10, -10), "back_left")
        self.assertEqual(home_pet.direction_for_delta(10, -10), "back_right")

    def test_depth_scale_is_clamped_and_increases_toward_foreground(self):
        self.assertEqual(home_pet.depth_scale_for_y(100), 0.72)
        self.assertEqual(home_pet.depth_scale_for_y(900), 1.08)
        self.assertLess(
            home_pet.depth_scale_for_y(450),
            home_pet.depth_scale_for_y(700),
        )

    def test_position_load_migrates_legacy_x_and_rejects_non_finite_values(self):
        self.assertEqual(
            home_pet.load_home_pet_position({}, 900),
            (900.0, 620.0),
        )
        self.assertEqual(
            home_pet.load_home_pet_position(
                {"pet_position": {"x": 700, "y": 600}}
            ),
            (700.0, 600.0),
        )
        self.assertEqual(
            home_pet.load_home_pet_position(
                {"pet_position": {"x": math.inf, "y": "bad"}},
                legacy_x="bad",
            ),
            home_pet.HOME_DEFAULT_ENTRY,
        )

    def test_saved_position_on_old_far_edge_moves_to_new_floor_boundary(self):
        self.assertEqual(
            home_pet.load_home_pet_position(
                {"pet_position": {"x": 900.0, "y": 420.0}}
            ),
            (900.0, 460.0),
        )

    def test_position_serialization_contains_only_rounded_coordinates(self):
        self.assertEqual(
            home_pet.serialize_home_pet_position((720.125, 610.555)),
            {"x": 720.12, "y": 610.55},
        )


class HomePetMovementTests(unittest.TestCase):
    def test_manual_move_advances_by_elapsed_time_without_overshooting(self):
        pet = home_pet.HomePetController(
            (500.0, 600.0),
            walk_speed=100.0,
        )
        self.assertFalse(pet.command_move((600.0, 600.0), now=10.0))

        self.assertEqual(pet.advance(0.25), ())
        self.assertEqual(pet.position, (510.0, 600.0))
        for _ in range(9):
            events = pet.advance(0.1)

        self.assertEqual(events, ("arrived",))
        self.assertEqual(pet.position, (600.0, 600.0))
        self.assertEqual(pet.state, "idle")
        self.assertIsNone(pet.target)

    def test_new_manual_target_replaces_existing_target(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.command_move((700.0, 600.0), now=1.0)
        pet.command_move((400.0, 500.0), now=2.0)

        self.assertEqual(pet.target, (400.0, 500.0))
        self.assertEqual(pet.state, "manual_walk")
        self.assertEqual(pet.direction, "back_left")

    def test_large_frame_delta_is_capped(self):
        pet = home_pet.HomePetController(
            (500.0, 600.0),
            walk_speed=100.0,
        )
        pet.command_move((700.0, 600.0), now=1.0)

        pet.advance(10.0)

        self.assertEqual(pet.position, (510.0, 600.0))

    def test_cancel_target_keeps_position_and_returns_to_idle(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.command_move((700.0, 600.0), now=1.0)

        pet.cancel_target()

        self.assertEqual(pet.position, (500.0, 600.0))
        self.assertIsNone(pet.target)
        self.assertEqual(pet.state, "idle")


class HomePetSleepTests(unittest.TestCase):
    def test_manual_sleep_walk_emits_distinct_arrival_event(self):
        pet = home_pet.HomePetController(
            (500.0, 600.0),
            walk_speed=100.0,
        )

        self.assertTrue(
            pet.request_manual_sleep((510.0, 600.0), now=10.0)
        )
        self.assertEqual(pet.state, "manual_sleep_walk")
        self.assertEqual(
            pet.advance(1.0),
            ("arrived", "manual_sleep_started"),
        )
        self.assertEqual(pet.state, "sleeping")

    def test_auto_sleep_arrival_emits_sleep_started(self):
        pet = home_pet.HomePetController(
            (500.0, 600.0),
            walk_speed=100.0,
        )

        self.assertTrue(
            pet.request_auto_sleep((510.0, 600.0), now=10.0)
        )
        self.assertEqual(
            pet.advance(1.0),
            ("arrived", "sleep_started"),
        )
        self.assertEqual(pet.state, "sleeping")

    def test_manual_command_interrupts_sleep_and_starts_retry_cooldown(self):
        pet = home_pet.HomePetController(
            (500.0, 600.0),
            sleep_retry_seconds=60.0,
        )
        pet.set_sleeping()

        self.assertTrue(pet.command_move((600.0, 600.0), now=20.0))
        self.assertEqual(pet.sleep_retry_until, 80.0)
        self.assertFalse(
            pet.request_auto_sleep((400.0, 600.0), now=79.0)
        )
        pet.cancel_target()
        self.assertTrue(
            pet.request_auto_sleep((400.0, 600.0), now=80.0)
        )

    def test_manual_command_interrupts_auto_sleep_walk(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.request_auto_sleep((400.0, 600.0), now=10.0)

        self.assertTrue(pet.command_move((600.0, 600.0), now=20.0))
        self.assertEqual(pet.state, "manual_walk")
        self.assertEqual(pet.sleep_retry_until, 80.0)

    def test_manual_command_interrupts_manual_sleep_walk(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.request_manual_sleep((400.0, 600.0), now=10.0)

        self.assertTrue(pet.command_move((600.0, 600.0), now=20.0))
        self.assertEqual(pet.state, "manual_walk")
        self.assertEqual(pet.sleep_retry_until, 80.0)

    def test_cancel_target_cancels_manual_sleep_walk(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.request_manual_sleep((400.0, 600.0), now=10.0)

        pet.cancel_target()

        self.assertEqual(pet.state, "idle")
        self.assertIsNone(pet.target)

    def test_sleeping_pet_wakes_only_at_auto_wake_threshold(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.set_sleeping()

        self.assertFalse(pet.wake_if_recovered(79.9, 80.0))
        self.assertTrue(pet.wake_if_recovered(80.0, 80.0))
        self.assertEqual(pet.state, "idle")

    def test_auto_sleep_request_does_not_replace_manual_walk(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.command_move((600.0, 600.0), now=10.0)

        self.assertFalse(
            pet.request_auto_sleep((400.0, 600.0), now=11.0)
        )
        self.assertEqual(pet.target, (600.0, 600.0))


class HomePetRouteTests(unittest.TestCase):
    def test_route_footprints_shorten_and_alternate(self):
        full = home_pet.route_footprints(
            (100.0, 100.0),
            (400.0, 100.0),
        )
        short = home_pet.route_footprints(
            (250.0, 100.0),
            (400.0, 100.0),
        )

        self.assertGreater(len(full), len(short))
        self.assertGreater(len(full), 2)
        self.assertNotEqual(full[0]["mirrored"], full[1]["mirrored"])
        self.assertAlmostEqual(full[0]["angle"], 0.0)

    def test_route_footprints_follow_direction_and_stay_off_end_marker(self):
        footprints = home_pet.route_footprints(
            (100.0, 100.0),
            (100.0, 300.0),
            spacing=40.0,
        )

        self.assertGreater(len(footprints), 1)
        self.assertTrue(all(item["y"] < 280.0 for item in footprints))
        self.assertTrue(
            all(abs(item["angle"] - 90.0) < 1e-6 for item in footprints)
        )


if __name__ == "__main__":
    unittest.main()
