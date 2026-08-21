import json

import pytest

import petpet.app.pets as pets
from petpet.app.pets import (
    DEFAULT_PET_ID,
    load_pet_registry,
    pet_asset_path,
    pet_definition,
    pet_display_name,
)


def test_registry_contains_lunch_meat_and_ice_cream():
    registry = load_pet_registry()

    assert DEFAULT_PET_ID == "lunch_meat"
    assert "lunch_meat" in registry
    assert registry["lunch_meat"]["default_name"] == "午餐肉"
    assert registry["ice_cream"]["default_name"] == "冰淇淋"
    assert registry["ice_cream"]["original_price"] == 1000
    assert registry["ice_cream"]["discount"] == 0.76
    assert registry["ice_cream"]["price"] == 760


def test_valid_action_is_selected_before_current_pet_idle(monkeypatch, tmp_path):
    monkeypatch.setattr(pets, "ASSETS_DIR", str(tmp_path))
    action = tmp_path / "pets" / "custom" / "poses" / "play.png"
    idle = tmp_path / "pets" / "custom" / "idle.png"
    action.parent.mkdir(parents=True)
    action.touch()
    idle.touch()
    monkeypatch.setattr(
        pets,
        "pet_definition",
        lambda _pet_id: {
            "id": "custom",
            "default_name": "Custom",
            "preview": "pets/custom/preview.png",
            "home": {"root": "pets/custom", "idle": "pets/custom/idle.png"},
        },
    )

    assert pet_asset_path("custom", "home", "play") == action.as_posix()


def test_missing_action_falls_back_to_current_pet_idle():
    assert pet_asset_path("ice_cream", "desktop", "play").endswith(
        "pets/ice_cream/desktop/poses/idle.png"
    )


def test_registered_assets_are_owned_by_the_selected_pet():
    assert pet_asset_path("lunch_meat", "desktop", "idle").endswith(
        "pets/lunch_meat/desktop/poses/idle.png"
    )
    assert pet_asset_path("ice_cream", "home", "idle").endswith(
        "pets/ice_cream/home/poses/home-pet-idle-sit.png"
    )
    assert pet_asset_path("lunch_meat", "home", "sleep").endswith(
        "pets/lunch_meat/desktop/poses/idle.png"
    )


def test_unknown_pet_falls_back_to_default():
    assert pet_definition("unknown")["id"] == "lunch_meat"


def test_pet_display_name_prefers_pet_nickname():
    state = {"pets": {"ice_cream": {"name": "甜筒"}}}

    assert pet_display_name("ice_cream", state) == "甜筒"


def test_pet_display_name_falls_back_to_default_name():
    assert pet_display_name("ice_cream", {}) == "冰淇淋"


def test_unknown_pet_display_name_uses_default_pet_nickname():
    state = {"pets": {"lunch_meat": {"name": "small meat"}}}

    assert pet_display_name("unknown", state) == "small meat"


def test_nested_path_fields_are_validated(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "lunch_meat": {
                    "id": "lunch_meat",
                    "default_name": "lunch",
                    "preview": "pets/desktop/poses/idle.png",
                    "metadata": {"resources": [{"asset_path": "../outside.png"}]},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pets, "PETS_MANIFEST_PATH", str(manifest_path))

    with pytest.raises(ValueError, match="escapes"):
        load_pet_registry()


def test_asset_path_does_not_escape_runtime_assets():
    assert pet_asset_path("ice_cream", "desktop", "../manifest.json").endswith(
        "pets/ice_cream/desktop/poses/idle.png"
    )
