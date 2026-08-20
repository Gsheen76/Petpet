# Home Pet Input and Overlay Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make left-click move the home pet, make right-click open the existing shortcut menu only when the home pet is hit, and anchor all shared pet overlays/windows to the visible home pet while the home is active.

**Architecture:** `HomeSceneWindow` owns home-pet hit testing and converts its rendered body rectangle into global screen coordinates. `PetWindow` exposes one overlay context (`interface_anchor_rect`, `interface_screen_rect`, `interface_anchor_visible`) and one shared placement helper, so existing menu, speech, status and feature windows remain single implementations that work both indoors and outdoors.

**Tech Stack:** Python 3, PyQt5, `unittest`, `pytest`, existing `home_scene.py`, `pet.py`, and `progression_ui.py`.

## Global Constraints

- Work only in `D:\Agent_project\Petpet\.worktrees\home-scene-system` on `codex/home-scene-system`.
- Preserve every existing uncommitted change; never run `git reset`, `git checkout`, or overwrite unrelated files.
- Use `apply_patch` for manual edits.
- Follow RED-GREEN-REFACTOR for every production behavior.
- Do not change shortcut-menu contents, pages, action semantics, furniture editing, pathfinding, or animation assets.
- Left-click valid floor moves; right-click only a visible home pet opens the menu; right-click elsewhere does nothing.
- Decoration mode accepts neither pet movement nor the pet menu.
- Do not stage, commit, push, publish, or release unless the user explicitly asks.
- Final source launch must use this worktree's exact `pet.py`.

---

### Task 1: Route Left Click to Movement and Right Click to Home-Pet Hit Testing

**Files:**
- Modify: `home_scene.py:720-840, 1065-1100, 1226-1240`
- Test: `tests/test_home_scene.py:428-565`

**Interfaces:**
- Consumes: existing `home_pet_draw_rect(visual_scale=1.0)`, `home_pet_walk_render_spec(now=None)`, `command_home_pet(point, now=None)`.
- Produces: `home_pet_hit_rect() -> QRectF`, `home_pet_global_rect() -> QRect`, `open_home_pet_menu(point: QPoint) -> bool`.
- Calls: `self.pet.open_bubble_menu()` only after a successful right-click hit.

- [ ] **Step 1: Add one reusable visible-home test fixture**

Add to the existing home-scene test class:

```python
def _visible_home_scene(self):
    state = progression.ensure_progression({"energy": 100.0})
    pet_host = SimpleNamespace(
        state=state,
        width=lambda: 190,
        height=lambda: 220,
        hide=Mock(),
        show=Mock(),
        raise_=Mock(),
        hide_overlays=Mock(),
        open_bubble_menu=Mock(),
        current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        auto_sleep_energy_threshold=30.0,
        auto_wake_energy_threshold=80.0,
    )
    scene = home_scene.HomeSceneWindow(pet_host, Mock())
    self.addCleanup(scene.close)
    scene.show_scene()
    return scene
```

- [ ] **Step 2: Replace the old right-click movement test with a failing left-click test**

Use a real `HomeSceneWindow`; patch only the command boundary so the test observes routing:

```python
def test_left_button_press_dispatches_one_home_move_command(self):
    scene = self._visible_home_scene()
    point = QPoint(scene.scene_canvas_rect().left() + 400, 600)
    event = SimpleNamespace(
        button=lambda: Qt.LeftButton,
        pos=lambda: point,
        accept=Mock(),
    )

    with patch.object(scene, "command_home_pet", return_value=True) as command:
        scene.mousePressEvent(event)

    command.assert_called_once_with(point)
    event.accept.assert_called_once_with()
```

- [ ] **Step 3: Add failing right-click hit and miss tests**

