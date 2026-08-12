# Petpet Chat Avatar and Window Shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the chat window’s outer corners truly transparent, add desktop-pet/player avatars to messages, and add local player-avatar editing.

**Architecture:** Keep `ChatWindow` as the controller, but render its visible surface inside `QFrame#chatCard`. Add avatar image preparation and path helpers to `buddy_ai.py`, so persistence is independent of UI and future desktop-pet variants can change their resolver without changing message rows.

**Tech Stack:** Python 3, PyQt5, QImage/QPixmap/QPainter, unittest/pytest.

## Global Constraints

- Preserve all existing uncommitted changes; no reset, checkout, commit, push, or release.
- Use `assets/poses/idle.png` for the current desktop-pet avatar, never a home-scene asset.
- Store the player avatar only in the user data directory.
- Write failing tests before production changes.
- Sync results to Obsidian and Petpet 总档案.

---

### Task 1: Real rounded outer window and compact labels

**Files:**
- Modify: `tests/test_chat_tools.py`
- Modify: `pet.py`

- [ ] Add failing tests for translucent top-level background, a `chatCard` child, transparent corner pixels, and exact `上传` / `DEL` labels.
- [ ] Run the new tests and confirm they fail on the rectangular top-level window and old labels.
- [ ] Move the visible layout into `chatCard`, enable translucent background, and update the two labels.
- [ ] Run `python -m pytest tests/test_chat_tools.py -q`.

### Task 2: Avatar preparation and persistence

**Files:**
- Modify: `tests/test_ai_config.py`
- Modify: `buddy_ai.py`

- [ ] Add failing tests for avatar location, centered square crop, PNG output, invalid-image rejection, and reset.
- [ ] Run the avatar tests and confirm missing helper failures.
- [ ] Implement `get_player_avatar_path()`, `prepare_player_avatar(path)`, and `clear_player_avatar()` using QImage-independent file/Pillow-free Qt-compatible image logic or standard-library path management as appropriate.
- [ ] Run `python -m pytest tests/test_ai_config.py -q`.

### Task 3: Message avatars and title-bar editor

**Files:**
- Modify: `tests/test_chat_tools.py`
- Modify: `pet.py`

- [ ] Add failing tests for assistant-left/player-right avatar order, desktop idle source, default player avatar, custom avatar refresh, and the title-bar avatar action.
- [ ] Run focused tests and confirm failure.
- [ ] Add circular avatar rendering, player default drawing, file selection/reset menu, and refresh existing history after avatar changes.
- [ ] Run `python -m pytest tests/test_chat_tools.py tests/test_ai_config.py -q`.

### Task 4: Full verification and records

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\聊天系统\聊天头像与真实圆角窗口设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

- [ ] Run `python -m pytest -q`.
- [ ] Render free/personal screenshots and inspect corner transparency, avatars, and narrow-width layout.
- [ ] Restart the current worktree `pet.py`.
- [ ] Record exact verification results in Obsidian and inspect `git status --short`.
