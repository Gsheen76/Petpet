# Settings Data Boundary Refactor Implementation Plan

**Goal:** Move persistent settings defaults and three-level presets out of `pet.py` while preserving the launcher API and every current value.

**Architecture:** `petpet.app.settings` owns defaults and JSON persistence. `petpet.ui.settings` owns UI-facing preset collections. `pet.py` imports and re-exports these exact objects; the settings window itself remains in place for a later slice.

## Task 1: Establish settings modules

- [x] Add failing tests for package imports, root compatibility, migration, and preset identity.
- [x] Move `DEFAULT_SETTINGS`, `SETTINGS_PATH`, `load_settings`, and `save_settings` to `petpet.app.settings`.
- [x] Move health/personality presets to `petpet.ui.settings`.
- [x] Keep root names and `SettingsWindow` class attributes compatible.
- [x] Run focused settings, chat, onboarding, and packaging tests.

## Task 2: Verify and document

- [x] Run the full test suite and current-worktree source smoke test.
- [x] Run `git diff --check`, inspect status, and confirm `VERSION` remains `1.5.0`.
- [x] Synchronize the Obsidian implementation record.
