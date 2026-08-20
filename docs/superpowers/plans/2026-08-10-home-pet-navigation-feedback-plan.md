# Home Pet Navigation Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground and size the home pet consistently in all four directions, constrain it to the visible floor, and show warm destination/path feedback for manual right-click movement.

**Architecture:** Keep movement and clamping in Qt-free `home_pet.py`. Add premeasured per-frame contact metadata and runtime-only navigation state to `home_scene.py`; the existing 33 ms timer drives animation, path shortening, pulse, and fade. Render navigation above the rug and below the pet and solid furniture.

**Tech Stack:** Python 3, PyQt5 (`QPainter`, `QPixmap`, `QRectF`, `QPainterPath`), unittest/pytest, existing `HomePetController` and scene render ordering.

## Global Constraints

- Work only in `D:\Agent_project\Petpet\.worktrees\home-scene-system` on `codex/home-scene-system`.
- Preserve all uncommitted changes; never run `git reset` or `git checkout`.
- Do not create another worktree; the requested isolated worktree already exists.
- Write and observe a failing test before each production change.
- Keep both original PNG sprite sheets unchanged.
- Back visual scale is `1.06`; front visual scale is `1.0`.
- Move the walkable top edge from `y=420` to `y=460`.
- Manual feedback fades in `350ms`; auto-sleep walking never creates it.
- The path is a straight visual guide only; do not add collision avoidance or pathfinding.
- Do not stage, commit, push, or publish unless explicitly requested. Each task ends with an unstaged review checkpoint.
- Finish with focused tests, full `pytest -q`, `py_compile`, `git diff --check`, and this worktree's `pet.py` manual review.

## File Map

- Modify `home_pet.py`: lower the walkable polygon far edge.
- Modify `home_scene.py`: frame-contact metadata, normalized render specs, frame-aware shadows, navigation lifecycle, and navigation painting.
- Modify `tests/test_home_pet.py`: new boundary and saved-position normalization.
- Modify `tests/test_home_scene.py`: scale, contact geometry, shadow, navigation lifecycle, layer order, and painting.
- Update `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园专用宠物与2.5D移动设计.md` with implementation evidence.

---

### Task 1: Lower the Walkable Far Edge

**Files:**
- Modify: `home_pet.py:10-16`
- Test: `tests/test_home_pet.py:7-55`

**Interfaces:**
- Consumes: `clamp_to_walkable(point, polygon=HOME_WALKABLE_POLYGON)` and `load_home_pet_position(home_scene, legacy_x)`.
- Produces: polygon `((60,460), (1740,460), (1800,730), (0,730))`.

- [ ] **Step 1: Write failing boundary tests**

```python
def test_points_outside_floor_are_projected_to_walkable_polygon(self):
    self.assertEqual(
        home_pet.clamp_to_walkable((900.0, 100.0)),
        (900.0, 460.0),
    )

def test_saved_position_on_old_far_edge_moves_to_new_floor_boundary(self):
    self.assertEqual(
        home_pet.load_home_pet_position(
            {"pet_position": {"x": 900.0, "y": 420.0}}
        ),
        (900.0, 460.0),
    )
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_home_pet.py -k "outside_floor or old_far_edge" -q
```

Expected: assertions receive `420.0` instead of `460.0`.

- [ ] **Step 3: Implement the polygon change**

```python
HOME_WALKABLE_POLYGON: tuple[Point, ...] = (
    (60.0, 460.0),
    (1740.0, 460.0),
    (1800.0, 730.0),
    (0.0, 730.0),
)
```

Do not alter clamping or depth-scale algorithms.

- [ ] **Step 4: Verify GREEN**

Run `python -m pytest tests/test_home_pet.py -q`. Expected: all home-pet tests pass.

- [ ] **Step 5: Review checkpoint**

Inspect `git diff -- home_pet.py tests/test_home_pet.py`; confirm only the far edge changed. Do not stage or commit.

---

### Task 2: Normalize Direction Scale and Frame-Aware Contact Shadows

