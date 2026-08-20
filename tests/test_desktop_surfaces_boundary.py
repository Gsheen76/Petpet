import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from petpet.app import state as app_state


class _SwitchChat:
    def __init__(self):
        self.pet_id = "lunch_meat"
        self.refresh_count = 0

    def set_pet_id(self, pet_id):
        self.pet_id = pet_id
        return True

    def refresh_pet_name(self):
        self.refresh_count += 1


class _SwitchSurface:
    def __init__(self):
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1


class _SwitchHome:
    def __init__(self, state):
        self.state = state
        self.refresh_count = 0

    @property
    def current_pet_id(self):
        return self.state["active_pet_id"]

    def refresh_active_pet(self):
        self.refresh_count += 1


class _SwitchPet:
    def __init__(self, state):
        self.state = state
        self.chat_win = _SwitchChat()
        self.shop_win = _SwitchSurface()
        self.records_win = _SwitchSurface()
        self.achievements_win = _SwitchSurface()
        self.home_scene_window = _SwitchHome(state)
        self.asset_pet_ids = []
        self.update_count = 0
        self.position = [320, 240]
        self.safe_position = [900, 700]
        self.placement_count = 0

    @property
    def current_pet_id(self):
        return self.state["active_pet_id"]

    @property
    def pet_name(self):
        return self.state["pet_name"]

    def active_chat_pet_id(self):
        return self.current_pet_id

    def refresh_pet_assets(self, pet_id):
        self.asset_pet_ids.append(pet_id)

    def x(self):
        return self.position[0]

    def y(self):
        return self.position[1]

    def _capture_desktop_position(self):
        import pet

        return pet.PetWindow._capture_desktop_position(self)

    def place_initial(self):
        profile = self.state["pets"][self.current_pet_id]
        self.position = list(
            profile.get("desktop_position") or self.safe_position
        )
        self.placement_count += 1

    def update(self):
        self.update_count += 1

    def set_pet_name(self, value):
        import pet

        return pet.PetWindow.set_pet_name(self, value)


def _switch_app():
    import pet

    state = app_state.ensure_state_schema(
        {**copy.deepcopy(pet.DEFAULT_STATE), "pet_name": "午餐肉"},
        "午餐肉",
        lambda value: str(value or "午餐肉"),
    )
    state["pets"]["lunch_meat"]["pet_name"] = "午餐肉"
    state["pet_name"] = "午餐肉"
    app_state.capture_active_pet(state)
    ice_cream = app_state.pet_profile(state, "ice_cream")
    ice_cream["pet_name"] = "冰淇淋"
    state["owned_pet_ids"].append("ice_cream")
    state["player"]["pet_coins"] = 123
    app_state.bind_active_pet(state, "lunch_meat")

    app = object.__new__(pet.TrayApp)
    app.state = state
    app.pet = _SwitchPet(state)
    app.home_scene_window = app.pet.home_scene_window
    app.tray = SimpleNamespace(setToolTip=Mock())
    return app


class DesktopSurfacesBoundaryTests(unittest.TestCase):
    def test_root_desktop_surfaces_are_owned_by_ui_package(self):
        import pet
        from petpet.ui import desktop

        for name in (
            "StatBubble",
            "BubbleMenu",
            "BonusBubble",
            "InteractiveBubble",
            "SpeechBubble",
        ):
            self.assertIs(getattr(pet, name), getattr(desktop, name))

    def test_anchor_helpers_are_package_owned(self):
        import pet
        from petpet.ui import desktop

        self.assertIs(pet._pet_interface_anchor_rect, desktop.pet_interface_anchor_rect)
        self.assertIs(pet._pet_interface_screen_rect, desktop.pet_interface_screen_rect)


def test_switch_refreshes_desktop_home_chat_shop_and_shared_progress():
    import pet

    app = _switch_app()
    with patch.object(pet, "save_state") as save_state:
        result = app.set_active_pet("ice_cream")

    assert result["ok"] is True
    assert app.pet.current_pet_id == "ice_cream"
    assert app.home_scene_window.current_pet_id == "ice_cream"
    assert app.state["player"]["pet_coins"] == 123
    assert app.pet.asset_pet_ids == ["ice_cream"]
    assert app.home_scene_window.refresh_count == 1
    assert app.pet.chat_win.pet_id == "ice_cream"
    assert app.pet.chat_win.refresh_count == 1
    assert app.pet.shop_win.refresh_count == 1
    assert app.pet.records_win.refresh_count == 1
    assert save_state.call_count == 1


def test_switch_rejects_unowned_pet_without_saving():
    import pet

    app = _switch_app()
    app.state["owned_pet_ids"].remove("ice_cream")
    with patch.object(pet, "save_state") as save_state:
        rejected = app.set_active_pet("ice_cream")

    assert rejected["ok"] is False
    assert app.state["active_pet_id"] == "lunch_meat"
    assert save_state.call_count == 0


def test_busy_chat_keeps_its_visible_pet_context_during_app_switch():
    import pet
    from petpet.ui.chat import ChatWindow

    class TextControl:
        def __init__(self, text):
            self.text = text

        def setText(self, text):
            self.text = text

        def setToolTip(self, text):
            self.text = text

    app = _switch_app()
    chat = ChatWindow.__new__(ChatWindow)
    chat.pet = app.pet
    chat.busy = True
    chat.pet_id = "lunch_meat"
    chat.memory_profile = "lunch_meat"
    chat.mem = {
        "pet_name": "午餐肉",
        "history": [{"role": "assistant", "content": "old stream"}],
    }
    chat._ui_built = True
    chat.title = TextControl("  午餐肉")
    chat.clear_btn = TextControl("让 午餐肉 忘记所有对话")
    app.pet.chat_win = chat

    with patch.object(pet, "save_state"):
        result = app.set_active_pet("ice_cream")

    assert result["ok"] is False
    assert app.state["active_pet_id"] == "lunch_meat"
    assert chat.pet_id == "lunch_meat"
    assert chat.memory_profile == "lunch_meat"
    assert chat.mem == {
        "pet_name": "午餐肉",
        "history": [{"role": "assistant", "content": "old stream"}],
    }
    assert chat.title.text == "  午餐肉"


