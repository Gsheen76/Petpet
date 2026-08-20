# Petpet Warm Chat Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the remaining system-looking chat controls with stable, warm, rounded Petpet components.

**Architecture:** Add small reusable `PetpetConfirmDialog` and `PetpetPopupMenu` widgets beside `ChatWindow`. Keep business behavior in `ChatWindow`, while popup/dialog classes only expose choices; convert the API editor to a frameless translucent card and render a static model card when only one model exists.

**Tech Stack:** Python 3, PyQt5 widgets/QSS, unittest/pytest.

## Global Constraints

- Preserve all uncommitted changes; no reset, checkout, commit, push, or release.
- Selection uses pale pink and never Windows blue.
- Segment geometry and font weight remain identical between selected states.
- File selection dialogs remain native.
- Test first, focused tests, then full `pytest -q` and live source restart.

---

### Task 1: Stable pastel segmented selector

- Add failing tests comparing button geometry/font weight before and after mode changes.
- Confirm RED on the current content-dependent sizing.
- Set fixed button and container geometry; use pale-pink checked QSS without font-weight changes.
- Run chat focused tests.

### Task 2: Reusable warm confirmation and popup menu

- Add failing tests for `PetpetConfirmDialog`, `PetpetPopupMenu`, and absence of `QMessageBox`/`QMenu` in clear/avatar paths.
- Implement frameless translucent rounded components.
- Connect clear-memory and avatar actions to the new components.
- Run chat focused tests.

### Task 3: Frameless API card and single-model display

- Add failing tests for frameless/translucent API dialog, rounded card, and no `QComboBox` for one model.
- Refactor API editor to an internal builder that creates the Petpet card and exposes testable widgets.
- Keep model data compatible with future multiple models; use static card for the current single model.
- Replace success popups with inline/close behavior and use warm confirmation for Key removal.
- Run chat and config focused tests.

### Task 4: Visual and full verification

- Run full `python -m pytest -q`.
- Render chat, avatar popup, clear confirmation, and API card screenshots.
- Inspect pastel variety, stable segment geometry, no blue selection, and rounded edges.
- Update Obsidian records, remove temporary renders, restart current worktree `pet.py`, inspect Git status.
