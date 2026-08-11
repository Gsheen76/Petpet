# Home Pet 2.5D Movement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the reused desktop `PetWindow` inside the home scene with an independently rendered, four-direction placeholder pet that accepts right-click movement and automatically walks to a rug to sleep when energy is low.

**Architecture:** Add a Qt-free `HomePetController` in `home_pet.py` for walkable-area geometry, movement, facing, sleep transitions, cooldown, and position serialization. Keep `HomeSceneWindow` responsible for input conversion, lifecycle, shared progression state, furniture-derived sleep targets, drawing, and camera behavior; reduce `pet.py` to desktop/home visibility handoff.

**Tech Stack:** Python 3, PyQt5, `unittest`/pytest, existing JSON state persistence.

**Execution status (2026-08-10):** Tasks 1–8 implemented in the current worktree without commits. Focused verification: `138 passed`; final full verification: `249 passed in 62.42s`. Source launched from this worktree for manual visual acceptance.

## Global Constraints

- Work only in `D:\Agent_project\Petpet\.worktrees\home-scene-system`.
- Preserve all existing uncommitted changes; do not run `git reset`, `git checkout`, or overwrite unrelated edits.
- Write a failing test before each behavior change.
- The home world remains `1800×768`; the visible canvas remains `900×768`; the decoration sidebar remains `338×768` and outside the canvas.
- The desktop `PetWindow` is hidden for the entire time the home scene is visible and restored only when the home scene exits.
- Decoration mode hides only the in-scene home pet and disables home-pet movement input.
- Phase one uses a placeholder block and implements no A*, navigation mesh, furniture collision, eight-direction animation, or production model assets.
- Persist only `home_scene.pet_position = {"x": float, "y": float}`; do not persist a target, current behavior, animation frame, or cooldown.
- Continue using shared `energy`, `sleeping`, and `sleep_mode` fields and the existing pet-configured auto-sleep/auto-wake thresholds.
- Run focused tests after each task and `python -m pytest -q` before completion.
- Do not commit, push, package, or publish unless the user explicitly requests it. Replace commit steps with review checkpoints.

## File Map

- Create `home_pet.py`: Qt-free point geometry, walkable polygon, depth scale, position migration, and `HomePetController`.
- Create `tests/test_home_pet.py`: deterministic unit tests for all controller and geometry behavior.
- Modify `home_scene.py`: controller ownership, right-click input, shared sleep synchronization, placeholder drawing, depth/layer sorting, position saves, and home lifecycle.
- Modify `pet.py`: stop driving the desktop window in home mode and keep entry/exit visibility handoff correct.
- Modify `tests/test_home_scene.py`: PyQt integration, input, lifecycle, rendering, rug target, and migration tests.
- Modify `tests/test_menu_ui.py`: protect the existing home entry and ensure the hidden desktop window is not used as the home entity.
- Modify `docs/superpowers/specs/2026-08-10-home-pet-2-5d-movement-design.md` only if implementation reveals a necessary clarification; do not silently change approved scope.
- Modify `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园专用宠物与2.5D移动设计.md` at final verification with actual test results and status.

---

### Task 1: Qt-Free Home Geometry and Save Migration

**Files:**
- Create: `home_pet.py`
- Create: `tests/test_home_pet.py`

**Interfaces:**
- Produces: `Point = tuple[float, float]`.
- Produces: `HOME_WALKABLE_POLYGON: tuple[Point, ...] = ((60.0, 420.0), (1740.0, 420.0), (1800.0, 730.0), (0.0, 730.0))`.
- Produces: `HOME_DEFAULT_ENTRY: Point = (450.0, 620.0)` and `HOME_DEFAULT_SLEEP_POINT: Point = (260.0, 610.0)`.
- Produces: `clamp_to_walkable(point: Point, polygon: tuple[Point, ...] = HOME_WALKABLE_POLYGON) -> Point`.
- Produces: `direction_for_delta(dx: float, dy: float, fallback: str = "front_right") -> str` with results `front_left`, `front_right`, `back_left`, or `back_right`.
- Produces: `depth_scale_for_y(y: float, polygon: tuple[Point, ...] = HOME_WALKABLE_POLYGON, minimum: float = 0.72, maximum: float = 1.08) -> float`.
- Produces: `load_home_pet_position(home_scene: Mapping[str, Any] | None, legacy_x: Any = None) -> Point`.
- Produces: `serialize_home_pet_position(position: Point) -> dict[str, float]`.

