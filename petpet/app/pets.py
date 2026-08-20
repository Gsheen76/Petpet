"""Runtime pet registry and asset resolution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import ASSETS_DIR, PETS_MANIFEST_PATH


DEFAULT_PET_ID = "lunch_meat"
_PATH_KEY_HINTS = ("path", "file", "asset", "image", "preview", "root", "manifest")
_PATH_CONTAINER_KEYS = {"desktop", "home", "resources", "assets", "actions", "poses", "animations"}


def _asset_path(value: str) -> Path:
    if not isinstance(value, str) or not value or os.path.isabs(value):
        raise ValueError("pet asset paths must be non-empty relative strings")
    root = Path(ASSETS_DIR).resolve()
    candidate = (root / Path(value)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("pet asset path escapes the runtime asset directory") from exc
    return candidate


def _validate_definition(pet_id: str, definition: Any) -> dict[str, Any]:
    if not isinstance(definition, dict):
        raise ValueError(f"pet definition {pet_id!r} must be an object")
    if definition.get("id") != pet_id or not isinstance(pet_id, str) or not pet_id:
        raise ValueError(f"pet definition {pet_id!r} has an invalid id")
    if not isinstance(definition.get("default_name"), str) or not definition["default_name"].strip():
        raise ValueError(f"pet definition {pet_id!r} has an invalid default name")

    def validate_paths(
        value: Any,
        key: str | None = None,
        path_context: bool = False,
    ) -> None:
        key_is_path = isinstance(key, str) and any(
            hint in key.lower() for hint in _PATH_KEY_HINTS
        )
        child_path_context = path_context or key_is_path or key in _PATH_CONTAINER_KEYS
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                validate_paths(child_value, child_key, child_path_context)
        elif isinstance(value, list):
            for item in value:
                validate_paths(item, key, child_path_context)
        elif child_path_context and isinstance(value, str):
            _asset_path(value)

    validate_paths(definition)
    return definition


def load_pet_registry() -> dict[str, dict]:
    with open(PETS_MANIFEST_PATH, "r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("pet manifest must contain pet definitions")
    registry = {
        pet_id: _validate_definition(pet_id, definition)
        for pet_id, definition in manifest.items()
    }
    if DEFAULT_PET_ID not in registry:
        raise ValueError(f"pet manifest must define {DEFAULT_PET_ID!r}")
    return registry


def pet_definition(pet_id: str) -> dict:
    registry = load_pet_registry()
    return registry.get(pet_id, registry[DEFAULT_PET_ID])


def _candidate_path(definition: dict, value: str | None) -> str | None:
    if not value:
        return None
    try:
        path = _asset_path(value)
    except ValueError:
        return None
    return path.as_posix() if path.is_file() else None


def pet_asset_path(pet_id: str, scene: str, action: str = "idle") -> str | None:
    definition = pet_definition(pet_id)
    scene_definition = definition.get(scene)
    if not isinstance(scene_definition, dict):
        return _candidate_path(definition, definition.get("preview"))

    root = scene_definition.get("root")
    candidates = [scene_definition.get(action)]
    if isinstance(root, str):
        candidates.append(f"{root}/poses/{action}.png")
    candidates.append(scene_definition.get("idle"))
    if isinstance(root, str):
        candidates.append(f"{root}/poses/idle.png")
    for value in candidates:
        resolved = _candidate_path(definition, value)
        if resolved:
            return resolved

    return _candidate_path(definition, definition.get("preview"))


def pet_display_name(pet_id: str, state: dict) -> str:
    definition = pet_definition(pet_id)
    normalized_pet_id = definition["id"]
    profile = state.get("pets", {}).get(normalized_pet_id, {}) if isinstance(state, dict) else {}
    if not isinstance(profile, dict):
        profile = {}
    name = profile.get("name") or profile.get("pet_name")
    return name if isinstance(name, str) and name.strip() else definition["default_name"]
