# Tutorial Window Extraction Implementation Plan

**Goal:** Move the complete first-run tutorial window from `pet.py` into `petpet.ui.tutorial` without changing behavior or visuals.

**Architecture:** The package module owns both immutable tutorial content and `TutorialWindow`. It imports only PyQt5, `buddy_ai`, and shared font helpers. `pet.py` re-exports the exact class for compatibility.

## Task 1: Move the window

- [x] Add a failing boundary test requiring `petpet.ui.tutorial.TutorialWindow` and exact root identity.
- [x] Move the unchanged window class into the package module.
- [x] Replace the root implementation with an explicit import.
- [x] Run onboarding, menu, tutorial-content, and common-UI focused tests.

## Task 2: Verify and document

- [x] Run the full test suite and current-worktree source smoke test.
- [x] Run `git diff --check`, inspect status, and confirm `VERSION` remains `1.5.0`.
- [x] Synchronize the Obsidian implementation record.
