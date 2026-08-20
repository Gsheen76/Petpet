"""Persistent player and stable-pet state compatibility helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable


STATE_SCHEMA_VERSION = 3
DEFAULT_PET_ID = "lunch_meat"
_FACADE_SNAPSHOT_KEY = "_active_pet_facade_snapshot"
_DEFAULT_PET_NAME_KEY = "_default_pet_name"

PLAYER_FIELDS = (
    "born", "autostart", "tutorial_completed", "level", "xp",
    "passive_xp_buffer", "pet_coins", "pending_dig_reward",
    "last_dig_discovery_at", "minigame_best_scores", "records",
    "upgrades", "owned_decorations", "owned_outfits",
    "owned_home_decorations", "home_scene", "home_decoration_positions",
    "home_stored_decorations", "home_decoration_transforms",
    "claimed_achievements",
)

PET_FIELDS = (
    "pet_name", "hunger", "mood", "energy", "affection_level",
    "affection_points", "passive_affection_buffer", "affection_last_gains",
    "sleeping", "sleep_mode", "x", "y", "desktop_position",
    "home_position", "chat_memory_key", "equipped_decorations",
    "decoration_adjustments", "equipped_outfit",
)

_PLAYER_DEFAULTS = {
    "born": 0.0, "autostart": False, "tutorial_completed": False,
    "level": 1, "xp": 0, "passive_xp_buffer": 0.0, "pet_coins": 0,
    "pending_dig_reward": 0, "last_dig_discovery_at": 0.0,
    "minigame_best_scores": {}, "records": {}, "upgrades": {},
    "owned_decorations": [], "owned_outfits": [],
    "owned_home_decorations": [], "home_scene": {},
    "home_decoration_positions": {}, "home_stored_decorations": [],
    "home_decoration_transforms": {}, "claimed_achievements": [],
}

_PET_DEFAULTS = {
    "pet_name": "Sheen", "hunger": 80, "mood": 70, "energy": 90,
    "affection_level": 1, "affection_points": 0,
    "passive_affection_buffer": 0.0, "affection_last_gains": {},
    "sleeping": False, "sleep_mode": None, "x": None, "y": None,
    "desktop_position": None, "home_position": None,
    "chat_memory_key": None,
    "equipped_decorations": {}, "decoration_adjustments": {},
    "equipped_outfit": None,
}


def _copy_fields(source: dict, fields: tuple[str, ...], defaults: dict) -> dict:
    return {
        field: deepcopy(source.get(field, defaults[field]))
        for field in fields
    }


def _complete_fields(target: dict, source: dict, fields, defaults) -> None:
    for field in fields:
        if field not in target:
            target[field] = deepcopy(source.get(field, defaults[field]))


def _pet_defaults(state: dict | None = None) -> dict:
    defaults = deepcopy(_PET_DEFAULTS)
    if state is not None and isinstance(state.get(_DEFAULT_PET_NAME_KEY), str):
        defaults["pet_name"] = state[_DEFAULT_PET_NAME_KEY]
    return defaults


def _pets(state: dict) -> dict:
    pets = state.get("pets")
    if not isinstance(pets, dict):
        pets = {}
        state["pets"] = pets
    return pets


def _copy_to_facade(state: dict, source: dict, fields) -> None:
    for field in fields:
        state[field] = deepcopy(source[field])


def _facade_snapshot(state: dict) -> dict | None:
    snapshot = state.get(_FACADE_SNAPSHOT_KEY)
    return snapshot if isinstance(snapshot, dict) else None


def _capture_facade_fields(state: dict, target: dict, fields) -> None:
    snapshot = _facade_snapshot(state)
    for field in fields:
        if field in state and (
            snapshot is None or state[field] != snapshot.get(field)
        ):
            target[field] = deepcopy(state[field])


def _remember_facade(state: dict, fields) -> None:
    snapshot = _facade_snapshot(state) or {}
    for field in fields:
        if field in state:
            snapshot[field] = deepcopy(state[field])
    state[_FACADE_SNAPSHOT_KEY] = snapshot


def pet_profile(state: dict, pet_id: str) -> dict:
    """Return an independent normalized profile without changing the active pet."""
    if not isinstance(pet_id, str) or not pet_id:
        raise ValueError("pet_id must be a non-empty string")
    pets = _pets(state)
    profile = pets.get(pet_id)
    if not isinstance(profile, dict):
        profile = {}
        pets[pet_id] = profile
    _complete_fields(profile, {}, PET_FIELDS, _pet_defaults(state))
    profile["pet_name"] = str(
        profile.get("pet_name") or _pet_defaults(state)["pet_name"]
    )
    return profile


def active_pet_profile(state: dict) -> dict:
    """Return the normalized profile for the selected pet."""
    pet_id = state.get("active_pet_id")
    if not isinstance(pet_id, str) or not pet_id:
        pet_id = DEFAULT_PET_ID
        state["active_pet_id"] = pet_id
    return pet_profile(state, pet_id)


def _project_active_pet(state: dict) -> dict:
    profile = active_pet_profile(state)
    _copy_to_facade(state, state["player"], PLAYER_FIELDS)
    _copy_to_facade(state, profile, PET_FIELDS)
    _remember_facade(state, PLAYER_FIELDS + PET_FIELDS)
    return profile


def capture_active_pet(state: dict) -> dict:
    """Copy changed legacy pet facade fields into the active profile."""
    player = state.get("player")
    if not isinstance(player, dict):
        player = {}
        state["player"] = player
    _capture_facade_fields(state, player, PLAYER_FIELDS)
    profile = active_pet_profile(state)
    _capture_facade_fields(state, profile, PET_FIELDS)
    _remember_facade(state, PLAYER_FIELDS + PET_FIELDS)
    return profile


def bind_active_pet(state: dict, pet_id: str) -> dict:
    """Capture the old facade, select ``pet_id``, and project its facade."""
    capture_active_pet(state)
    profile = pet_profile(state, pet_id)
    state["active_pet_id"] = pet_id
    owned_pet_ids = state.setdefault("owned_pet_ids", [])
    if pet_id not in owned_pet_ids:
        owned_pet_ids.append(pet_id)
    return _project_active_pet(state)


def ensure_state_schema(
    state: dict,
    default_pet_name: str,
    normalize_pet_name: Callable[[object], str],
) -> dict:
    """Create and hydrate the shared-player/stable-pet save structure."""
    state[_DEFAULT_PET_NAME_KEY] = normalize_pet_name(default_pet_name)
    player = state.get("player")
    if not isinstance(player, dict):
        player = _copy_fields(state, PLAYER_FIELDS, _PLAYER_DEFAULTS)
        state["player"] = player
    else:
        _complete_fields(player, state, PLAYER_FIELDS, _PLAYER_DEFAULTS)

    pets = _pets(state)
    legacy_desktop = pets.get("desktop")
    legacy_home = pets.get("home")
    lunch_meat = pets.get(DEFAULT_PET_ID)
    if not isinstance(lunch_meat, dict):
        source = (
            legacy_desktop if isinstance(legacy_desktop, dict)
            else legacy_home if isinstance(legacy_home, dict)
            else state
        )
        lunch_meat = _copy_fields(source, PET_FIELDS, _PET_DEFAULTS)
        pets[DEFAULT_PET_ID] = lunch_meat
    else:
        _complete_fields(lunch_meat, {}, PET_FIELDS, _pet_defaults(state))
    pets.pop("desktop", None)
    pets.pop("home", None)

    for profile in pets.values():
        if isinstance(profile, dict):
            _complete_fields(profile, {}, PET_FIELDS, _pet_defaults(state))
            profile["pet_name"] = normalize_pet_name(
                profile.get("pet_name", default_pet_name)
            )

    active_pet_id = state.get("active_pet_id")
    if (
        not isinstance(active_pet_id, str)
        or not active_pet_id
        or active_pet_id in {"desktop", "home"}
        or not isinstance(pets.get(active_pet_id), dict)
    ):
        active_pet_id = DEFAULT_PET_ID
    state["active_pet_id"] = active_pet_id

    owned_pet_ids = state.get("owned_pet_ids")
    if not isinstance(owned_pet_ids, list):
        owned_pet_ids = []
    owned_pet_ids = [
        pet_id for index, pet_id in enumerate(owned_pet_ids)
        if isinstance(pet_id, str) and pet_id not in owned_pet_ids[:index]
    ]
    for pet_id in (DEFAULT_PET_ID, active_pet_id):
        if pet_id not in owned_pet_ids:
            owned_pet_ids.append(pet_id)
    state["owned_pet_ids"] = owned_pet_ids

    _project_active_pet(state)
    state["state_schema_version"] = STATE_SCHEMA_VERSION
    return state


def prepare_state_for_save(state: dict) -> dict:
    """Capture legacy facade changes before serializing a stable-ID save."""
    player = state.get("player")
    if not isinstance(player, dict):
        player = {}
        state["player"] = player
    _complete_fields(player, state, PLAYER_FIELDS, _PLAYER_DEFAULTS)
    _capture_facade_fields(state, player, PLAYER_FIELDS)
    capture_active_pet(state)
    state["state_schema_version"] = STATE_SCHEMA_VERSION
    return state