- [ ] **Step 1: Write failing geometry and migration tests**

Add tests with concrete expectations:

```python
import math
import unittest

import home_pet


class HomePetGeometryTests(unittest.TestCase):
    def test_points_outside_floor_are_projected_to_walkable_polygon(self):
        self.assertEqual(home_pet.clamp_to_walkable((900.0, 100.0)), (900.0, 420.0))
        x, y = home_pet.clamp_to_walkable((-200.0, 900.0))
        self.assertGreaterEqual(x, 0.0)
        self.assertLessEqual(y, 730.0)

    def test_four_directions_follow_screen_space_target_delta(self):
        self.assertEqual(home_pet.direction_for_delta(-10, 10), "front_left")
        self.assertEqual(home_pet.direction_for_delta(10, 10), "front_right")
        self.assertEqual(home_pet.direction_for_delta(-10, -10), "back_left")
        self.assertEqual(home_pet.direction_for_delta(10, -10), "back_right")

    def test_depth_scale_is_clamped_and_increases_toward_foreground(self):
        self.assertEqual(home_pet.depth_scale_for_y(100), 0.72)
        self.assertEqual(home_pet.depth_scale_for_y(900), 1.08)
        self.assertLess(home_pet.depth_scale_for_y(450), home_pet.depth_scale_for_y(700))

    def test_position_load_migrates_legacy_x_and_rejects_non_finite_values(self):
        self.assertEqual(home_pet.load_home_pet_position({}, 900), (900.0, 620.0))
        self.assertEqual(
            home_pet.load_home_pet_position({"pet_position": {"x": 700, "y": 600}}),
            (700.0, 600.0),
        )
        self.assertEqual(
            home_pet.load_home_pet_position(
                {"pet_position": {"x": math.inf, "y": "bad"}}, legacy_x="bad"
            ),
            home_pet.HOME_DEFAULT_ENTRY,
        )
```

- [ ] **Step 2: Run the new tests and verify import failure**

Run:

```text
python -m pytest -q tests/test_home_pet.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'home_pet'`.

- [ ] **Step 3: Implement finite-number normalization and polygon projection**

In `home_pet.py`, use only the standard library (`math`, `typing`). Implement point-in-polygon and nearest-point-on-segment helpers privately. `clamp_to_walkable` returns the input unchanged when it is inside or on the polygon; otherwise it returns the closest point on any edge. Do not import PyQt.

- [ ] **Step 4: Implement direction, depth, and save migration helpers**

Use screen coordinates where positive `dy` means toward the viewer (`front`). For a zero-length delta, return the supplied fallback. Normalize invalid persisted values to `HOME_DEFAULT_ENTRY`, clamp valid persisted and legacy values into `HOME_WALKABLE_POLYGON`, and serialize rounded two-decimal floats.

- [ ] **Step 5: Run Task 1 tests**

Run:

```text
python -m pytest -q tests/test_home_pet.py
```

Expected: all Task 1 tests pass.

- [ ] **Step 6: Review checkpoint without committing**

Run `git status --short -- home_pet.py tests/test_home_pet.py`, then inspect both files with `Get-Content -Encoding UTF8`. Confirm there are no PyQt imports or persistence of transient fields. These files may still be untracked, so do not rely on `git diff` to display them. Do not stage or commit.

---

### Task 2: Deterministic Movement Controller

**Files:**
- Modify: `home_pet.py`
- Modify: `tests/test_home_pet.py`

