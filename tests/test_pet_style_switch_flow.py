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
    # 2026-10-26 流畅度轮:重载/表面刷新移 QTimer.singleShot(0) 下一拍
    # ——断言前跑一轮事件循环
    from PyQt5.QtWidgets import QApplication
    _qapp = QApplication.instance() or QApplication([])
    result = app.set_pet_style("lunch_meat", "classic")
    _qapp.processEvents()
    assert result["ok"] is True
    assert app.state["pets"]["lunch_meat"]["style"] == "classic"
    assert app.pet.refreshed == ["lunch_meat"]
    # 2026-10-26 缓存复用契约:不再清双风格条目(键含风格,资产不可变,
    # 目标风格命中即秒切);别的宠不受影响
    assert ("ice_cream", "new") in app.pet._pet_assets_cache
    # processEvents 会排干其他用例遗留的单拍定时器(含别的 state 引用)
    # ——断言本状态的同步存档在场即可,不锚最后一条
    assert any(x is app.state for x in app._saved)
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


def test_set_pet_style_non_active_pet_only_writes_state(app):
    from PyQt5.QtWidgets import QApplication
    _qapp = QApplication.instance() or QApplication([])
    result = app.set_pet_style("ice_cream", "new")
    assert result["ok"] is True
    assert app.state["pets"]["ice_cream"]["style"] == "new"
    # 非出勤宠不动桌面表面(重活虽延后,仍不触碰桌面)
    _qapp.processEvents()
    assert app.pet.refreshed == []
