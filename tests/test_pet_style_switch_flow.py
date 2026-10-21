"""宠物风格切换:TrayApp 风格切换事务测试(2026-10-21 风格切换轮)。

壳化 TrayApp(不跑 __init__),逐环断言写档/资产重载/缓存清理/存盘/家园刷新。
"""

import pytest

import pet as pet_module
from pet import TrayApp


class _RecordingPet:
    def __init__(self):
        self.refreshed = []
        self._pet_assets_cache = {
            ("lunch_meat", "new"): object(),
            ("lunch_meat", "classic"): object(),
            ("ice_cream", "new"): object(),
        }

    def refresh_pet_assets(self, pet_id=None):
        self.refreshed.append(pet_id)


class _RecordingHome:
    def __init__(self):
        self.calls = 0

    def refresh_active_pet(self):
        self.calls += 1


@pytest.fixture
def app(monkeypatch):
    tray = TrayApp.__new__(TrayApp)
    tray.state = {"active_pet_id": "lunch_meat", "pets": {"lunch_meat": {}}}
    tray.pet = _RecordingPet()
    tray.home_scene_window = _RecordingHome()
    saved = []
    monkeypatch.setattr(pet_module, "save_state", lambda state: saved.append(state))
    tray._saved = saved
    return tray


def test_set_pet_style_updates_state_and_surfaces(app):
    result = app.set_pet_style("lunch_meat", "classic")
    assert result["ok"] is True
    assert app.state["pets"]["lunch_meat"]["style"] == "classic"
    assert app.pet.refreshed == ["lunch_meat"]
    # 该宠的双风格缓存全部清理,别的宠不受影响
    assert ("lunch_meat", "new") not in app.pet._pet_assets_cache
    assert ("lunch_meat", "classic") not in app.pet._pet_assets_cache
    assert ("ice_cream", "new") in app.pet._pet_assets_cache
    assert app._saved and app._saved[-1] is app.state
    assert app.home_scene_window.calls == 1


def test_set_pet_style_rejects_unknown(app):
    result = app.set_pet_style("lunch_meat", "bogus")
    assert result["ok"] is False
    assert result.get("message")
    assert "style" not in app.state["pets"]["lunch_meat"]
    assert app.pet.refreshed == []
    assert app._saved == []


def test_set_pet_style_single_style_pet_rejected(app):
    result = app.set_pet_style("marshmallow", "new")
    assert result["ok"] is False
    assert "marshmallow" not in app.state["pets"]