**Interfaces:**
- Consumes: geometry functions and constants from Task 1.
- Produces: `HomePetController(position: Point, *, walk_speed: float = 180.0, arrival_radius: float = 3.0, sleep_retry_seconds: float = 60.0)`.
- Produces attributes: `position: Point`, `target: Point | None`, `state: str`, `direction: str`, `sleep_retry_until: float`.
- Produces: `command_move(target: Point, now: float) -> bool`; return value is `True` only when an existing sleeping state was interrupted.
- Produces: `request_auto_sleep(target: Point, now: float) -> bool`.
- Produces: `advance(dt: float) -> tuple[str, ...]`; possible events are `arrived` and `sleep_started`.
- Produces: `cancel_target() -> None`.

- [ ] **Step 1: Write failing movement tests**

```python
class HomePetMovementTests(unittest.TestCase):
    def test_manual_move_advances_by_elapsed_time_without_overshooting(self):
        pet = home_pet.HomePetController((500.0, 600.0), walk_speed=100.0)
        pet.command_move((600.0, 600.0), now=10.0)
        self.assertEqual(pet.advance(0.25), ())
        self.assertEqual(pet.position, (525.0, 600.0))
        self.assertEqual(pet.advance(2.0), ("arrived",))
        self.assertEqual(pet.position, (600.0, 600.0))
        self.assertEqual(pet.state, "idle")
        self.assertIsNone(pet.target)

    def test_new_manual_target_replaces_existing_target(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.command_move((700.0, 600.0), now=1.0)
        pet.command_move((400.0, 500.0), now=2.0)
        self.assertEqual(pet.target, (400.0, 500.0))
        self.assertEqual(pet.state, "manual_walk")
        self.assertEqual(pet.direction, "back_left")

    def test_large_frame_delta_is_capped(self):
        pet = home_pet.HomePetController((500.0, 600.0), walk_speed=100.0)
        pet.command_move((700.0, 600.0), now=1.0)
        pet.advance(10.0)
        self.assertLessEqual(pet.position[0], 510.0)
```

- [ ] **Step 2: Run only movement tests and verify failure**

Run `python -m pytest -q tests/test_home_pet.py::HomePetMovementTests`.

Expected: FAIL because `HomePetController` does not exist.

- [ ] **Step 3: Implement the minimal controller movement state**

Clamp constructor and command targets with `clamp_to_walkable`. Limit a single `advance` call to `0.1` seconds. Move by normalized direction vector times `walk_speed * dt`; if the remaining distance is within the step plus `arrival_radius`, snap exactly to the target. Manual arrival transitions to `idle` and emits only `arrived`.

- [ ] **Step 4: Implement target replacement and cancellation**

`command_move` always replaces the current target, selects direction with `direction_for_delta`, and enters `manual_walk`. `cancel_target` clears the target and returns walking states to `idle` without changing position or direction.

- [ ] **Step 5: Run Task 2 tests and the complete controller file**

Run:

```text
python -m pytest -q tests/test_home_pet.py::HomePetMovementTests
python -m pytest -q tests/test_home_pet.py
```

Expected: both commands pass.

- [ ] **Step 6: Review checkpoint without committing**

Inspect `home_pet.py` and `tests/test_home_pet.py` directly because they may still be untracked. Confirm movement is time-based, capped, deterministic, and independent of frame count.

---

### Task 3: Automatic Sleep, Wake, and User-Interruption Priority

**Files:**
- Modify: `home_pet.py`
- Modify: `tests/test_home_pet.py`

**Interfaces:**
- Consumes: `HomePetController` from Task 2.
- Produces: `set_sleeping() -> None` for restoring shared sleep state on home entry.
- Produces: `wake_if_recovered(energy: float, wake_threshold: float) -> bool`.
- Extends: `command_move` to wake and set `sleep_retry_until = now + sleep_retry_seconds` when interrupting `auto_sleep_walk` or `sleeping`.
- Extends: `request_auto_sleep` so it starts only from `idle` at or after `sleep_retry_until`.

- [ ] **Step 1: Write failing sleep-state tests**

