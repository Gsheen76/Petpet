"""Profile-aware JSON persistence for independent pet chat memories."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Callable


MEMORY_PROFILES = ("desktop", "home")


def normalize_profile(profile: object) -> str:
    """Return a supported pet profile, defaulting old callers to desktop."""
    value = str(profile or "").strip().lower()
    return value if value in MEMORY_PROFILES else "desktop"


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
