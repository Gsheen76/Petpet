# Home Status Card and Shop Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a free live status-card wall decoration, remove the home status button, and compact the upgrade shop into two columns.

**Architecture:** Extend the existing home furniture catalog and persistence path. Render the state card from current progression data through one shared Qt helper used by both the scene and shop, then build upgrade cards in a two-column `QGridLayout`.

**Tech Stack:** Python, PyQt5, unittest/pytest.

## Global Constraints

- Preserve all existing uncommitted changes.
- Write failing tests before production edits.
- Do not commit, push, or release unless explicitly requested.

---

### Task 1: Catalog and header behavior

**Files:** `tests/test_progression.py`, `tests/test_home_scene.py`, `progression.py`, `scene_system.py`, `home_scene.py`

- [x] Add failing tests for zero-cost claiming, wall default placement, and the four-button header.
- [x] Run focused tests and confirm the missing status card/header behavior fails.
- [x] Add the catalog entry, geometry, header removal, and wall-depth ordering.
- [x] Re-run focused tests.

### Task 2: Live card rendering and compact shop

**Files:** `tests/test_home_scene.py`, `tests/test_progression_ui.py`, `home_scene.py`, `progression_ui.py`

- [x] Add failing tests proving state changes alter the rendered card and upgrades form a two-column grid.
- [x] Run focused tests and confirm both fail for the intended reason.
- [x] Add shared state-card rendering, free-claim copy, and concise two-column upgrade cards.
- [x] Re-run focused tests.

### Task 3: Documentation and regression verification

**Files:** Obsidian project notes and affected test suites.

- [x] Synchronize the behavior record and Petpet total archive.
- [x] Run focused tests.
- [x] Run `pytest -q` and verify the final git diff.