```python
class HomePetSleepTests(unittest.TestCase):
    def test_auto_sleep_arrival_emits_sleep_started(self):
        pet = home_pet.HomePetController((500.0, 600.0), walk_speed=100.0)
        self.assertTrue(pet.request_auto_sleep((510.0, 600.0), now=10.0))
        self.assertEqual(pet.advance(1.0), ("arrived", "sleep_started"))
        self.assertEqual(pet.state, "sleeping")

    def test_manual_command_interrupts_sleep_and_starts_retry_cooldown(self):
        pet = home_pet.HomePetController((500.0, 600.0), sleep_retry_seconds=60.0)
        pet.set_sleeping()
        self.assertTrue(pet.command_move((600.0, 600.0), now=20.0))
        self.assertEqual(pet.sleep_retry_until, 80.0)
        self.assertFalse(pet.request_auto_sleep((400.0, 600.0), now=79.0))
        pet.cancel_target()
        self.assertTrue(pet.request_auto_sleep((400.0, 600.0), now=80.0))

    def test_sleeping_pet_wakes_only_at_auto_wake_threshold(self):
        pet = home_pet.HomePetController((500.0, 600.0))
        pet.set_sleeping()
        self.assertFalse(pet.wake_if_recovered(79.9, 80.0))
        self.assertTrue(pet.wake_if_recovered(80.0, 80.0))
        self.assertEqual(pet.state, "idle")
```

- [ ] **Step 2: Run sleep tests and verify failure**

Run `python -m pytest -q tests/test_home_pet.py::HomePetSleepTests`.

Expected: FAIL because sleep methods and transitions are absent.

- [ ] **Step 3: Implement automatic-sleep transitions**

`request_auto_sleep` clamps its target, sets direction, and enters `auto_sleep_walk`. Auto-sleep arrival emits `arrived` followed by `sleep_started`, clears the target, and enters `sleeping`. `set_sleeping` clears any target without changing position.

- [ ] **Step 4: Implement wake and interruption cooldown**

`command_move` returns `True` and starts cooldown when called from `auto_sleep_walk` or `sleeping`; it returns `False` for ordinary manual commands. `wake_if_recovered` transitions only `sleeping` to `idle` when `energy >= wake_threshold`.

- [ ] **Step 5: Run all pure-logic tests**

Run `python -m pytest -q tests/test_home_pet.py`.

Expected: all geometry, movement, and sleep tests pass.

- [ ] **Step 6: Review checkpoint without committing**

Confirm the controller does not read global state or call save functions. Do not stage or commit.

---

### Task 4: Home Scene Ownership, Lifecycle, and Position Persistence

**Files:**
- Modify: `home_scene.py:13-25, 88-270, 344-375`
- Modify: `pet.py:4947-4956, 5023-5028, 5194-5220, 5908-5916`
- Modify: `tests/test_home_scene.py`
- Modify: `tests/test_menu_ui.py`

**Interfaces:**
- Consumes: `HomePetController`, `load_home_pet_position`, `serialize_home_pet_position`, `depth_scale_for_y`, `HOME_DEFAULT_SLEEP_POINT`.
- Produces on `HomeSceneWindow`: `home_pet: HomePetController`.
- Produces: `home_pet_visible() -> bool`.
- Produces: `_save_home_pet_position() -> None`.
- Removes active use of: `dog_world_x`, `set_dog_world_x`, `_place_pet_from_world`, and `PetWindow._on_home_scene_tick`.

- [ ] **Step 1: Write failing lifecycle and migration tests**

Add a reusable fake pet with `hide`, `show`, `raise_`, `current_screen_rect`, `auto_sleep_energy_threshold = 30.0`, and `auto_wake_energy_threshold = 80.0`. Add tests equivalent to:

```python
def test_home_scene_owns_internal_pet_and_hides_desktop_pet_for_full_session(self):
    state = progression.ensure_progression({"home_scene_dog_world_x": 900})
    pet = make_fake_pet(state)
    scene = home_scene.HomeSceneWindow(pet, Mock())
    self.addCleanup(scene.close)

    scene.show_scene()
    pet.hide.assert_called_once_with()
    self.assertEqual(scene.home_pet.position, (900.0, home_pet.HOME_DEFAULT_ENTRY[1]))
    self.assertTrue(scene.home_pet_visible())

    scene.toggle_decoration_mode()
    self.assertFalse(scene.home_pet_visible())
    scene.toggle_decoration_mode()
    self.assertTrue(scene.home_pet_visible())
    pet.show.assert_not_called()

    scene.hide_scene()
    pet.show.assert_called_once_with()


def test_home_scene_persists_only_internal_pet_position(self):
    state = progression.ensure_progression({})
    save = Mock()
    scene = home_scene.HomeSceneWindow(make_fake_pet(state), save)
    scene.home_pet.position = (720.125, 610.555)
    scene._save_home_pet_position()
    self.assertEqual(state["home_scene"]["pet_position"], {"x": 720.12, "y": 610.55})
    self.assertNotIn("target", state["home_scene"])
```

