# 家场景视野与装修控制 Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with tests first.

**Goal:** Add controllable horizontal panning and a persistent Chinese furniture decoration mode to the existing home scene.

**Architecture:** Keep geometry and persistence normalization in `scene_system.py` and `progression.py`; keep Qt painting, pointer repeat timers, and the decoration overlay in `home_scene.py`. Existing shop IDs remain unchanged, and the scene owns only home-specific placement state.

**Tech Stack:** Python 3, PyQt5, Pillow for one-time asset preparation, unittest/pytest.

## Global Constraints

- Home viewport remains `900 x 768`; world remains `1800 x 768`.
- The scene stays fixed at the lower-right and keeps rounded corners.
- All visible new controls use Chinese labels: `左移`, `右移`, `装饰`, `退出`, `全部`, `地毯`, `沙发`, `绿植`, `墙饰`.
- Do not mix home furniture state with wearable decoration state.
- Every behavior change follows a failing test, then minimal implementation, then full regression.

### Task 1: Persist view, editing, storage, and transforms

**Files:** `scene_system.py`, `progression.py`, `tests/test_scene_system.py`, `tests/test_progression.py`

- Add clamped viewport panning, transform normalization, placement/storage migration, and purchase defaults.
- Tests cover old-save defaults, camera bounds, scale/rotation limits, and storage toggles.

### Task 2: Import replacement furniture images

**Files:** `tools/import_home_furniture.py`, `assets/scenes/home/rug.png`, `assets/scenes/home/plant.png`, `tests/test_home_scene.py`

- Remove the rug's dark edge-connected background and the plant's green screen, crop the subject, and render to the authored dimensions.
- Verify alpha, dimensions, and asset paths.

### Task 3: Add scene controls and camera repeat

**Files:** `home_scene.py`, `tests/test_home_scene.py`

- Draw Chinese edge buttons and adjacent lower-right controls.
- Add press/release repeat timers, viewport persistence, and safe button hit testing.
- Preserve dog tracking when no manual pan is active.

### Task 4: Add decoration mode and transform editor

**Files:** `home_scene.py`, `tests/test_home_scene.py`, `tests/test_scene_system.py`

- Add the category/inventory overlay, place/store actions, selected furniture, drag gating, and scale/rotation buttons.
- Render transformed furniture with painter save/restore and inverse hit testing.
- Exit decoration mode disables all furniture editing.

### Task 5: Package, document, and verify

**Files:** `packaging/Petpet-windows.spec`, `packaging/Petpet-mac.spec`, Obsidian home-scene record

- Keep the scene assets in both package specs and document the new workflow.
- Run focused tests, then `pytest -q`, then start the source instance for manual acceptance.
