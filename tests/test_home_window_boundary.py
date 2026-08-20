import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

from petpet.progression import core as progression
from petpet.home.pet import HOME_DEFAULT_ENTRY


@pytest.fixture
def home_window():
    app = QApplication.instance() or QApplication([])
    state = progression.ensure_progression({})
    state["pets"] = {
        "lunch_meat": {"home_position": None, "sleeping": False},
        "ice_cream": {"home_position": None, "sleeping": False},
    }
    pet = SimpleNamespace(
        state=state,
        width=lambda: 190,
        height=lambda: 220,
        current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
    )
    from petpet.home.window import HomeSceneWindow

    window = HomeSceneWindow(pet, Mock())
    yield window
    window.close()
    app.processEvents()


class HomeWindowBoundaryTests(unittest.TestCase):
    def test_root_home_window_is_package_owned(self):
        import home_scene
        from petpet.home.window import HomeSceneWindow

        self.assertIs(home_scene.HomeSceneWindow, HomeSceneWindow)


def test_lunch_meat_home_uses_desktop_idle_asset(home_window):
    home_window.refresh_pet_assets("lunch_meat")

    assert home_window.home_pet_asset_state()["idle"].endswith(
        "pets/desktop/poses/idle.png"
    )


def test_missing_home_walk_falls_back_to_active_pet_idle(home_window):
    home_window.refresh_pet_assets("lunch_meat")

    assert home_window.home_pet_asset_state()["walk"] == "idle"


def test_home_idle_renders_the_desktop_animation_frame(home_window):
    frame = QPixmap(32, 48)
    frame.fill()
    home_window.pet.shared_animation_frame = lambda: {
        "name": "idle",
        "pixmap": frame,
        "frame_index": 3,
        "spec": {"scale": 1.2},
    }
    home_window.home_pet.state = "idle"

    spec = home_window.home_pet_render_spec(now=0.0)

    assert spec.pixmap.cacheKey() == frame.cacheKey()
    assert spec.frame_index == 3
    assert spec.visual_scale == 1.2


def test_home_position_is_saved_per_pet(home_window):
    home_window.state["active_pet_id"] = "ice_cream"
    home_window.home_pet.position = (321.0, 455.0)

    home_window._save_home_pet_position()

    assert home_window.state["pets"]["ice_cream"]["home_position"] == [
        321.0,
        455.0,
    ]


def test_pet_without_home_position_uses_default_not_global_mirror(home_window):
    home_window.state["active_pet_id"] = "lunch_meat"
    home_window.home_pet.position = (700.0, 600.0)
    home_window._save_home_pet_position()

    home_window.state["active_pet_id"] = "ice_cream"
    home_window.state["pets"]["ice_cream"]["home_position"] = None
    home_window._reset_home_pet_controller()

    assert home_window.home_pet.position == HOME_DEFAULT_ENTRY


def test_refresh_active_pet_resets_controller_and_assets(home_window):
    home_window.state["active_pet_id"] = "ice_cream"
    home_window.state["pets"]["ice_cream"]["home_position"] = [321.0, 455.0]

    home_window.refresh_active_pet()

    assert home_window.current_pet_id == "ice_cream"
    assert home_window.home_pet.position == (321.0, 455.0)
    assert home_window.home_pet_asset_state()["pet_id"] == "ice_cream"


def test_home_controller_movement_is_saved_to_active_pet(home_window):
    home_window.state["active_pet_id"] = "ice_cream"
    home_window.home_pet.command_move((600.0, 620.0), now=0.0)
    home_window._last_pet_tick = 0.0

    home_window._advance_home_pet(now=0.1)

    assert home_window.state["pets"]["ice_cream"]["home_position"] == [
        468.0,
        620.0,
    ]


if __name__ == "__main__":
    unittest.main()