Update the old `test_decoration_mode_temporarily_hides_and_restores_the_pet`: it must now assert internal visibility changes while `pet.show` is not called until `hide_scene`.

- [ ] **Step 2: Run focused lifecycle tests and verify failure**

Run:

```text
python -m pytest -q tests/test_home_scene.py -k "internal_pet or persists_only or decoration_mode_temporarily"
```

Expected: FAIL because `home_pet` and `_save_home_pet_position` do not exist and the old scene restores the desktop window after decoration.

- [ ] **Step 3: Construct the controller from saved state**

In `HomeSceneWindow.__init__`, call `load_home_pet_position(self.state.get("home_scene"), self.state.get("home_scene_dog_world_x"))`. Construct `HomePetController` with a home-specific world speed of `180.0`. If shared state is already sleeping, call `set_sleeping()`.

- [ ] **Step 4: Replace desktop-pet placement with internal lifecycle**

Remove calls that move the desktop widget into the scene. `show_scene` hides overlays, hides the desktop pet, shows the scene, and initializes the camera from `home_pet.position[0]`. `toggle_decoration_mode` changes only `home_pet_visible`; it must not show the desktop pet when editing ends. `hide_scene` cancels the internal target, saves position, hides the scene, and restores/raises the desktop pet.

- [ ] **Step 5: Stop `PetWindow` from driving or dragging in the home world**

Remove the home-scene branch in `PetWindow.mouseMoveEvent`, remove the early `_on_home_scene_tick` delegation in `on_tick`, and delete `_on_home_scene_tick` after no references remain. Since the desktop widget is hidden, its normal tick may continue updating shared progression but must not alter `HomePetController`.

- [ ] **Step 6: Run lifecycle, menu, and existing home tests**

Run:

```text
python -m pytest -q tests/test_home_scene.py tests/test_menu_ui.py
```

Expected: all tests pass after adapting only assertions invalidated by the approved architecture.

- [ ] **Step 7: Review checkpoint without committing**

Run `Select-String -Path pet.py,home_scene.py -Pattern '_on_home_scene_tick|set_dog_world_x|_place_pet_from_world'`. Expected: no active references. Inspect the diff and confirm `show_scene`/`hide_scene` are the only desktop visibility handoff points.

---

### Task 5: Right-Click World Targets and Decoration Input Isolation

**Files:**
- Modify: `home_scene.py:595-770`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: `HomePetController.command_move` and `clamp_to_walkable`.
- Produces: `canvas_to_world(point: QPoint) -> Point`.
- Produces: `command_home_pet(point: QPoint, now: float | None = None) -> bool`.
- Produces: `_scene_control_at(point: QPoint) -> bool` to exclude exit, decoration, pan, sidebar, and decoration-card controls.

- [ ] **Step 1: Write failing coordinate and input tests**

```python
def test_right_click_converts_canvas_point_with_camera_offset(self):
    scene = make_scene()
    scene._camera_x = 500
    canvas = scene.scene_canvas_rect()
    point = QPoint(canvas.left() + 200, 600)
    self.assertTrue(scene.command_home_pet(point, now=10.0))
    self.assertEqual(scene.home_pet.target, (700.0, 600.0))


def test_right_click_is_ignored_while_decorating_or_over_controls(self):
    scene = make_scene()
    original = scene.home_pet.target
    self.assertFalse(scene.command_home_pet(scene.exit_button_rect().center(), now=1.0))
    scene.toggle_decoration_mode()
    self.assertFalse(scene.command_home_pet(scene.scene_canvas_rect().center(), now=2.0))
    self.assertEqual(scene.home_pet.target, original)
```

