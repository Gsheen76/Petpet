# Common Settings Controls Extraction Plan

**Goal:** Move the reusable warm settings controls out of `pet.py` without changing rendering or behavior.

**Architecture:** `petpet.ui.controls` owns `ToggleSwitch`, `StepperControl`, and `ThreeLevelSlider`. `pet.py` imports and re-exports the exact classes, so `SettingsWindow` and existing tests remain compatible.

## Task 1: Extract controls

- [x] Add a failing boundary and behavior test for the package control classes.
- [x] Move the three unchanged PyQt control classes into `petpet.ui.controls`.
- [x] Replace root implementations with explicit imports.
- [x] Run settings, common UI, menu, and packaging focused tests.

## Task 2: Verify and document

- [x] Run the full test suite and current-worktree source smoke test.
- [x] Run `git diff --check`, inspect status, and confirm `VERSION` remains `1.5.0`.
- [x] Synchronize the Obsidian implementation record.
