"""Versioned, player-facing Petpet gameplay knowledge."""

from __future__ import annotations

import json
import os

from app_paths import ASSETS_DIR
from version import VERSION


KNOWLEDGE_PATH = os.path.join(ASSETS_DIR, "knowledge", "game_knowledge.json")
REQUIRED_FIELDS = ("id", "title", "keywords", "content")


def _load_payload() -> dict:
    try:
        with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as knowledge_file:
            payload = json.load(knowledge_file)
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        return {}
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        return {}
    for entry in entries:
        if not isinstance(entry, dict):
            return {}
        if not all(isinstance(entry.get(field), str) and entry[field].strip()
                   for field in ("id", "title", "content")):
            return {}
        if not isinstance(entry.get("keywords"), list) or not entry["keywords"]:
            return {}
        if not all(isinstance(keyword, str) and keyword.strip()
                   for keyword in entry["keywords"]):
            return {}
    return payload


def knowledge_version() -> str:
    """Return the bundled knowledge version when its payload is valid."""
    return _load_payload().get("version", "")


def load_game_knowledge() -> list[dict]:
    """Return validated released-player knowledge, or no entries on failure."""
    return _load_payload().get("entries", [])


def find_relevant_entries(user_text: str, limit: int = 5) -> list[dict]:
    """Rank entries by distinct matching keywords, preserving source order ties."""
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        return []
    text = str(user_text or "").casefold()
    ranked = []
    for index, entry in enumerate(load_game_knowledge()):
        score = sum(
            len(keyword)
            for keyword in entry["keywords"]
            if keyword.casefold() in text
        )
        if score:
            ranked.append((-score, index, entry))
    return [item[2] for item in sorted(ranked)[:limit]]