Use a minimal `QMouseEvent` or a small event fake to assert `mousePressEvent` accepts `Qt.RightButton` and dispatches exactly once.

- [ ] **Step 2: Run the new right-click tests and verify failure**

Run `python -m pytest -q tests/test_home_scene.py -k "right_click"`.

Expected: FAIL because only left-button furniture input exists.

- [ ] **Step 3: Implement local-to-world conversion and control exclusion**

Subtract `scene_canvas_rect().left()` from local x, then add `_camera_x`; keep local y. Return `False` when the scene is hidden, decorating, outside the canvas, or over any scene control. Let `HomePetController` perform final polygon clamping.

- [ ] **Step 4: Dispatch right-button press without disturbing left-button furniture gestures**

Handle `Qt.RightButton` first in `mousePressEvent`, call `command_home_pet(event.pos())`, accept only when it returns `True`, and return. Preserve all current left-click button, panel, and furniture behavior unchanged.

- [ ] **Step 5: Synchronize shared sleep state on manual interruption**

If `command_move` returns `True`, set `state["sleeping"] = False`, set `state["sleep_mode"] = None`, and call `save_state`. Do not change energy. This is the sole wake action for a right-clicked sleeping home pet.

- [ ] **Step 6: Run focused input regression tests**

Run:

```text
python -m pytest -q tests/test_home_scene.py -k "right_click or decoration or furniture"
```

Expected: all selected tests pass.

- [ ] **Step 7: Review checkpoint without committing**

Inspect `home_scene.py` and the new tests directly; both may still be untracked in this worktree. Verify no right-click path invokes the desktop bubble menu while the home scene receives the event.

---

### Task 6: Scene Tick, Rug Sleep Target, and Shared Sleep Synchronization

**Files:**
- Modify: `home_scene.py:116-140, 382-400, 657-669`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: controller methods from Tasks 2–3 and `progression.home_decoration_position`/`home_decoration_transform`.
- Produces: `home_sleep_target() -> Point`.
- Produces: `_advance_home_pet(now: float | None = None) -> tuple[str, ...]`.
- Produces: `_home_pet_energy() -> float` with safe finite normalization.

- [ ] **Step 1: Write failing sleep-target tests**

```python
def test_home_sleep_target_prefers_placed_rug_center_and_tracks_moves(self):
    state = progression.ensure_progression({"pet_coins": 500})
    progression.purchase_home_decoration(state, "home_rug")
    scene = make_scene(state)
    self.assertEqual(scene.home_sleep_target(), (840.0, 565.0))
    progression.set_home_decoration_position(state, "home_rug", 700, 430)
    self.assertEqual(scene.home_sleep_target(), (920.0, 565.0))


def test_home_sleep_target_falls_back_when_rug_is_stored(self):
    state = progression.ensure_progression({"pet_coins": 500})
    progression.purchase_home_decoration(state, "home_rug")
    progression.store_home_decoration(state, "home_rug")
    self.assertEqual(make_scene(state).home_sleep_target(), home_pet.HOME_DEFAULT_SLEEP_POINT)
```

Compute the unrotated furniture center from top-left plus half authored pixmap size. Rotation and scale do not change the center. Final target is always passed through `clamp_to_walkable`.

- [ ] **Step 2: Write failing tick synchronization tests**

Freeze `scene._last_pet_tick` or inject explicit `now` values. Cover: low energy starts `auto_sleep_walk`; arrival writes `sleeping=True` and `sleep_mode="auto"`; energy `80.0` wakes and clears `sleep_mode`; no automatic request is made during decoration or manual walking.

- [ ] **Step 3: Run sleep integration tests and verify failure**

Run `python -m pytest -q tests/test_home_scene.py -k "sleep_target or home_pet_sleep"`.

Expected: FAIL because sleep-target and home-pet tick methods do not exist.

- [ ] **Step 4: Implement rug/default target selection**

Return the rug center only when `home_rug` is owned and not listed in `home_stored_decorations`. Read its current saved/default position through progression. Any missing definition, invalid position, or null pixmap falls back to `HOME_DEFAULT_SLEEP_POINT`.

