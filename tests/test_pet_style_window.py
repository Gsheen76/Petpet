"""宠物风格切换:桌面资产装载风格接线测试(2026-10-21 风格切换轮)。

用真实清单与已提交的 desktop_new 资产做解析级验证,不构造完整 PetWindow。
"""

import pytest
from PyQt5.QtWidgets import QApplication

from petpet.app import pet_window as pw
from petpet.app import pets
from petpet.app.pet_window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _shell(state):
    window = PetWindow.__new__(PetWindow)
    window.state = state
    window._current_pet_id = pets.pet_definition(
        state.get("active_pet_id", "lunch_meat")
    )["id"]
    return window


def test_current_pet_style_helper_reads_state():
    # 分级默认:批产收口前缺省 classic
    assert _shell({"active_pet_id": "lunch_meat"})._current_pet_style() == "classic"
    state = {"active_pet_id": "lunch_meat",
             "pets": {"lunch_meat": {"style": "new"}}}
    assert _shell(state)._current_pet_style() == "new"
    # 单风格宠物返回 None,解析照旧走基线
    assert _shell({"active_pet_id": "marshmallow"})._current_pet_style() is None


def test_manifest_path_new_style_when_profile_says_so():
    state = {"active_pet_id": "lunch_meat",
             "pets": {"lunch_meat": {"style": "new"}}}
    path = _shell(state)._desktop_animation_manifest_path()
    assert path and "desktop_new" in path


def test_manifest_path_defaults_to_classic_until_batch_done():
    path = _shell({"active_pet_id": "lunch_meat"})._desktop_animation_manifest_path()
    assert path and "desktop_new" not in path


def test_single_style_pet_manifest_unaffected():
    path = _shell({"active_pet_id": "marshmallow"})._desktop_animation_manifest_path()
    assert path and "desktop_new" not in path


def test_pose_loader_passes_style(qapp, monkeypatch):
    window = _shell({"active_pet_id": "lunch_meat",
                     "pets": {"lunch_meat": {"style": "new"}}})
    captured = {}
    real = pw.pet_asset_path

    def spy(pet_id, scene, action="idle", style=None):
        captured[action] = style
        return real(pet_id, scene, action, style=style)

    monkeypatch.setattr(pw, "pet_asset_path", spy)
    monkeypatch.setattr(pw, "_dependency", lambda name: {"idle": 0})
    window.pose_pixmaps = {}
    window.use_png = False
    window._load_static_pose_assets()
    assert captured.get("idle") == "new"
    assert window.use_png is True


def test_pet_asset_cache_key_includes_style():
    state = {"active_pet_id": "lunch_meat",
             "pets": {"lunch_meat": {"style": "classic"}}}
    window = _shell(state)
    assert window._pet_asset_cache_key("lunch_meat") == ("lunch_meat", "classic")
    assert _shell({"active_pet_id": "lunch_meat"})._pet_asset_cache_key("lunch_meat") == \
        ("lunch_meat", "classic")
    # 单风格宠物键稳定(风格维度为 None)
    assert _shell({"active_pet_id": "marshmallow"})._pet_asset_cache_key("marshmallow") == \
        ("marshmallow", None)
