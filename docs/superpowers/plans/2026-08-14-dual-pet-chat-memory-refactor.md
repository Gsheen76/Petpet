# Dual-Pet Chat Memory Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give desktop and home pets independent persisted conversation memory while preserving the current chat UI and model request behavior.

**Architecture:** `petpet.chat.memory` owns JSON memory loading, first-use seeding, and saving. `buddy_ai` retains a compatibility API with an optional profile argument defaulting to `desktop`; `ChatWindow` selects its profile when opened and passes it to every persistence operation.

**Tech Stack:** Python 3.11, standard-library JSON/filesystem APIs, PyQt5, unittest/pytest.

## Global Constraints

- Desktop memory remains `memory.json` for backward compatibility.
- Home memory uses `memory-home.json` and is seeded from desktop memory only when it does not yet exist.
- Later desktop changes must never overwrite an existing home memory file.
- Existing callers that omit a profile continue using desktop memory.
- Model endpoints, prompts, quota, streaming, and networking are not changed in this slice.
- No version change, dependency, commit, push, tag, or release.
- Use failing tests first and synchronize Obsidian after verification.

---

### Task 1: Extract profile-aware memory persistence

**Files:**
- Create: `petpet/chat/__init__.py`
- Create: `petpet/chat/memory.py`
- Create: `tests/test_chat_memory.py`

**Interfaces:**
- Produces: `normalize_profile(profile: object) -> str`.
- Produces: `load_memory(path: str, default_factory: Callable[[], dict], seed_path: str | None = None) -> dict`.
- Produces: `save_memory(path: str, memory: dict) -> None`.

- [x] Write failing tests proving first home load copies desktop history and later home loads remain independent.
- [x] Run `python -m pytest tests/test_chat_memory.py -q` and verify import failure.
- [x] Implement minimal JSON load/save and one-time seed behavior.
- [x] Run `python -m pytest tests/test_chat_memory.py -q` and verify all tests pass.

### Task 2: Add the compatibility profile API to `buddy_ai`

**Files:**
- Modify: `buddy_ai.py`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Preserves: `load_memory()`, `save_memory(memory)`, `set_pet_name(name)`, and `append_history(...)` as desktop defaults.
- Adds: optional `profile="desktop"` to memory-writing functions.
- Adds: `HOME_MEMORY_PATH` and `memory_path(profile)`.

- [x] Write a failing test that patches both paths, appends different histories, and verifies independent files.
- [x] Wire `buddy_ai` to `petpet.chat.memory` and propagate the profile through append, summary, rename, and nudge saves.
- [x] Run `python -m pytest tests/test_chat_memory.py tests/test_ai_config.py tests/test_chat_tools.py -q`.

### Task 3: Select the active pet profile in the chat window

**Files:**
- Modify: `pet.py`
- Create: `tests/test_chat_profile.py`

**Interfaces:**
- `ChatWindow.__init__(pet_window, memory_profile="desktop")`.
- `ChatWindow.set_memory_profile(profile: str) -> None` reloads the selected memory and refreshes visible pet naming.
- `PetWindow.chat()` selects `home` only while the home scene window is visible; otherwise it selects `desktop`.

- [x] Write failing tests for active profile selection and profile-specific display names.
- [x] Pass the profile to load, append, clear, and reload operations.
- [x] Run chat/profile focused tests.

### Task 4: Verify and record

- [x] Run `python -m pytest -q`.
- [x] Run current-worktree `pet.py` source startup smoke.
- [x] Run `git diff --check` and inspect status/version.
- [x] Update the Obsidian implementation record with exact behavior and test evidence.