**Files:**
- Modify: `home_scene.py:38-115, 548-625`
- Test: `tests/test_home_scene.py:19-110, 637-735`

**Interfaces:**
- Produces `HomePetWalkRenderSpec`, `home_pet_frame_contact(direction, frame_index)`, `home_pet_shadow_rect(body, contact)`, and `home_pet_draw_rect(visual_scale=1.0)`.

- [ ] **Step 1: Add failing contact and mirror tests**

```python
def test_frame_contact_metadata_wraps_and_mirrors_horizontal_center(self):
    self.assertEqual(
        home_scene.home_pet_frame_contact("front_right", 0),
        (0.5547, 0.1523, 0.9784),
    )
    self.assertEqual(
        home_scene.home_pet_frame_contact("front_left", 0),
        (0.4453, 0.1523, 0.9784),
    )
    self.assertEqual(
        home_scene.home_pet_frame_contact("back_right", 8),
        (0.4102, 0.1250, 0.9806),
    )
```

Encode these measured tables verbatim:

```python
HOME_PET_FRONT_CONTACTS = (
    (0.5547, 0.1523, 0.9784), (0.5410, 0.1562, 0.9763),
    (0.5098, 0.1523, 0.9720), (0.4844, 0.1484, 0.9612),
    (0.6348, 0.5039, 0.9526), (0.6309, 0.5156, 0.9591),
    (0.5527, 0.6016, 0.9547), (0.5078, 0.6211, 0.9440),
)
HOME_PET_BACK_CONTACTS = (
    (0.4102, 0.1250, 0.9806), (0.3779, 0.1230, 0.9828),
    (0.3555, 0.1211, 0.9828), (0.3438, 0.1055, 0.9806),
    (0.3887, 0.1211, 0.9828), (0.3857, 0.2988, 0.9828),
    (0.4053, 0.3965, 0.9806), (0.3613, 0.3633, 0.9828),
)
```

- [ ] **Step 2: Add failing scale and shadow tests**

```python
front = scene.home_pet_draw_rect(visual_scale=1.0)
back = scene.home_pet_draw_rect(visual_scale=1.06)
self.assertAlmostEqual(back.width(), front.width() * 1.06)
self.assertAlmostEqual(back.height(), front.height() * 1.06)
self.assertAlmostEqual(back.bottom(), front.bottom())

shadow = home_scene.home_pet_shadow_rect(
    QRectF(10.0, 20.0, 100.0, 100.0),
    (0.4, 0.2, 0.98),
)
self.assertEqual(shadow, QRectF(34.0, 113.75, 32.0, 5.5))
```

- [ ] **Step 3: Verify RED**

Run `python -m pytest tests/test_home_scene.py -k "frame_contact or shadow_uses or draw_rect" -q`.

Expected: missing contact helper and old method signatures.

- [ ] **Step 4: Add the named render specification**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class HomePetWalkRenderSpec:
    pixmap: QPixmap
    source_rect: QRect
    mirrored: bool
    frame_index: int
    visual_scale: float
    contact_center_x: float
    contact_width: float
    contact_foot_y: float
```

`home_pet_frame_contact` selects front/back table, wraps modulo 8, and replaces `center` with `round(1.0 - center, 4)` for `_left` directions.

- [ ] **Step 5: Implement exact shadow geometry**

```python
def home_pet_shadow_rect(body, contact):
    center_ratio, width_ratio, foot_ratio = contact
    width = max(
        body.width() * 0.32,
        min(body.width() * 0.72, body.width() * width_ratio * 1.15),
    )
    height = body.height() * 0.055
    center_x = body.left() + body.width() * center_ratio
    center_y = body.top() + body.height() * foot_ratio - body.height() * 0.015
    return QRectF(center_x - width / 2, center_y - height / 2, width, height)