```python
def test_right_click_opens_shared_menu_only_inside_home_pet_body(self):
    scene = self._visible_home_scene()
    scene.home_pet.position = (900.0, 600.0)
    scene._camera_x = 450
    inside = scene.home_pet_draw_rect().center().toPoint()
    outside = scene.scene_canvas_rect().topLeft() + QPoint(30, 100)

    self.assertTrue(scene.open_home_pet_menu(inside))
    scene.pet.open_bubble_menu.assert_called_once_with()

    scene.pet.open_bubble_menu.reset_mock()
    self.assertFalse(scene.open_home_pet_menu(outside))
    scene.pet.open_bubble_menu.assert_not_called()
```

Add `open_bubble_menu=Mock()` to the test pet fixture. Add a separate decoration assertion:

```python
scene.toggle_decoration_mode()
self.assertFalse(scene.open_home_pet_menu(inside))
scene.pet.open_bubble_menu.assert_not_called()
```

- [ ] **Step 4: Add a failing global rectangle conversion test**

```python
def test_home_pet_global_rect_maps_the_rendered_body_from_scene_window(self):
    scene = self._visible_home_scene()
    scene.home_pet.position = (900.0, 600.0)
    scene._camera_x = 450
    local = scene.home_pet_hit_rect().toAlignedRect()

    result = scene.home_pet_global_rect()

    self.assertEqual(result.topLeft(), scene.mapToGlobal(local.topLeft()))
    self.assertEqual(result.size(), local.size())
```

- [ ] **Step 5: Run the Task 1 tests and verify RED**

Run:

```powershell
python -m pytest tests/test_home_scene.py -k "left_button_press or opens_shared_menu or global_rect" -q
```

Expected: failures show left-click does not call movement and the three new home-pet geometry/menu methods do not exist.

- [ ] **Step 6: Implement rendered-body geometry and right-click hit testing**

Add beside `home_pet_draw_rect`:

```python
def home_pet_hit_rect(self):
    spec = self.home_pet_walk_render_spec()
    visual_scale = spec.visual_scale if spec is not None else 1.0
    return self.home_pet_draw_rect(visual_scale)

def home_pet_global_rect(self):
    local = self.home_pet_hit_rect().toAlignedRect()
    return QRect(self.mapToGlobal(local.topLeft()), local.size())

def open_home_pet_menu(self, point):
    if (
        not self.home_pet_visible()
        or self.is_decorating()
        or not self.scene_canvas_rect().contains(point)
        or not self.home_pet_hit_rect().contains(QPointF(point))
    ):
        return False
    opener = getattr(self.pet, "open_bubble_menu", None)
    if not callable(opener):
        return False
    opener()
    return True
```

Import `QPointF` only if it is not already present.

- [ ] **Step 7: Change mouse routing with controls taking priority**

Replace the right-click movement branch and normal left-click fallthrough with:

```python
def mousePressEvent(self, event):
    if event.button() == Qt.RightButton:
        if self.open_home_pet_menu(event.pos()):
            event.accept()
        return
    if event.button() != Qt.LeftButton:
        return
    if self.handle_scene_click(event.pos()):
        event.accept()
        return
    if not self.is_decorating():
        if self.command_home_pet(event.pos()):
            event.accept()
        return
    if not self.begin_furniture_gesture(event.pos()):
        event.accept()
        return
    self.setCursor(Qt.ClosedHandCursor)
    event.accept()
```

This preserves buttons, keeps furniture gestures decoration-only, and makes blank right-click inert.

- [ ] **Step 8: Verify Task 1 GREEN and the full home-scene file**

Run:

```powershell
python -m pytest tests/test_home_scene.py -k "left_button_press or opens_shared_menu or global_rect or ignored_over_controls" -q
python -m pytest tests/test_home_scene.py -q
```

Expected: both commands exit `0`; the former right-click movement expectations have been replaced, not duplicated.

---

### Task 2: Add the Unified Pet Interface Context and Shared Menu Entry

**Files:**
- Modify: `pet.py:4424-4460, 4845-4895, 5847-5889`
- Test: `tests/test_menu_ui.py:79-225`

