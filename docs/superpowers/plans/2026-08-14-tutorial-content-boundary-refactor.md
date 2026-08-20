# Tutorial Content Boundary Refactor Implementation Plan

**Goal:** Move the six tutorial page definitions out of the launcher into `petpet.ui.tutorial` without changing the tutorial window or its content.

**Architecture:** The package module owns immutable tutorial content. `TutorialWindow.PAGES` references the exact package object so existing callers remain compatible while later window extraction has a stable dependency.

## Task 1: Extract tutorial content

- [x] Add a failing boundary test for `petpet.ui.tutorial.TUTORIAL_PAGES`.
- [x] Move the unchanged six-page content into the package module.
- [x] Import it explicitly in `pet.py` and retain `TutorialWindow.PAGES` compatibility.
- [x] Run tutorial and UI focused tests.

## Task 2: Verify and document

- [x] Run the full test suite and current-worktree source smoke test.
- [x] Run `git diff --check` and confirm version remains `1.5.0`.
- [x] Synchronize the Obsidian implementation record.