```

- [ ] **Step 6: Make one frame drive sprite, scale, and shadow**

Return `HomePetWalkRenderSpec` from `home_pet_walk_render_spec(now)`, with scale `1.06` for `back_*` and `1.0` for `front_*`. In `_draw_home_pet`, compute the spec once, anchor the scaled body bottom at `world_y`, then derive the shadow from the same spec's contact tuple. Keep sleep fallback rendering intact.

Update existing tuple-unpacking tests to named fields such as `spec.source_rect`, `spec.mirrored`, and `spec.visual_scale`.

Also assert that the same render spec carries the measured contact for its selected frame:

```python
self.assertEqual(spec.frame_index, 0)
self.assertEqual(
    (spec.contact_center_x, spec.contact_width, spec.contact_foot_y),
    (0.4102, 0.1250, 0.9806),
)
```

- [ ] **Step 7: Verify GREEN**

Run `python -m pytest tests/test_home_scene.py -q`. Expected: all home-scene tests pass.

- [ ] **Step 8: Review checkpoint**

Inspect the diff and confirm both PNG files remain untouched and mirrored directions mirror contact center as well as artwork. Do not stage or commit.

---

### Task 3: Add Manual Destination State and Fade Lifecycle

**Files:**
- Modify: `home_scene.py:119-156, 259-296, 366-395, 477-496, 895-930`
- Test: `tests/test_home_scene.py:409-485, 530-635`

**Interfaces:**
- Consumes normalized `HomePetController.target` and `advance(dt)` events.
- Produces `HOME_DESTINATION_FADE_SECONDS`, `home_destination_opacity`, `_manual_destination`, `_destination_fade_started_at`, `_clear_navigation_feedback`, and `_start_destination_fade`.

- [ ] **Step 1: Write the failing opacity test**

```python
def test_destination_opacity_is_full_until_fade_then_reaches_zero(self):
    self.assertEqual(home_scene.home_destination_opacity(None, 10.0), 1.0)
    self.assertAlmostEqual(
        home_scene.home_destination_opacity(10.0, 10.175), 0.5
    )
    self.assertEqual(home_scene.home_destination_opacity(10.0, 10.35), 0.0)
```

- [ ] **Step 2: Write failing command and replacement tests**

```python
scene.show_scene()
canvas = scene.scene_canvas_rect()
scene._camera_x = 450
self.assertTrue(scene.command_home_pet(QPoint(canvas.left() + 450, 100), now=10.0))
self.assertEqual(scene.home_pet.target, (900.0, 460.0))
self.assertEqual(scene._manual_destination, (900.0, 460.0))
self.assertIsNone(scene._destination_fade_started_at)

scene._destination_fade_started_at = 9.0
scene.command_home_pet(QPoint(canvas.left() + 700, 600), now=11.0)
self.assertEqual(scene._manual_destination, scene.home_pet.target)
self.assertIsNone(scene._destination_fade_started_at)
```

- [ ] **Step 3: Write failing arrival, auto-sleep, and cleanup tests**

```python
scene.home_pet.position = (500.0, 600.0)
scene.home_pet.command_move((505.0, 600.0), now=9.0)
scene._manual_destination = scene.home_pet.target
scene._last_pet_tick = 9.9
events = scene._advance_home_pet(now=10.0)
self.assertIn("arrived", events)
self.assertEqual(scene._destination_fade_started_at, 10.0)
scene._advance_home_pet(now=10.35)
self.assertIsNone(scene._manual_destination)

scene._clear_navigation_feedback()
scene.home_pet.request_auto_sleep((600.0, 600.0), now=11.0)
self.assertIsNone(scene._manual_destination)

scene._manual_destination = (700.0, 600.0)
scene.toggle_decoration_mode()
self.assertIsNone(scene._manual_destination)
```

Also extend `hide_scene` and re-entry tests to require navigation state `None`.

- [ ] **Step 4: Verify RED**

Run `python -m pytest tests/test_home_scene.py -k "destination or manual_arrival" -q`.

Expected: missing helper/state failures.

- [ ] **Step 5: Implement opacity and state helpers**

```python
HOME_DESTINATION_FADE_SECONDS = 0.35