**Interfaces:**
- Consumes: `HomeSceneWindow.home_pet_global_rect()`, `HomeSceneWindow.home_pet_visible()`.
- Produces: `PetWindow.interface_anchor_rect() -> QRect`, `PetWindow.interface_screen_rect() -> QRect`, `PetWindow.interface_anchor_visible() -> bool`, `PetWindow.interface_window_position(window_size: QSize, gap: int = 16) -> QPoint`, `PetWindow.open_bubble_menu() -> None`.
- Existing `PetWindow.contextMenuEvent` becomes a thin call to `open_bubble_menu`.

- [ ] **Step 1: Write failing indoor/outdoor interface-context tests**

```python
def test_interface_anchor_uses_home_pet_while_home_is_visible(self):
    home_rect = QRect(1100, 620, 140, 126)
    home = SimpleNamespace(home_pet_global_rect=lambda: home_rect)
    harness = SimpleNamespace(
        _active_home_interface=lambda: home,
        geometry=lambda: QRect(20, 30, 190, 220),
    )
    self.assertEqual(pet.PetWindow.interface_anchor_rect(harness), home_rect)
    self.assertTrue(pet.PetWindow.interface_anchor_visible(harness))

def test_active_home_interface_requires_visible_non_decorating_home_pet(self):
    home = SimpleNamespace(
        isVisible=lambda: True,
        is_decorating=lambda: False,
        home_pet_visible=lambda: True,
    )
    harness = SimpleNamespace(home_scene_window=home)
    self.assertIs(pet.PetWindow._active_home_interface(harness), home)

    home.is_decorating = lambda: True
    self.assertIsNone(pet.PetWindow._active_home_interface(harness))

def test_interface_anchor_falls_back_to_desktop_pet_outside_home(self):
    desktop = QRect(20, 30, 190, 220)
    harness = SimpleNamespace(
        _active_home_interface=lambda: None,
        geometry=lambda: desktop,
        isVisible=lambda: True,
    )
    self.assertEqual(pet.PetWindow.interface_anchor_rect(harness), desktop)
    self.assertTrue(pet.PetWindow.interface_anchor_visible(harness))
```

- [ ] **Step 2: Write failing placement and shared-menu tests**

```python
def test_interface_window_position_prefers_space_beside_anchor(self):
    harness = SimpleNamespace(
        interface_anchor_rect=lambda: QRect(900, 500, 120, 100),
        interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
    )
    point = pet.PetWindow.interface_window_position(
        harness, QSize(500, 700), gap=16
    )
    self.assertEqual(point.x(), 1036)
    self.assertGreaterEqual(point.y(), 0)

def test_open_bubble_menu_closes_old_menu_before_replacement(self):
    old = SimpleNamespace(_close=Mock())
    harness = SimpleNamespace(_bubble_menu=old)
    with patch("pet.BubbleMenu") as menu_type:
        pet.PetWindow.open_bubble_menu(harness)
    old._close.assert_called_once_with()
    self.assertIs(harness._bubble_menu, menu_type.return_value)

def test_open_home_scene_is_idempotent_while_already_visible(self):
    scene = SimpleNamespace(isVisible=lambda: True, raise_=Mock(), show_scene=Mock())
    harness = SimpleNamespace(home_scene_window=scene)
    pet.PetWindow.open_home_scene(harness)
    scene.raise_.assert_called_once_with()
    scene.show_scene.assert_not_called()
```

- [ ] **Step 3: Verify Task 2 RED**

Run:

```powershell
python -m pytest tests/test_menu_ui.py -k "interface_anchor or interface_window_position or open_bubble_menu" -q
```

Expected: missing-method failures.

- [ ] **Step 4: Implement the interface context without changing desktop physics APIs**

Add to `PetWindow` near `current_screen_rect`; do not modify `geometry()` or `current_screen_rect()`:

