# Settings Window Extraction Plan

**Goal:** Move the complete settings window into `petpet.ui.settings` now that its data, typography, and controls have stable package boundaries.

**Architecture:** `petpet.ui.settings` owns presets and `SettingsWindow`; it depends on `petpet.app.settings`, `petpet.ui.common`, and `petpet.ui.controls`. `pet.py` imports and re-exports the exact class.

## Task 1: Move SettingsWindow

- [x] Add a failing ownership test for `petpet.ui.settings.SettingsWindow`.
- [x] Move the unchanged window class and required PyQt imports into the package module.
- [x] Update persistence patch targets to the module that now owns the call.
- [x] Remove the root implementation and retain compatibility import.
- [x] Run settings, menu, chat, onboarding, and packaging focused tests.

## Task 2: Verify and document

- [x] Run full tests and current-worktree source smoke.
- [x] Run `git diff --check`, inspect status, and confirm `VERSION` remains `1.5.0`.
- [x] Synchronize Obsidian and continue to the chat boundary.
