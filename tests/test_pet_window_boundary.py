import copy
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
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