```python
def _active_home_interface(self):
    home = getattr(self, "home_scene_window", None)
    if home is None:
        return None
    try:
        if home.isVisible() and not home.is_decorating() and home.home_pet_visible():
            return home
    except RuntimeError:
        return None
    return None

def interface_anchor_rect(self):
    home = self._active_home_interface()
    if home is not None:
        rect = home.home_pet_global_rect()
        if not rect.isEmpty():
            return rect
    return self.geometry()

def interface_anchor_visible(self):
    return self._active_home_interface() is not None or self.isVisible()

def interface_screen_rect(self):
    anchor = self.interface_anchor_rect()
    screen = self.screen_at(anchor.center())
    if screen is not None:
        return screen.availableGeometry()
    return self.current_screen_rect()

def interface_window_position(self, window_size, gap=16):
    anchor = self.interface_anchor_rect()
    screen = self.interface_screen_rect()
    width, height = window_size.width(), window_size.height()
    right_x = anchor.right() + int(gap)
    left_x = anchor.left() - width - int(gap)
    if right_x + width - 1 <= screen.right():
        x = right_x
    elif left_x >= screen.left():
        x = left_x
    else:
        x = screen.center().x() - width // 2
    y = anchor.center().y() - height // 2
    x = max(screen.left(), min(x, screen.right() - width + 1))
    y = max(screen.top(), min(y, screen.bottom() - height + 1))
    return QPoint(int(x), int(y))
```

- [ ] **Step 5: Centralize menu opening and make home re-entry idempotent**

```python
def open_bubble_menu(self):
    old = getattr(self, "_bubble_menu", None)
    if old is not None:
        try:
            old._close()
        except RuntimeError:
            pass
    self._bubble_menu = BubbleMenu(self)

def contextMenuEvent(self, event):
    self.open_bubble_menu()
    super().contextMenuEvent(event)
```

At the start of `open_home_scene`, return after raising/syncing an already visible home instead of calling `show_scene` again:

```python
if self.home_scene_window is not None and self.home_scene_window.isVisible():
    self.home_scene_window.raise_()
    return
```

This keeps the existing BubbleMenu “home” action but prevents position/target reset indoors.

- [ ] **Step 6: Verify Task 2 GREEN**

Run:

```powershell
python -m pytest tests/test_menu_ui.py -k "interface_anchor or interface_window_position or open_bubble_menu or open_home_scene" -q
```

Expected: all selected tests pass, including the pre-existing test that first entry creates and shows a home scene.

---

### Task 3: Anchor Menu, Status, Speech, and Interaction Feedback Indoors

**Files:**
- Modify: `pet.py:2249-2258, 2643-2660, 2999-3018, 3115-3132, 3293-3411, 4419-4422, 4871-4890, 5161-5174, 5537-5543`
- Modify: `home_scene.py:235-255`
- Test: `tests/test_menu_ui.py:246-500`
- Test: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: the five Task 2 `PetWindow.interface_*` methods.
- Produces: `PetWindow.follow_interface_overlays() -> None`.
- `SpeechBubble`, `BubbleMenu`, `StatBubble`, interactive bubbles and reward bubbles read the interface context instead of desktop geometry.

- [ ] **Step 1: Write failing menu/stat placement tests**

Use lightweight harnesses and call unbound placement methods:

```python
def test_bubble_and_stat_menu_place_from_interface_anchor(self):
    anchor = QRect(1100, 620, 140, 126)
    screen = QRect(0, 0, 1920, 1080)
    pet_host = SimpleNamespace(
        interface_anchor_rect=lambda: anchor,
        interface_screen_rect=lambda: screen,
    )
    menu = SimpleNamespace(pet=pet_host, W=590, H=112, move=Mock())
    pet.BubbleMenu._place(menu)
    menu.move.assert_called_once()
    self.assertAlmostEqual(menu.move.call_args.args[0] + 590 / 2, anchor.center().x(), delta=2)

    stats = SimpleNamespace(
        pet=pet_host,
        width=lambda: 620,
        height=lambda: 416,
        move=Mock(),
    )
    pet.StatBubble._place(stats)
    stats.move.assert_called_once()
```

- [ ] **Step 2: Write failing speech availability and geometry tests**