def home_destination_opacity(fade_started_at, now):
    if fade_started_at is None:
        return 1.0
    elapsed = max(0.0, float(now) - float(fade_started_at))
    return max(0.0, 1.0 - elapsed / HOME_DESTINATION_FADE_SECONDS)

def _clear_navigation_feedback(self):
    self._manual_destination = None
    self._destination_fade_started_at = None

def _start_destination_fade(self, now):
    if self._manual_destination is not None:
        self._destination_fade_started_at = float(now)
```

Initialize both attributes before `__init__` calls `_sync_scene()`.

- [ ] **Step 6: Wire lifecycle without persistence**

- After successful `command_move`, copy the controller's already-clamped `target` into `_manual_destination` and clear fade start.
- In `_advance_home_pet`, start fade on manual `arrived`; clear after opacity reaches zero.
- Clear navigation on `show_scene`, `hide_scene`, and entering decoration.
- Never set manual destination from `request_auto_sleep`.
- Leave `_save_home_pet_position` writing only `pet_position`.

- [ ] **Step 7: Verify GREEN**

Run `python -m pytest tests/test_home_scene.py -k "destination or manual_arrival or decoration_mode or reentering_home" -q`.

Expected: all selected lifecycle tests pass.

- [ ] **Step 8: Review checkpoint**

Confirm no path, target, or fade timestamp is added to persistent state. Do not stage or commit.

---

### Task 4: Render the Straight Path, Circle, and Down Arrow

**Files:**
- Modify: `home_scene.py:9-10, 306-335, 675-688`
- Test: `tests/test_home_scene.py:670-780`

**Interfaces:**
- Produces `navigation_feedback(now) -> dict | None`, `_draw_navigation_feedback(painter, now=None)`, and render entry `((1, 1.0), "navigation", "home_navigation")`.

- [ ] **Step 1: Write the failing shortening test**

```python
scene._camera_x = 450
scene._manual_destination = (900.0, 600.0)
scene.home_pet.position = (600.0, 600.0)
first = scene.navigation_feedback(now=10.0)
scene.home_pet.position = (750.0, 600.0)
second = scene.navigation_feedback(now=10.0)
self.assertEqual(first["end"], second["end"])
self.assertGreater(
    first["end"].x() - first["start"].x(),
    second["end"].x() - second["start"].x(),
)
```

- [ ] **Step 2: Write failing layer and pixel tests**

Use the existing purchased rug/sofa fixture:

```python
scene._manual_destination = (900.0, 600.0)
order = [entry[2] for entry in scene._scene_render_entries()]
self.assertLess(order.index("home_rug"), order.index("home_navigation"))
self.assertLess(order.index("home_navigation"), order.index("home_pet"))
self.assertLess(order.index("home_navigation"), order.index("home_sofa"))
```

Render `_draw_navigation_feedback` into transparent `QImage`; assert nonzero Alpha within a `3×3` neighborhood around a painted path dash and at the destination circle edge.

- [ ] **Step 3: Verify RED**

Run `python -m pytest tests/test_home_scene.py -k "navigation_feedback or navigation_layer" -q`.

Expected: missing geometry/draw methods and missing render entry.

- [ ] **Step 4: Implement navigation geometry**

```python
def navigation_feedback(self, now=None):
    if self._manual_destination is None or not self.home_pet_visible():
        return None
    current = time.monotonic() if now is None else float(now)
    opacity = home_destination_opacity(
        self._destination_fade_started_at, current
    )
    if opacity <= 0.0:
        return None
    start_x, start_y = self.home_pet.position
    end_x, end_y = self._manual_destination
    offset = self._scene_content_offset() - self._camera_x
    return {
        "start": QPointF(offset + start_x, start_y),
        "end": QPointF(offset + end_x, end_y),
        "opacity": opacity,
        "pulse": 1.0 + 0.06 * math.sin(current * math.tau / 0.9),
        "depth_scale": depth_scale_for_y(end_y),
    }
