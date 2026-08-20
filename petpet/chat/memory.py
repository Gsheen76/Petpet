"""Profile-aware JSON persistence for independent pet chat memories."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Callable

from petpet.app.pets import DEFAULT_PET_ID, load_pet_registry

def normalize_memory_pet_id(value: object) -> str:
    """Return a registered pet ID, mapping old profile names to lunch meat."""
    candidate = str(value or "").strip().lower()
    if candidate in {"desktop", "home"}:
        return DEFAULT_PET_ID
    try:
        registered_ids = load_pet_registry()
    except (OSError, ValueError, TypeError):
        registered_ids = {DEFAULT_PET_ID: {}}
    return candidate if candidate in registered_ids else DEFAULT_PET_ID


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def load_memory(
    path: str,
    default_factory: Callable[[], dict],
    seed_path: str | None = None,
) -> dict:
    """Load one profile, seeding a missing file from another profile once."""
    loaded = _read_json(path)
    if loaded is None and not os.path.exists(path) and seed_path:
        seeded = _read_json(seed_path)
        if seeded is not None:
            loaded = deepcopy(seeded)
            save_memory(path, loaded)
    defaults = default_factory()
    if not isinstance(defaults, dict):
        defaults = {}
    return {**deepcopy(defaults), **deepcopy(loaded or {})}


def save_memory(path: str, memory: dict) -> None:
    """Persist a memory document without exposing a partially-written file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(memory, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temporary_path)
        except OSError:
            pass