```python
def test_say_uses_visible_home_interface_when_desktop_pet_is_hidden(self):
    speech = SimpleNamespace(isVisible=lambda: True, show_text=Mock())
    harness = SimpleNamespace(
        interface_anchor_visible=lambda: True,
        isVisible=lambda: False,
        _speech_bubble=speech,
    )
    pet.PetWindow.say(harness, "我在小屋里", 2200)
    speech.show_text.assert_called_once_with("我在小屋里", 2200)

def test_speech_bubble_geometry_uses_interface_anchor(self):
    host = SimpleNamespace(
        interface_anchor_rect=lambda: QRect(1100, 620, 140, 126),
        interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
    )
    bubble = SimpleNamespace(pet=host)
    rect = pet.SpeechBubble._bubble_geometry(bubble, 260, 90)
    self.assertEqual(rect.center().x(), 1170)
    self.assertLess(rect.bottom(), host.interface_anchor_rect().bottom())
```

- [ ] **Step 3: Write a failing home-sync follow test**

```python
def test_home_sync_repositions_visible_pet_overlays(self):
    scene = self._visible_home_scene()
    scene.pet.follow_interface_overlays = Mock()

    scene._sync_scene()

    scene.pet.follow_interface_overlays.assert_called_once_with()
```

- [ ] **Step 4: Verify Task 3 RED**

Run:

```powershell
python -m pytest tests/test_menu_ui.py tests/test_home_scene.py -k "interface_anchor or visible_home_interface or speech_bubble_geometry or home_sync_repositions" -q
```

Expected: placement still reads `geometry/current_screen_rect/isVisible`, and the follow method is missing.

- [ ] **Step 5: Replace direct desktop geometry in shared overlays**

Apply these exact substitutions in the listed overlay classes:

```python
g = self.pet.interface_anchor_rect()
scr = self.pet.interface_screen_rect()
```

Use them in `StatBubble._place`, `BubbleMenu._place`, and the side-placement method around line 2999. In `SpeechBubble`:

```python
def follow_pet(self):
    if not self.pet.interface_anchor_visible():
        self.clear_messages()
        return
    self.move(self._bubble_geometry(self.width(), self.height()).topLeft())

def _bubble_geometry(self, width, height):
    g = self.pet.interface_anchor_rect()
    screen = self.pet.interface_screen_rect()
    x = g.center().x() - width // 2
    y = g.top() + 3 - max(0, height - 56)
    x = max(screen.left() + 4, min(x, screen.right() - width - 4))
    y = max(screen.top() + 4, min(y, screen.bottom() - height - 4))
    return QRect(int(x), int(y), int(width), int(height))
```

Change `_show_next_or_hide` and `PetWindow.say` to `interface_anchor_visible()`.

- [ ] **Step 6: Move transient action/reward feedback to the same anchor**

At the existing `BonusBubble` creation sites (interaction result, level-up, pending Pet coins), replace `pet.geometry()` / `self.geometry()` with `interface_anchor_rect()`. Do not alter reward values or timers.

- [ ] **Step 7: Extract and call one overlay-follow method**

Move the existing menu/speech follow blocks from `on_tick` into:

```python
def follow_interface_overlays(self):
    if self._bubble_menu is not None:
        try:
            if self._bubble_menu.isVisible():
                self._bubble_menu.follow_pet()
            else:
                self._bubble_menu = None
        except RuntimeError:
            self._bubble_menu = None
    if self._speech_bubble is not None:
        try:
            if self._speech_bubble.isVisible():
                self._speech_bubble.follow_pet()
        except RuntimeError:
            self._speech_bubble = None
```

Call it from `PetWindow.on_tick`. At the end of visible `HomeSceneWindow._sync_scene`, call it through `getattr`:

```python
follow = getattr(self.pet, "follow_interface_overlays", None)
if callable(follow):
    follow()
```

- [ ] **Step 8: Verify Task 3 GREEN**

Run:

