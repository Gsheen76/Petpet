"""宠物风格切换:注册表风格解析单源测试(2026-10-21 风格切换轮)。

夹具用临时清单+临时资产树,不依赖真实 runtime 素材;末尾另有
针对真实清单的断言(styles 块落地后生效)。
"""

import json

import pytest

from petpet.app import pets


def build_styled_registry(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    rels = [
        "pets/dog/desktop/poses/idle.png",
        "pets/dog/desktop_new/poses/idle.png",
        "pets/dog/avatar.png",
        "pets/dog/avatar_classic.png",
        "pets/lunch_meat/desktop/poses/idle.png",
        "pets/lunch_meat/avatar.png",
    ]
    for rel in rels:
        p = assets / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"png")
    manifest = {
        "dog": {
            "id": "dog",
            "default_name": "Dog",
            "preview": "pets/dog/desktop/poses/idle.png",
            "avatar": "pets/dog/avatar.png",
            "desktop": {"root": "pets/dog/desktop"},
            "styles": {
                "classic": {"avatar": "pets/dog/avatar_classic.png"},
                "new": {"desktop": {"root": "pets/dog/desktop_new"}},
            },
        },
        "lunch_meat": {
            "id": "lunch_meat",
            "default_name": "午餐肉",
            "preview": "pets/lunch_meat/desktop/poses/idle.png",
            "avatar": "pets/lunch_meat/avatar.png",
        },
    }
    manifest_path = assets / "pets" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(pets, "ASSETS_DIR", str(assets))
    monkeypatch.setattr(pets, "PETS_MANIFEST_PATH", str(manifest_path))
    pets._REGISTRY_CACHE.clear()
    return pets


@pytest.fixture
def styled_registry(tmp_path, monkeypatch):
    return build_styled_registry(tmp_path, monkeypatch)


def test_available_styles(styled_registry):
    assert styled_registry.available_styles("dog") == ["classic", "new"]
    assert styled_registry.available_styles("lunch_meat") == []
    assert styled_registry.available_styles("missing") == []


def test_definition_merge_overrides_desktop_root(styled_registry):
    merged = styled_registry.pet_definition("dog", "new")
    assert merged["desktop"]["root"] == "pets/dog/desktop_new"
    assert merged["avatar"] == "pets/dog/avatar.png"
    # 基线不被合并污染
    assert styled_registry.pet_definition("dog")["desktop"]["root"] == "pets/dog/desktop"
    # 单风格宠物传 style 也不合并
    assert styled_registry.pet_definition("lunch_meat", "new") == \
        styled_registry.pet_definition("lunch_meat")


def test_classic_avatar_override(styled_registry):
    assert styled_registry.pet_avatar_path("dog", "classic").endswith("avatar_classic.png")
    assert styled_registry.pet_avatar_path("dog", "new").endswith("avatar.png")
    assert styled_registry.pet_avatar_path("dog").endswith("avatar.png")


def test_asset_path_style_routes_tree(styled_registry):
    new_path = styled_registry.pet_asset_path("dog", "desktop", "idle", style="new")
    classic_path = styled_registry.pet_asset_path("dog", "desktop", "idle", style="classic")
    assert new_path and "desktop_new" in new_path
    assert classic_path and "desktop_new" not in classic_path


def test_resolve_pet_style_defaults_to_new(styled_registry):
    assert styled_registry.DEFAULT_STYLE == "new"
    assert styled_registry.resolve_pet_style("dog", None) == "new"
    assert styled_registry.resolve_pet_style("dog", "bogus") == "new"
    assert styled_registry.resolve_pet_style("dog", "classic") == "classic"
    assert styled_registry.resolve_pet_style("lunch_meat", "new") is None


def test_current_pet_style_reads_state(styled_registry):
    state = {"pets": {"dog": {"style": "classic"}}}
    assert styled_registry.current_pet_style("dog", state) == "classic"
    assert styled_registry.current_pet_style("dog", {}) == "new"
    assert styled_registry.current_pet_style("dog", {"pets": {"dog": {"style": "bogus"}}}) == "new"
    assert styled_registry.current_pet_style("lunch_meat", {}) is None


def test_real_registry_dual_style_pets():
    """真实清单:两犬双风格、棉花糖单风格、缺省新装(Task 3 落地后生效)。"""
    assert pets.available_styles("lunch_meat") == ["classic", "new"]
    assert pets.available_styles("ice_cream") == ["classic", "new"]
    assert pets.available_styles("marshmallow") == []
    assert pets.current_pet_style("lunch_meat", {}) == "new"
    assert "avatar_classic" in (pets.pet_avatar_path("lunch_meat", "classic") or "")
