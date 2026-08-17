"""Persistent player and dual-pet state compatibility helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable


STATE_SCHEMA_VERSION = 2

PLAYER_FIELDS = (
    "born",
    "autostart",
    "tutorial_completed",
    "level",
    "xp",
    "passive_xp_buffer",
    "pet_coins",
    "pending_dig_reward",
    "last_dig_discovery_at",
    "minigame_best_scores",
    "records",
    "upgrades",
    "owned_decorations",
    "owned_home_decorations",
    "home_scene",
    "home_decoration_positions",
    "home_stored_decorations",
    "home_decoration_transforms",
    "claimed_achievements",
)

PET_FIELDS = (
    "pet_name",
    "hunger",
    "mood",
    "energy",
    "affection_level",
    "affection_points",
    "passive_affection_buffer",
    "affection_last_gains",
    "sleeping",
    "sleep_mode",
    "x",
    "y",
    "equipped_decorations",
    "decoration_adjustments",
)

_PLAYER_DEFAULTS = {
    "born": 0.0,
    "autostart": False,
    "tutorial_completed": False,
    "level": 1,
    "xp": 0,
    "passive_xp_buffer": 0.0,
    "pet_coins": 0,
    "pending_dig_reward": 0,
    "last_dig_discovery_at": 0.0,
    "minigame_best_scores": {},
    "records": {},
    "upgrades": {},
    "owned_decorations": [],
    "owned_home_decorations": [],
    "home_scene": {},
    "home_decoration_positions": {},
    "home_stored_decorations": [],
    "home_decoration_transforms": {},
    "claimed_achievements": [],
}

_PET_DEFAULTS = {
    "pet_name": "Sheen",
    "hunger": 80,
    "mood": 70,
    "energy": 90,
    "affection_level": 1,
    "affection_points": 0,
    "passive_affection_buffer": 0.0,
    "affection_last_gains": {},
    "sleeping": False,
    "sleep_mode": None,
    "x": None,
    "y": None,
    "equipped_decorations": {},
    "decoration_adjustments": {},
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


def _hydrate_legacy_fields(state: dict, source: dict, fields) -> None:
    for field in fields:
        if field in source:
            state[field] = deepcopy(source[field])


def ensure_state_schema(
    state: dict,
    default_pet_name: str,
    normalize_pet_name: Callable[[object], str],
) -> dict:
    """Create and hydrate the shared-player/two-pet save structure.

    Existing nested profiles are authoritative. Legacy top-level fields remain
    a temporary desktop compatibility facade while callers migrate gradually.
    """
    player = state.get("player")
    if not isinstance(player, dict):
        player = _copy_fields(state, PLAYER_FIELDS, _PLAYER_DEFAULTS)
        state["player"] = player
    else:
        _complete_fields(player, state, PLAYER_FIELDS, _PLAYER_DEFAULTS)

    pets = state.get("pets")
    if not isinstance(pets, dict):
        pets = {}
        state["pets"] = pets

    desktop = pets.get("desktop")
    if not isinstance(desktop, dict):
        desktop = _copy_fields(state, PET_FIELDS, _PET_DEFAULTS)
        pets["desktop"] = desktop
    else:
        _complete_fields(desktop, state, PET_FIELDS, _PET_DEFAULTS)

    desktop["pet_name"] = normalize_pet_name(
        desktop.get("pet_name", default_pet_name)
    )

    home = pets.get("home")
    if not isinstance(home, dict):
        home = deepcopy(desktop)
        pets["home"] = home
    else:
        _complete_fields(home, desktop, PET_FIELDS, _PET_DEFAULTS)
    home["pet_name"] = normalize_pet_name(
        home.get("pet_name", default_pet_name)
    )

    _hydrate_legacy_fields(state, player, PLAYER_FIELDS)
    _hydrate_legacy_fields(state, desktop, PET_FIELDS)
    state["state_schema_version"] = STATE_SCHEMA_VERSION
    return state


def prepare_state_for_save(state: dict) -> dict:
    """Capture legacy facade changes without overwriting the home pet."""
    player = state.setdefault("player", {})
    if not isinstance(player, dict):
        player = {}
        state["player"] = player
    for field in PLAYER_FIELDS:
        if field in state:
            player[field] = deepcopy(state[field])

    pets = state.setdefault("pets", {})
    if not isinstance(pets, dict):
        pets = {}
        state["pets"] = pets
    desktop = pets.setdefault("desktop", {})
    if not isinstance(desktop, dict):
        desktop = {}
        pets["desktop"] = desktop
    for field in PET_FIELDS:
        if field in state:
            desktop[field] = deepcopy(state[field])

    if not isinstance(pets.get("home"), dict):
        pets["home"] = deepcopy(desktop)
    state["state_schema_version"] = STATE_SCHEMA_VERSION
    return state