```powershell
python -m pytest tests/test_menu_ui.py tests/test_home_scene.py -k "bubble or speech or interface or overlay" -q
```

Expected: selected tests pass and the pre-existing overlay cleanup tests remain green.

---

### Task 4: Place Chat, Progression, Settings, and Tutorial Windows Near the Active Pet

**Files:**
- Modify: `pet.py:1131-1153, 1503-1590, 2160-2178, 5852-5908, 6026-6032`
- Modify: `progression_ui.py:360-378`
- Test: `tests/test_menu_ui.py`
- Test: `tests/test_progression_ui.py`

**Interfaces:**
- Consumes: `interface_anchor_rect`, `interface_screen_rect`, `interface_window_position` from Task 2.
- Produces: `SettingsWindow.show_near_pet() -> None`; existing Chat/Tutorial/Progression window entry points all use the active interface context.

- [ ] **Step 1: Write failing chat and settings placement tests**

```python
def test_chat_and_settings_use_interface_window_position(self):
    position = QPoint(880, 240)
    pet_host = SimpleNamespace(
        settings=dict(pet.DEFAULT_SETTINGS),
        interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        interface_window_position=Mock(return_value=position),
    )
    chat = SimpleNamespace(
        pet=pet_host,
        s=pet_host.settings,
        width=lambda: 560,
        height=lambda: 720,
        size=lambda: QSize(560, 720),
        setFixedSize=Mock(), move=Mock(), show=Mock(), raise_=Mock(),
        activateWindow=Mock(), input=SimpleNamespace(setFocus=Mock()),
    )
    pet.ChatWindow.show_near_pet(chat)
    chat.move.assert_called_once_with(position)

    settings = SimpleNamespace(
        pet=pet_host, size=lambda: QSize(840, 960), move=Mock(),
        show=Mock(), raise_=Mock(), activateWindow=Mock(),
    )
    pet.SettingsWindow.show_near_pet(settings)
    settings.move.assert_called_once_with(position)
```

- [ ] **Step 2: Write failing progression and tutorial placement tests**

In `tests/test_progression_ui.py`:

```python
def test_progression_window_uses_active_interface_position(self):
    point = QPoint(700, 180)
    window.pet.interface_window_position = Mock(return_value=point)
    window.show_near_pet()
    self.assertEqual(window.pos(), point)
    window.pet.interface_window_position.assert_called_once_with(
        window.size(), gap=20
    )
```

In `tests/test_menu_ui.py`, construct a tutorial harness with `interface_window_position=Mock` and assert `TutorialWindow.start` moves to its return value.

- [ ] **Step 3: Verify Task 4 RED**

Run:

```powershell
python -m pytest tests/test_menu_ui.py tests/test_progression_ui.py -k "interface_window_position or active_interface_position" -q
```

Expected: Chat/Progression/Tutorial still read desktop geometry or screen, and Settings has no `show_near_pet`.

- [ ] **Step 4: Update window placement methods**

After Chat calculates and applies its bounded size, replace its manual side calculation with:

```python
self.move(self.pet.interface_window_position(self.size(), gap=16))
```

Add to `SettingsWindow`:

```python
def show_near_pet(self):
    self.move(self.pet.interface_window_position(self.size(), gap=16))
    self.show()
    self.raise_()
    self.activateWindow()
```

Change `PetWindow.open_settings` to call `show_near_pet()`.

In `TutorialWindow.start`, replace screen-centering with:

```python
self.move(self.pet.interface_window_position(self.size(), gap=16))
```

In `progression_ui.CozyProgressWindow.show_near_pet`, replace its complete geometry calculation with:

```python
self.refresh()
self.move(self.pet.interface_window_position(self.size(), gap=20))
self.show()
self.raise_()
self.activateWindow()
```

Records, achievements, shop and minigame hub inherit this method, so do not duplicate changes in their classes.

- [ ] **Step 5: Verify Task 4 GREEN**

Run:

```powershell
python -m pytest tests/test_menu_ui.py tests/test_progression_ui.py -k "chat or settings or tutorial or progression or shop or records or minigame" -q
```