- [ ] **Step 5: Drive controller with monotonic elapsed time**

In `_sync_scene`, call `_advance_home_pet(time.monotonic())` before `update()`. Store `_last_pet_tick`; clamp negative elapsed time to zero and let the controller cap large deltas. Do not advance while decorating.

- [ ] **Step 6: Synchronize shared sleep fields and save at transitions**

When idle energy is below `pet.auto_sleep_energy_threshold`, call `request_auto_sleep`. On `sleep_started`, set shared `sleeping=True`, `sleep_mode="auto"`, call `progression.record_sleep(state, "auto")`, and save. When `wake_if_recovered` succeeds at `pet.auto_wake_energy_threshold`, clear shared sleep fields and save. Save position on `arrived`, sleep transition, wake transition, and scene exit—not on every frame.

- [ ] **Step 7: Re-evaluate targets after furniture operations**

No cached rug target is allowed. `store_furniture`, `place_furniture`, and `move_furniture` already update state; the next auto-sleep decision must call `home_sleep_target()` fresh.

- [ ] **Step 8: Run sleep and progression regression tests**

Run:

```text
python -m pytest -q tests/test_home_scene.py -k "sleep or rug or furniture"
python -m pytest -q tests/test_progression.py tests/test_sleep_interaction.py
```

Expected: all selected tests pass.

- [ ] **Step 9: Review checkpoint without committing**

Confirm saves occur only at explicit transitions/arrival/exit, and controller cooldown remains runtime-only.

---

### Task 7: Placeholder Rendering, Four Directions, and 2.5D Layering

**Files:**
- Modify: `home_scene.py:211-243, 421-477`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: `depth_scale_for_y`, `home_pet.position`, `home_pet.direction`, and `home_pet.state`.
- Produces: `home_pet_draw_rect() -> QRectF` anchored at foot-center.
- Produces: `_draw_home_pet(painter: QPainter) -> None`.
- Produces: `_furniture_depth_key(decoration_id: str) -> tuple[int, float]`.
- Produces: `_scene_render_entries() -> list[tuple[tuple[int, float], str, str]]` where entries identify floor furniture, depth furniture, and pet.

- [ ] **Step 1: Write failing scale and anchor tests**

Create two scenes with pet y values `450` and `700`. Assert the foreground `home_pet_draw_rect()` is larger, both rectangles have `bottom() == pet_y`, and both horizontal centers equal `scene_canvas_rect().left() + world_x - camera_x`.

- [ ] **Step 2: Write failing layer-order tests**

Use owned rug, sofa, plant, and wall art. Assert wall art/background entries precede the rug; rug precedes the pet; sofa/plant compare their transformed foot y with the pet foot y. Verify changing the pet y moves it from behind to in front without changing furniture state.

- [ ] **Step 3: Run rendering tests and verify failure**

Run `python -m pytest -q tests/test_home_scene.py -k "home_pet_draw or layer_order or depth_scale"`.

Expected: FAIL because draw rectangles and render entries do not exist.

- [ ] **Step 4: Implement the foot-anchored placeholder rectangle**

Use a base block size of `96×112` world pixels multiplied by `depth_scale_for_y`. Convert world x through the camera and canvas offset. The block bottom is exactly the foot y. Draw a translucent oval shadow centered at the foot point.

- [ ] **Step 5: Draw direction and behavior cues**

Use four stable warm colors or a contrasting arrow for `front_left`, `front_right`, `back_left`, and `back_right`. During walking, offset the block vertically by a small sine bob based on a runtime phase; during sleep, reduce block height and draw two small `Z` glyphs. Keep all placeholder-specific drawing inside `_draw_home_pet`.

- [ ] **Step 6: Implement render-entry ordering**

Classify `home_wall_art` as background, `home_rug` as floor, and `home_sofa`/`home_plant` as depth items. For depth furniture, compute transformed visual bounds and use the bottom edge as the foot-depth key. Insert the pet with its foot y. Preserve selection overlay drawing after the normal scene entries so editing handles remain visible.