```

- [ ] **Step 5: Insert the floor-layer entry**

Append `((1, 1.0), "navigation", "home_navigation")` only when feedback exists. Handle `kind == "navigation"` in the paint loop before pet/furniture drawing. Rug remains `(1, 0.0)`; pet and solid furniture remain key group `2`.

- [ ] **Step 6: Draw exact requested styling**

- Path: `QColor(166, 95, 71, round(150 * opacity))`, round-cap pen, width `max(1.5, min(2.5, 2.0 * depth_scale))`, dash pattern `[3.0, 3.0]`.
- Skip only the line when start/end distance is `<=1px`; still draw marker.
- Circle: base radius `12 * depth_scale * pulse`, warm 2 px outline, low-Alpha warm fill.
- Arrow: height `10 * depth_scale * pulse`, points down, tip remains `2px` above circle edge.
- Wrap all painting in `save()`/`restore()`.

- [ ] **Step 7: Verify GREEN**

Run `python -m pytest tests/test_home_scene.py -q`. Expected: all home-scene tests pass.

- [ ] **Step 8: Review checkpoint**

Confirm feedback is hidden during decoration and can be occluded by the pet/solid furniture without changing the warm furniture selection style. Do not stage or commit.

---

### Task 5: Full Verification and Documentation

**Files:**
- Update: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园专用宠物与2.5D移动设计.md`
- Update: this plan's checkboxes/execution status only.

- [ ] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_home_pet.py tests/test_home_scene.py tests/test_scene_system.py -q
```

Expected: exit code `0`, no failures.

- [ ] **Step 2: Run the full suite**

```powershell
python -m pytest -q
```

Expected: exit code `0`. Record the fresh count/duration; never reuse `254 passed`.

- [ ] **Step 3: Run compile and diff checks**

```powershell
python -m py_compile home_scene.py home_pet.py pet.py scene_system.py
git diff --check
git status --short
```

Expected: compile and diff check exit `0`; existing LF/CRLF warnings are informational.

- [ ] **Step 4: Restart only this worktree's source app**

Resolve `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py`; stop only Python processes whose command line contains that exact path, then launch it with `pythonw.exe`, this worktree as working directory, and hidden console window.

- [ ] **Step 5: Manual acceptance**

- Click wall area: target and pet stop at `y=460` floor boundary.
- Compare front/back at same depth: no visible size drop.
- Watch all eight frames: shadow remains under contact paws.
- Click a distant target: warm dashed path, circle, and down arrow appear.
- Path shortens; furniture can cover it; arrival fades in about `350ms`.
- Second click replaces old marker; decoration/exit clears it.
- Automatic low-energy walk to rug shows no manual path.

- [ ] **Step 6: Update Obsidian evidence**

Append final boundary, scale, frame-shadow strategy, navigation lifecycle, fresh automated results, manual observations, and remaining asset limitations. Preserve earlier history.

- [ ] **Step 7: Final review checkpoint**

Review `git diff` and `git status`. Report intended files, preserved pre-existing changes, fresh evidence, launched PID, and manual observations. Do not stage, commit, push, or publish.

## Execution Status (2026-08-10)

- [x] Task 1: walkable far edge moved from `y=420` to `y=460` with RED/GREEN coverage.
- [x] Task 2: per-frame contact metadata, anchored `1.06` back scale, and contact-following shadow implemented.
- [x] Task 3: manual destination replacement, arrival fade, cleanup lifecycle, and auto-sleep isolation implemented.
- [x] Task 4: shortening dashed path, pulsing circle, down arrow, and floor-layer ordering implemented.
- [x] Task 5 automated verification: focused `73 passed`; full suite `262 passed`; compile and `git diff --check` exit `0`.
- [x] Obsidian implementation evidence updated.
- [x] Current worktree source launched as PID `22048`.
- [ ] Visual acceptance remains for the user in the launched app; no code, asset, or test blocker is known.
