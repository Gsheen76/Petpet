"""Runtime pet registry and asset resolution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import ASSETS_DIR, PETS_MANIFEST_PATH


DEFAULT_PET_ID = "lunch_meat"
# 分级默认(2026-10-21 风格切换轮):批产完成前缺省经典,防止仅有 idle 的
# 新装树让全部交互落回待机;批产收口时翻回 "new"(用户定稿=默认新装)。
# TODO(style-switch): 批产完成后改回 "new" 并同步翻转两处测试期望。
DEFAULT_STYLE = "classic"
STYLE_LABELS = {"classic": "经典", "new": "新装"}
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


_REGISTRY_CACHE: dict[str, object] = {}


def load_pet_registry() -> dict[str, dict]:
    # Parsing + path-validating every asset on each call cost >0.6s/s in
    # the paint loop; cache until the manifest file actually changes.
    try:
        stat = os.stat(PETS_MANIFEST_PATH)
        stamp = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        stamp = None
    cached = _REGISTRY_CACHE.get("registry")
    if cached is not None and _REGISTRY_CACHE.get("stamp") == stamp:
        return cached
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
    _REGISTRY_CACHE["stamp"] = stamp
    _REGISTRY_CACHE["registry"] = registry
    return registry


def available_styles(pet_id: str) -> list[str]:
    """列出宠物的可选画风键;无 styles 块的单风格宠物返回空表。"""
    styles = pet_definition(pet_id).get("styles")
    if not isinstance(styles, dict):
        return []
    return [key for key, value in styles.items() if isinstance(value, dict)]


def _merged_definition(definition: dict, style: str) -> dict:
    overrides = definition["styles"][style]
    merged = dict(definition)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def pet_definition(pet_id: str, style: str | None = None) -> dict:
    registry = load_pet_registry()
    definition = registry.get(pet_id, registry[DEFAULT_PET_ID])
    if style is not None and style in (definition.get("styles") or {}):
        return _merged_definition(definition, style)
    return definition


def is_classic_style(style: str | None) -> bool:
    """该画风下经典资产语义成立(经典或单风格基线)——套装生效判定的
    共享谓词,四处调用点单源(2026-10-21 code-review 采纳)。"""
    return style in (None, "classic")


def resolve_pet_style(pet_id: str, style_value) -> str | None:
    """归一化画风值:有效直返;无效/缺失回落 DEFAULT_STYLE;单风格宠物 None。"""
    styles = available_styles(pet_id)
    if not styles:
        return None
    if style_value in styles:
        return style_value
    return DEFAULT_STYLE if DEFAULT_STYLE in styles else styles[0]


def current_pet_style(pet_id: str, state: dict) -> str | None:
    """读存档里该宠的当前画风(缺省按新装处理)。"""
    profile = {}
    if isinstance(state, dict):
        raw = state.get("pets", {}).get(pet_definition(pet_id)["id"])
        if isinstance(raw, dict):
            profile = raw
    return resolve_pet_style(pet_id, profile.get("style"))


def _candidate_path(definition: dict, value: str | None) -> str | None:
    if not value:
        return None
    try:
        path = _asset_path(value)
    except ValueError:
        return None
    return path.as_posix() if path.is_file() else None


def pet_asset_path(pet_id: str, scene: str, action: str = "idle", style: str | None = None) -> str | None:
    definition = pet_definition(pet_id, style)
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


def pet_avatar_path(pet_id: str, style: str | None = None) -> str | None:
    """Return the pet's square portrait, falling back to its idle pose."""
    definition = pet_definition(pet_id, style)
    resolved = _candidate_path(definition, definition.get("avatar"))
    if resolved:
        return resolved
    return pet_asset_path(pet_id, "desktop", "idle", style=style)


def pet_display_name(pet_id: str, state: dict) -> str:
    definition = pet_definition(pet_id)
    normalized_pet_id = definition["id"]
    profile = state.get("pets", {}).get(normalized_pet_id, {}) if isinstance(state, dict) else {}
    if not isinstance(profile, dict):
        profile = {}
    name = profile.get("name") or profile.get("pet_name")
    return name if isinstance(name, str) and name.strip() else definition["default_name"]
