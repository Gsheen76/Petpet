"""Compatibility facade for :mod:`petpet.chat.knowledge`."""

from petpet.chat.knowledge import (
    KNOWLEDGE_PATH,
    REQUIRED_FIELDS,
    find_relevant_entries,
    knowledge_version,
    load_game_knowledge,
)

__all__ = [
    "KNOWLEDGE_PATH",
    "REQUIRED_FIELDS",
    "find_relevant_entries",
    "knowledge_version",
    "load_game_knowledge",
]