- [ ] **Step 7: Keep pet hidden during decoration**

Do not include the pet entry in `_scene_render_entries` when `is_decorating()` is true. Background, furniture, controls, and sidebar must render unchanged.

- [ ] **Step 8: Run home rendering and geometry tests**

Run:

```text
python -m pytest -q tests/test_home_scene.py tests/test_scene_system.py
```

Expected: all tests pass, including the existing warm selection and furniture transform tests.

- [ ] **Step 9: Review checkpoint without committing**

Render a `QPixmap` in the offscreen test path and verify nontransparent pixels exist at the placeholder rect and shadow. Inspect the diff for accidental production sprite dependencies.

---

### Task 8: Camera Follow, Regression Cleanup, and Final Verification

**Files:**
- Modify: `home_scene.py`
- Modify: `tests/test_home_scene.py`
- Modify: `tests/test_menu_ui.py`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园专用宠物与2.5D移动设计.md`

**Interfaces:**
- Consumes: complete home-pet controller and scene integration.
- Finalizes: automatic camera tracking from `home_pet.position[0]` outside decoration mode.
- Finalizes: manual camera pan only during decoration, with return to home-pet tracking afterward.

- [ ] **Step 1: Write failing camera-follow regression tests**

Replace old tests that derive camera position from desktop pet width. Assert `camera_x_for_dog(home_pet.position[0], 0)` or a dedicated point-centered helper follows the internal foot x, clamps to world edges, remains manually pinned during decoration, and returns to internal-pet tracking when decoration closes.

- [ ] **Step 2: Run camera tests and verify failure**

Run `python -m pytest -q tests/test_home_scene.py -k "viewport or camera"`.

Expected: FAIL while camera tracking still depends on legacy `dog_world_x` or desktop width.

- [ ] **Step 3: Switch camera follow to the internal pet**

Outside decoration, center the 900-pixel viewport on `home_pet.position[0]` and clamp to `[0, 900]`. During decoration, retain the existing manual camera and pan timers. On leaving decoration, clear the pin and immediately recenter on the internal pet.

- [ ] **Step 4: Remove obsolete one-dimensional home movement code**

Remove unused `dog_scene_y`, `HOME_DOG_BASELINE_INSET`, `dog_world_x`, `set_dog_world_x`, `_place_pet_from_world`, and `PetWindow._on_home_scene_tick` only after `Select-String` confirms no active consumers. Keep `home_scene_dog_world_x` read support solely inside migration.

- [ ] **Step 5: Run all focused tests**

Run:

```text
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q tests/test_home_pet.py tests/test_home_scene.py tests/test_menu_ui.py tests/test_scene_system.py tests/test_progression.py tests/test_sleep_interaction.py
```

Expected: all selected tests pass.

- [ ] **Step 6: Run the complete regression suite**

Run:

```text
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q
```

Expected: every test passes; the count must be greater than the current `217 passed` baseline because `tests/test_home_pet.py` and integration cases were added.

- [ ] **Step 7: Inspect the final repository state**

Run:

```text
git status --short
git diff --stat
git diff --check
```

Expected: only intentional working-tree changes, no whitespace errors in tracked diffs, no staged files, and no commit. Because several home-scene files were already untracked before this feature, inspect those files directly rather than assuming `git diff --stat` includes them.

- [ ] **Step 8: Update the Obsidian implementation record**

In `家园专用宠物与2.5D移动设计.md`, change `status` from `设计已确认` to `方块原型待手工验收`, add the exact focused/full test results, and summarize any implementation detail that differs from the approved design. Do not mark it complete before manual visual acceptance.

- [ ] **Step 9: Launch only the current worktree source for manual acceptance**

After automated verification, launch `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py`. Verify: desktop pet hides on home entry; a directional block appears; right-click moves within the floor; foreground scale is larger; furniture occlusion changes with y; low energy selects rug/default sleep; manual right-click interrupts sleep behavior; decoration hides the block; exit restores the desktop pet.

- [ ] **Step 10: Final review checkpoint without committing**

Report the exact test commands/results, manual acceptance status, changed files, and known phase-two exclusions. Do not commit, push, package, or publish.