def test_busy_chat_rejects_switch_before_capture_bind_save_or_refresh():
    import pet
    from petpet.ui.chat import ChatWindow

    class TextControl:
        def __init__(self, text):
            self.text = text

        def setText(self, text):
            self.text = text

        def setToolTip(self, text):
            self.text = text

    app = _switch_app()
    chat = ChatWindow.__new__(ChatWindow)
    chat.pet = app.pet
    chat.busy = True
    chat.pet_id = "lunch_meat"
    chat.memory_profile = "lunch_meat"
    chat.mem = {"pet_name": "午餐肉", "history": []}
    chat._ui_built = True
    chat.title = TextControl("  午餐肉")
    chat.clear_btn = TextControl("让 午餐肉 忘记所有对话")
    app.pet.chat_win = chat

    with (
        patch.object(pet, "save_state") as save_state,
        patch.object(app.pet, "_capture_desktop_position") as capture,
        patch.object(app.pet, "refresh_pet_assets") as refresh_assets,
        patch.object(app.pet, "place_initial") as place_initial,
        patch.object(app.home_scene_window, "refresh_active_pet") as refresh_home,
        patch.object(app.pet.shop_win, "refresh") as refresh_shop,
        patch.object(app.pet.records_win, "refresh") as refresh_records,
        patch.object(app.pet.achievements_win, "refresh") as refresh_achievements,
        patch.object(chat, "set_pet_id", wraps=chat.set_pet_id) as set_pet_id,
    ):
        result = app.set_active_pet("ice_cream")

    assert result["ok"] is False
    assert app.state["active_pet_id"] == "lunch_meat"
    assert app.pet.pet_name == "午餐肉"
    assert chat.pet_id == "lunch_meat"
    assert chat.memory_profile == "lunch_meat"
    assert chat.mem["pet_name"] == "午餐肉"
    assert chat.title.text == "  午餐肉"
    save_state.assert_not_called()
    capture.assert_not_called()
    refresh_assets.assert_not_called()
    place_initial.assert_not_called()
    refresh_home.assert_not_called()
    refresh_shop.assert_not_called()
    refresh_records.assert_not_called()
    refresh_achievements.assert_not_called()
    set_pet_id.assert_not_called()


@pytest.mark.parametrize(
    ("target_position", "expected_position"),
    [([640, 360], [640, 360]), (None, [900, 700])],
)
def test_switch_captures_live_old_position_before_target_placement(
    target_position, expected_position
):
    import pet

    app = _switch_app()
    app.pet.position = [333, 222]
    app.state["pets"]["lunch_meat"]["desktop_position"] = [10, 20]
    app.state["pets"]["ice_cream"]["desktop_position"] = target_position

    with patch.object(pet, "save_state"):
        result = app.set_active_pet("ice_cream")

    assert result["ok"] is True
    assert app.state["pets"]["lunch_meat"]["desktop_position"] == [333, 222]
    assert app.pet.position == expected_position
    assert app.pet.placement_count == 1

    app.pet._capture_desktop_position()
    assert app.state["pets"]["ice_cream"]["desktop_position"] == expected_position


def test_closed_surfaces_are_dropped_after_state_is_saved():
    import pet

    class ClosedSurface:
        def refresh(self):
            raise RuntimeError("wrapped C++ object has been deleted")

        def refresh_active_pet(self):
            raise RuntimeError("wrapped C++ object has been deleted")

        def set_pet_id(self, _pet_id):
            raise RuntimeError("wrapped C++ object has been deleted")

        def refresh_pet_name(self):
            raise RuntimeError("wrapped C++ object has been deleted")

    app = _switch_app()
    app.pet.chat_win = ClosedSurface()
    app.pet.shop_win = ClosedSurface()
    app.pet.records_win = ClosedSurface()
    app.pet.achievements_win = ClosedSurface()
    app.pet.home_scene_window = ClosedSurface()
    app.home_scene_window = app.pet.home_scene_window

    with patch.object(pet, "save_state") as save_state:
        result = app.set_active_pet("ice_cream")

    assert result["ok"] is True
    assert app.state["active_pet_id"] == "ice_cream"
    assert save_state.call_count == 1
    assert app.pet.chat_win is None
    assert app.pet.shop_win is None
    assert app.pet.records_win is None
    assert app.pet.achievements_win is None
    assert app.pet.home_scene_window is None


def test_names_and_chat_memory_follow_active_pet(tmp_path, monkeypatch):
    import pet

    monkeypatch.setattr(pet.ai, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pet.ai, "MEMORY_PATH", str(tmp_path / "memory.json"))
    monkeypatch.setattr(
        pet,
        "save_state",
        lambda state: app_state.prepare_state_for_save(state),
    )
    app = _switch_app()

    app.set_active_pet("ice_cream")
    app.pet.set_pet_name("甜筒")
    app.set_active_pet("lunch_meat")
    assert app.pet.pet_name == "午餐肉"
    app.set_active_pet("ice_cream")

    assert app.pet.pet_name == "甜筒"
    assert app.state["pets"]["ice_cream"]["pet_name"] == "甜筒"
    assert pet.ai.load_memory("ice_cream")["pet_name"] == "甜筒"


if __name__ == "__main__":
    unittest.main()