Expected: all selected window tests pass using the interface placement helper.

---

### Task 5: Lifecycle Cleanup, Regression Verification, and Documentation

**Files:**
- Modify: `home_scene.py:424-455, 535-554`
- Modify: `pet.py:4890-4924`
- Test: `tests/test_home_scene.py`
- Test: `tests/test_menu_ui.py`
- Update: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园专用宠物与2.5D移动设计.md`
- Update: `docs/superpowers/plans/2026-08-10-home-pet-input-and-overlay-anchor-plan.md` execution status only

**Interfaces:**
- Consumes: `PetWindow.hide_overlays()`, unified interface context, home scene lifecycle.
- Produces: no new persistence fields and no new public API.

- [ ] **Step 1: Write failing cleanup tests**

```python
def test_entering_decoration_and_hiding_home_clear_interface_overlays(self):
    scene = self._visible_home_scene()
    scene.pet.hide_overlays = Mock()

    scene.toggle_decoration_mode()
    scene.pet.hide_overlays.assert_called_once_with()

    scene.pet.hide_overlays.reset_mock()
    scene.toggle_decoration_mode()
    scene.hide_scene()
    scene.pet.hide_overlays.assert_called_once_with()
```

Also assert that `show_scene` itself does not create a speech/menu overlay and that `home_scene` persistence still contains only durable scene fields, never anchor rectangles or overlay state.

- [ ] **Step 2: Verify cleanup RED**

Run:

```powershell
python -m pytest tests/test_home_scene.py tests/test_menu_ui.py -k "clear_interface_overlays or open_home_scene or persistence" -q
```

Expected: decoration/hide do not yet explicitly clear interface overlays.

- [ ] **Step 3: Wire cleanup at context boundaries**

Call `pet.hide_overlays()` when entering decoration and before hiding/exiting the home. Do not call it on ordinary home movement. Keep `show_scene` free of any automatic speech.

- [ ] **Step 4: Verify lifecycle GREEN**

Run:

```powershell
python -m pytest tests/test_home_scene.py tests/test_menu_ui.py -k "decoration or hide or overlay or persistence or open_home_scene" -q
```

Expected: selected tests exit `0` and no overlay runtime geometry appears in saved state.

- [ ] **Step 5: Run the complete focused suite**

```powershell
python -m pytest tests/test_home_pet.py tests/test_home_scene.py tests/test_menu_ui.py tests/test_progression_ui.py tests/test_scene_system.py -q
```

Expected: exit `0`, no failures.

- [ ] **Step 6: Run fresh full verification**

```powershell
python -m pytest -q
python -m py_compile pet.py home_pet.py home_scene.py scene_system.py progression.py progression_ui.py
git diff --check
git status --short --branch
```

Expected: all commands exit `0`; record the new test count and duration. Existing LF/CRLF notices are informational only.

- [ ] **Step 7: Restart only this worktree's source application**

Resolve the exact path `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py`. Stop only Python processes whose command line contains that exact path, then launch it with `pythonw.exe`, this worktree as the working directory, and a hidden console window.

- [ ] **Step 8: Perform manual acceptance**

- Left-click near and far floor points; verify movement and the existing path feedback.
- Right-click the home dog; verify the five-button primary menu and status card.
- Right-click floor, wall, furniture, sidebar and buttons; verify no pet menu opens.
- Trigger autonomous speech and an interaction response; verify the bubble follows the moving home dog.
- Open chat, shop, records, settings and tutorial; verify each appears on-screen near the home dog.
- Enter decoration and exit home; verify menu and speech overlays disappear.
- Return outdoors; verify right-click menu, speech, dragging and existing click behavior still work.

- [ ] **Step 9: Update evidence without committing**

Append the final input mapping, unified-anchor method names, overlay/window coverage, test counts, launched PID, manual observations and remaining limitations to the Obsidian record. Add an execution-status section to this plan. Do not stage, commit, push or publish.
