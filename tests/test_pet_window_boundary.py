import copy
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication


class PetWindowBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_root_pet_window_is_owned_by_app_package(self):
        import pet
        from petpet.app.pet_window import PetWindow

        self.assertIs(pet.PetWindow, PetWindow)

    def test_default_animation_name_uses_configured_pose_mapping(self):
        import pet
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._animation_override = None
        window.state = {}
        window.dragging = False
        window.behavior = "idle"
        window.pose = pet.POSE["idle"]

        self.assertEqual(window._current_animation_name(), "idle")

    def test_awake_stationary_state_always_uses_idle_animation(self):
        import pet
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._animation_override = None
        window.state = {"sleeping": False}
        window.dragging = False
        window.behavior = "idle"
        window.pose = pet.POSE["happy"]

        self.assertEqual(window._current_animation_name(), "idle")

    def test_passive_sit_behavior_uses_idle_animation(self):
        import pet
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._animation_override = None
        window.state = {"sleeping": False}
        window.dragging = False
        window.behavior = "sit"
        window.pose = pet.POSE["idle"]

        self.assertEqual(window._current_animation_name(), "idle")

    def test_equipped_outfit_uses_its_idle_animation(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._animation_override = None
        window.state = {
            "sleeping": False,
            "owned_outfits": ["dinosaur_suit"],
            "equipped_outfit": "dinosaur_suit",
        }
        window.dragging = False
        window.behavior = "idle"
        window.animation_frames = {"idle": [object()], "idle_dinosaur": [object()]}

        self.assertEqual(window._current_animation_name(), "idle_dinosaur")

    def test_drag_preview_uses_the_equipped_outfit_reference(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window.state = {
            "owned_outfits": ["dinosaur_suit"],
            "equipped_outfit": "dinosaur_suit",
        }

        preview = MagicMock()
        preview.isNull.return_value = False
        with patch(
            "petpet.app.pet_window.QPixmap", return_value=preview
        ) as pixmap:
            self.assertIs(window._equipped_outfit_preview(), preview)
            pixmap.assert_called_once()

    def test_drag_preview_is_absent_without_an_equipped_outfit(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window.state = {"owned_outfits": [], "equipped_outfit": None}

        self.assertIsNone(window._equipped_outfit_preview())

    def test_drag_preview_does_not_use_an_outfit_from_another_pet(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window.state = {
            "active_pet_id": "ice_cream",
            "owned_outfits": ["dinosaur_suit"],
            "equipped_outfit": "dinosaur_suit",
        }
        window._outfit_preview_cache = {}

        with patch("petpet.app.pet_window.QPixmap") as pixmap:
            self.assertIsNone(window._equipped_outfit_preview())
            pixmap.assert_not_called()

    def test_right_mouse_release_opens_the_bubble_menu(self):
        from petpet.app.pet_window import PetWindow

        class Event:
            def button(self):
                return Qt.RightButton

            def accept(self):
                self.accepted = True

        window = PetWindow.__new__(PetWindow)
        window.open_bubble_menu = MagicMock()
        event = Event()

        window.mouseReleaseEvent(event)

        window.open_bubble_menu.assert_called_once_with()
        self.assertTrue(event.accepted)

    def test_presence_guard_restores_an_unexpectedly_hidden_pet(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._user_hidden = False
        window.play_scene = None
        window.home_scene_window = None
        window.settings = {"always_on_top": True}
        window.isVisible = MagicMock(return_value=False)
        window.show = MagicMock()
        window.raise_ = MagicMock()
        window.windowFlags = MagicMock(return_value=Qt.WindowStaysOnTopHint)
        window._presence_guard_t = 0.0

        self.assertTrue(window._maintain_desktop_presence(now=5.0))
        window.show.assert_called_once_with()
        window.raise_.assert_called_once_with()

    def test_presence_guard_respects_an_intentional_hide(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window._user_hidden = True
        window.isVisible = MagicMock(return_value=False)
        window.show = MagicMock()
        window.raise_ = MagicMock()

        self.assertFalse(window._maintain_desktop_presence(now=2.0))
        window.show.assert_not_called()
        window.raise_.assert_not_called()

    def test_idle_animation_defaults_match_the_sixteen_frame_sequence(self):
        import pet

        self.assertEqual(pet.DEFAULT_ANIMATIONS["idle"]["fps"], 8)
        self.assertEqual(pet.DEFAULT_DEBUG_PARAMETERS["animation_idle_fps"], 8.0)

    def test_animation_frame_uses_authored_per_frame_durations(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window.animation_frames = {"idle": list(range(16))}
        window.animation_specs = {
            "idle": {
                "fps": 8,
                "loop": True,
                "frame_durations_ms": [
                    139.423076923, 139.423076923, 139.423076923,
                    139.423076923, 139.423076923, 139.423076923,
                    62.5, 62.5, 62.5,
                    139.423076923, 139.423076923, 139.423076923,
                    139.423076923, 139.423076923, 139.423076923,
                    139.423076923,
                ],
            }
        }
        window._active_animation = "idle"
        window._animation_started_at = 0.0

        with patch("petpet.app.pet_window.time.monotonic", return_value=1.05):
            self.assertEqual(window._animation_frame("idle"), 9)

    def test_animation_cache_releases_inactive_action_frames(self):
        from petpet.app.pet_window import PetWindow

        loaded = {
            "idle": [object()],
            "pet": [object()],
            "eat": [object()],
        }

        kept = PetWindow._retained_animation_names(
            loaded, {"idle"}, "eat"
        )

        self.assertEqual(kept, {"idle", "eat"})

    def test_animation_decode_size_is_bounded_for_runtime_memory(self):
        from petpet.app.pet_window import PetWindow

        self.assertEqual(PetWindow.ANIMATION_MAX_SIZE, 384)

    def test_stat_decay_uses_a_half_rate_for_existing_profiles(self):
        from petpet.app.pet_window import PetWindow

        self.assertEqual(PetWindow.STAT_DECAY_RATE_MULTIPLIER, 0.5)

    def test_sleep_at_full_energy_does_not_consume_hunger(self):
        from petpet.app.pet_window import PetWindow

        window = PetWindow.__new__(PetWindow)
        window.settings = {}
        window.state = {
            "sleeping": True,
            "energy": 100,
            "hunger": 50,
        }
        window.refresh_pose_from_state = MagicMock()
        window.say = MagicMock()

        with patch(
            "petpet.app.pet_window._dependency", return_value=lambda _state: None
        ):
            window.on_decay()

        self.assertEqual(window.state["energy"], 100)
        self.assertEqual(window.state["hunger"], 50)

    def test_window_preloads_frequent_interaction_animations(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            self.assertEqual(
                set(window.animation_frames),
                {"idle", "pet", "eat", "play", "sleep", "dig_reward"},
            )
            self.assertIn("idle_strawberry", window._animation_frame_paths)
        finally:
            window.close()

    def test_ice_cream_sleep_reuses_the_home_eight_frame_spritesheet(self):
        import pet
        from petpet.app.paths import ASSETS_DIR

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            self.assertEqual(len(window.animation_frames["sleep"]), 12)
            self.assertEqual(window.animation_specs["sleep"]["fps"], 2.4)
            self.assertEqual(window.animation_specs["sleep"]["scale"], 0.7)
            self.assertTrue(window.animation_specs["sleep"]["anchor_bottom"])

            window.refresh_pet_assets("ice_cream")

            frames = window.animation_frames["sleep"]
            spec = window.animation_specs["sleep"]
            sheet_path = (
                Path(ASSETS_DIR)
                / "pets"
                / "ice_cream"
                / "home"
                / "poses"
                / "home-pet-sleep.png"
            )
            expected_first = QPixmap(str(sheet_path)).copy(24, 176, 592, 288)
            expected_first = expected_first.scaled(
                384, 384, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            expected_last = QPixmap(str(sheet_path)).copy(
                664, 1456, 592, 288
            )
            expected_last = expected_last.scaled(
                384, 384, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            self.assertEqual(len(frames), 8)
            self.assertEqual(spec["fps"], 3)
            self.assertAlmostEqual(spec["scale"], 0.62)
            self.assertTrue(spec["anchor_bottom"])
            self.assertEqual(frames[0].size(), expected_first.size())
            self.assertEqual(frames[0].toImage(), expected_first.toImage())
            self.assertEqual(frames[-1].size(), expected_last.size())
            self.assertEqual(frames[-1].toImage(), expected_last.toImage())
        finally:
            window.close()

    def test_spritesheet_rejects_frame_count_above_limit_before_iteration(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)
            window.animation_specs["sleep"].update({
                "frame_size": 1,
                "frame_count": 65,
                "columns": 65,
                "content_rect": [0, 0, 1, 1],
            })

            with patch(
                "petpet.app.pet_window.range", return_value=(), create=True
            ) as frame_range:
                window._load_animation("sleep")

            self.assertNotIn("sleep", window.animation_frames)
            self.assertIn("sleep", window._failed_animation_names)
            frame_range.assert_not_called()
        finally:
            window.close()

    def test_spritesheet_content_rect_may_start_at_the_cell_edge(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)
            window.animation_specs["sleep"]["content_rect"] = [0, 176, 592, 288]

            window._load_animation("sleep")

            self.assertEqual(len(window.animation_frames["sleep"]), 8)
        finally:
            window.close()

    def test_spritesheet_content_rect_accepts_zero_y_origin_independently(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)
            window.animation_specs["sleep"]["content_rect"] = [24, 0, 592, 288]

            window._load_animation("sleep")

            self.assertEqual(len(window.animation_frames["sleep"]), 8)
        finally:
            window.close()

    def test_spritesheet_rejects_oversized_source_before_pixmap_decode(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)

            with patch(
                "petpet.app.pet_window.QImageReader", create=True
            ) as reader_type, patch(
                "petpet.app.pet_window.QPixmap", wraps=QPixmap
            ) as pixmap_loader:
                reader_type.return_value.size.return_value = QSize(4097, 4096)
                window._load_animation("sleep")

            self.assertNotIn("sleep", window.animation_frames)
            self.assertIn("sleep", window._failed_animation_names)
            pixmap_loader.assert_not_called()
        finally:
            window.close()

    def test_spritesheet_rejects_unreadable_dimensions_before_pixmap_decode(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)

            with patch(
                "petpet.app.pet_window.QImageReader", create=True
            ) as reader_type, patch(
                "petpet.app.pet_window.QPixmap", wraps=QPixmap
            ) as pixmap_loader:
                reader_type.return_value.size.return_value = QSize()
                window._load_animation("sleep")

            self.assertNotIn("sleep", window.animation_frames)
            self.assertIn("sleep", window._failed_animation_names)
            pixmap_loader.assert_not_called()
        finally:
            window.close()

    def test_spritesheet_source_at_exact_pixel_budget_is_accepted(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)

            with patch(
                "petpet.app.pet_window.QImageReader", create=True
            ) as reader_type:
                reader_type.return_value.size.return_value = QSize(4096, 4096)
                window._load_animation("sleep")

            self.assertEqual(len(window.animation_frames["sleep"]), 8)
        finally:
            window.close()

    def test_invalid_spritesheet_crop_is_discarded_and_failed_until_refresh(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)
            source = QPixmap(window._animation_frame_paths["sleep"][0])

            class PartialSheet:
                def __init__(self, invalid_crop):
                    self.copy_count = 0
                    self.invalid_crop = invalid_crop

                def isNull(self):
                    return False

                def width(self):
                    return source.width()

                def height(self):
                    return source.height()

                def copy(self, *args):
                    self.copy_count += 1
                    if self.copy_count == 2:
                        return self.invalid_crop
                    return source.copy(*args)

            invalid_crops = (
                ("null", QPixmap()),
                ("undersized", source.copy(24, 176, 591, 288)),
            )
            for label, invalid_crop in invalid_crops:
                with self.subTest(crop=label):
                    window.animation_frames.pop("sleep", None)
                    window._failed_animation_names.discard("sleep")
                    partial = PartialSheet(invalid_crop)
                    with patch(
                        "petpet.app.pet_window.QPixmap", return_value=partial
                    ) as pixmap_loader:
                        window._load_animation("sleep")
                        window._load_animation("sleep")

                    self.assertNotIn("sleep", window.animation_frames)
                    self.assertIn("sleep", window._failed_animation_names)
                    self.assertEqual(pixmap_loader.call_count, 1)

            window.refresh_pet_assets("ice_cream")
            self.assertEqual(len(window.animation_frames["sleep"]), 8)
        finally:
            window.close()

    def test_invalid_spritesheet_is_failed_without_decode_until_assets_refresh(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            window.animation_frames.pop("sleep", None)
            window.animation_specs["sleep"]["content_rect"] = [
                24, 176, 617, 288
            ]

            with patch(
                "petpet.app.pet_window.QImageReader"
            ) as reader_type, patch(
                "petpet.app.pet_window.QPixmap", wraps=QPixmap
            ) as pixmap_loader:
                first = window._animation_frame("sleep")
                second = window._animation_frame("sleep")

            self.assertIsNone(first)
            self.assertIsNone(second)
            self.assertIn("sleep", window._failed_animation_names)
            reader_type.assert_not_called()
            pixmap_loader.assert_not_called()

            window.refresh_pet_assets("ice_cream")
            self.assertEqual(len(window.animation_frames["sleep"]), 8)
        finally:
            window.close()

    def test_malformed_spritesheet_metadata_uses_the_static_fallback(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")
            valid_spec = dict(window.animation_specs["sleep"])
            malformed_values = (
                {"frame_size": True},
                {"frame_count": True},
                {"columns": True},
                {"content_rect": [-1, 176, 592, 288]},
                {"content_rect": [24, 176, 617, 288]},
                {"columns": 4},
            )
            for malformed in malformed_values:
                with self.subTest(malformed=malformed):
                    window.animation_specs["sleep"] = {
                        **valid_spec,
                        **malformed,
                    }
                    window.animation_frames.pop("sleep", None)
                    window._failed_animation_names.discard("sleep")
                    window._load_animation("sleep")
                    self.assertNotIn("sleep", window.animation_frames)

            window.state["sleeping"] = True
            shared = window.shared_animation_frame()

            self.assertIsNotNone(shared)
            self.assertEqual(shared["name"], "sleep")
            self.assertEqual(
                shared["pixmap"].cacheKey(),
                window.pose_pixmaps[pet.POSE["sleep"]].cacheKey(),
            )
        finally:
            window.close()

    def test_refresh_pet_assets_uses_selected_pet_idle_and_clears_stale_cache(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.animation_frames["obsolete"] = [object()]
            window._animation_frame_paths["obsolete"] = ["obsolete.png"]
            window._outfit_preview_cache = {"dinosaur_suit": object()}

            window.refresh_pet_assets("ice_cream")

            self.assertEqual(window.current_pet_id, "ice_cream")
            self.assertEqual(state.get("active_pet_id"), None)
            self.assertEqual(window._fallback_pose("play"), pet.POSE["idle"])
            self.assertNotIn("obsolete", window.animation_frames)
            self.assertNotIn("obsolete", window._animation_frame_paths)
            self.assertEqual(window._outfit_preview_cache, {})
            self.assertEqual(len(window.pose_pixmaps), len(pet.POSE))
        finally:
            window.close()

    def test_shared_animation_frame_falls_back_to_desktop_static_pose(self):
        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets("ice_cream")

            shared = window.shared_animation_frame()

            self.assertIsNotNone(shared)
            self.assertEqual(shared["name"], "idle")
            self.assertFalse(shared["pixmap"].isNull())
        finally:
            window.close()

    def test_place_initial_prefers_active_pet_desktop_position(self):
        import pet
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            copy.deepcopy(pet.DEFAULT_STATE),
            pet.ai.DEFAULT_PET_NAME,
            pet.ai.normalize_pet_name,
        )
        state.update({"x": 700, "y": 500, "tutorial_completed": True})
        state["pets"]["lunch_meat"]["desktop_position"] = [100, 120]

        window = pet.PetWindow(state)
        try:
            self.assertEqual(window.pos().x(), 100)
            self.assertEqual(window.pos().y(), 120)
        finally:
            window.close()

    def test_set_active_pet_rejection_does_not_refresh_or_mutate_state(self):
        import pet
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            copy.deepcopy(pet.DEFAULT_STATE),
            pet.ai.DEFAULT_PET_NAME,
            pet.ai.normalize_pet_name,
        )
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            rejection = {"ok": False, "message": "not owned"}
            window._set_active_pet_callback = lambda _pet_id: rejection
            window.refresh_pet_assets = MagicMock()

            result = window.set_active_pet("ice_cream")

            self.assertIs(result, rejection)
            self.assertEqual(state["active_pet_id"], "lunch_meat")
            self.assertEqual(window.current_pet_id, "lunch_meat")
            window.refresh_pet_assets.assert_not_called()
        finally:
            window.close()

    def test_set_active_pet_without_callback_rejects_without_mutating_state(self):
        import pet
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            copy.deepcopy(pet.DEFAULT_STATE),
            pet.ai.DEFAULT_PET_NAME,
            pet.ai.normalize_pet_name,
        )
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        try:
            window.refresh_pet_assets = MagicMock()

            result = window.set_active_pet("ice_cream")

            self.assertFalse(result)
            self.assertEqual(state["active_pet_id"], "lunch_meat")
            self.assertEqual(window.current_pet_id, "lunch_meat")
            window.refresh_pet_assets.assert_not_called()
        finally:
            window.close()

    def test_set_active_pet_captures_the_old_profile_through_its_callback(self):
        import pet
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            copy.deepcopy(pet.DEFAULT_STATE),
            pet.ai.DEFAULT_PET_NAME,
            pet.ai.normalize_pet_name,
        )
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        state["mood"] = 91
        window = pet.PetWindow(state)
        try:
            window._set_active_pet_callback = (
                lambda pet_id: app_state.bind_active_pet(state, pet_id)
            )

            window.set_active_pet("ice_cream")

            self.assertEqual(state["pets"]["lunch_meat"]["mood"], 91)
            self.assertEqual(state["active_pet_id"], "ice_cream")
            self.assertEqual(window.current_pet_id, "ice_cream")
            self.assertEqual(window.pose, pet.POSE["idle"])
        finally:
            window.close()

    def test_set_active_pet_forwards_transaction_without_refreshing_assets(self):
        import pet

        window = pet.PetWindow.__new__(pet.PetWindow)
        window._set_active_pet_callback = MagicMock(
            return_value={"ok": True, "pet_id": "ice_cream"}
        )
        window.refresh_pet_assets = MagicMock()

        result = window.set_active_pet("ice_cream")

        self.assertEqual(result["pet_id"], "ice_cream")
        window._set_active_pet_callback.assert_called_once_with("ice_cream")
        window.refresh_pet_assets.assert_not_called()

    def test_set_active_pet_forwards_unknown_raw_id_for_transaction_rejection(self):
        import pet

        window = pet.PetWindow.__new__(pet.PetWindow)
        window._current_pet_id = "lunch_meat"
        received_pet_ids = []

        def reject_unknown_pet(pet_id):
            received_pet_ids.append(pet_id)
            return {"ok": False, "pet_id": pet_id}

        window._set_active_pet_callback = reject_unknown_pet

        result = window.set_active_pet("unknown_pet")

        self.assertEqual(received_pet_ids, ["unknown_pet"])
        self.assertEqual(result, {"ok": False, "pet_id": "unknown_pet"})
        self.assertEqual(window._current_pet_id, "lunch_meat")

    def test_menu_warmup_constructs_hidden_windows_before_native_show(self):
        from petpet.app.pet_window import PetWindow

        class FakeTimer:
            def stop(self):
                pass

        class FakeMenu:
            def __init__(self):
                self.stat_bubble = None
                self._anim = FakeTimer()
                self.show_calls = 0

            def move(self, *_args):
                pass

            def repaint(self):
                pass

            def show(self):
                self.show_calls += 1

        menus = []

        def make_menu(*args, **kwargs):
            menus.append((args, kwargs))
            return FakeMenu()

        window = PetWindow.__new__(PetWindow)
        window.isVisible = MagicMock(return_value=True)
        window._bubble_menu = None
        window._prewarmed_bubble_menus = {}

        with patch(
            "petpet.app.pet_window._dependency",
            side_effect=lambda name: make_menu if name == "BubbleMenu" else None,
        ):
            window._warm_up_interaction_surfaces()

        self.assertEqual(len(menus), 3)
        self.assertTrue(all(item[1]["show_window"] is False for item in menus))


if __name__ == "__main__":
    unittest.main()
