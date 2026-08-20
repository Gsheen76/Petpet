# Common UI Typography Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `petpet.ui.common` with the shared DPI-independent typography API used by chat, settings, tutorial, and other full-window UI.

**Architecture:** Move only the pure font scaling constants and QFont factories in this slice. Root `pet.py` imports and re-exports those exact objects, keeping all existing callers and tests compatible while later UI modules gain a stable dependency.

**Tech Stack:** Python 3.11, PyQt5 `QFont`, unittest/pytest.

## Global Constraints

- Preserve every numeric font scale and rendered pixel size.
- Do not move window classes, display-scaling initialization, or styles in the same change.
- Root imports remain compatible.
- Root `pet.py` remains the launcher.
- No dependency, version, release, commit, or remote change.
- Write the failing boundary test first and run focused/full verification.

---

### Task 1: Extract typography helpers

**Files:**
- Create: `petpet/ui/__init__.py`
- Create: `petpet/ui/common.py`
- Create: `tests/test_common_ui.py`
- Modify: `pet.py`
- Modify: `tests/test_windows_packaging.py`

**Interfaces:**
- Produces and re-exports `FIXED_FONT_SCALE`, `SETTINGS_FONT_SCALE`, `font_px`, `independent_font_px`, `settings_font_px`, `tutorial_font_px`, `pixel_font`, and `independent_pixel_font`.

- [x] Add a failing test asserting root `pet` exposes the exact package objects and authored sizes remain unchanged.
- [x] Run `python -m pytest tests/test_common_ui.py -q` and verify missing-package failure.
- [x] Move the unchanged implementation to `petpet/ui/common.py` and explicitly import it in `pet.py`.
- [x] Update the packaging source-structure test to require the new import and package implementation.
- [x] Run `python -m pytest tests/test_common_ui.py tests/test_windows_packaging.py tests/test_settings_ui.py tests/test_chat_tools.py -q`.

### Task 2: Verify and document

- [x] Run `python -m pytest -q`.
- [x] Run current-worktree source startup smoke.
- [x] Run `git diff --check`, inspect status, and confirm `VERSION` remains `1.5.0`.
- [x] Synchronize the Obsidian implementation record.
