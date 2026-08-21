# Pet Shop, Drag, and Home Visual Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the pet shop inside the shared viewport, prevent cross-pet outfit rendering, and make the home idle pet match walk size, foot anchor, and shadow.

**Architecture:** Reuse the outfit card's compact row structure for pet cards, enforce pet ownership at the existing equipped-outfit lookup boundary, and crop static/shared pixmaps to their alpha bounds before the existing foot-anchored home renderer scales them. No new persistence fields or per-pet visual configuration are introduced.

**Tech Stack:** Python 3, PyQt5, pytest/unittest, JSON pet manifests.

## Global Constraints

- Keep every currently displayed pet-card field and keep the description on one line.
- The selected `active_pet_id` is authoritative on desktop and in the home scene.
- Do not delete or migrate an equipped outfit when its pet is inactive.
- Idle and walk visible body heights must match and their bottom edge must remain foot anchored.
- Preserve the existing resource tree and all 16 ice-cream idle frames.
- Add no dependency and no per-pet scale/shadow configuration.

---

### Task 1: Make Pet Cards Use the Shared Compact Width

**Files:**
- Modify: `tests/test_progression_ui.py`
- Modify: `petpet/progression/ui.py:1159-1256`

**Interfaces:**
- Consumes: `ShopWindow._pet_card(pet_id: str) -> QFrame` and the existing `QScrollArea` viewport.
- Produces: pet cards whose title row owns the status badge and whose bottom row owns price plus action button.

- [ ] **Step 1: Write the failing viewport regression test**

Add a test that creates a shop with both pets, shows the pet page, processes Qt events, and verifies each `petCard_*` right edge is no farther right than `shop.scroll.viewport().rect().right()` after coordinate mapping. Assert that pet name, single-line description, price, status, and action controls still exist.

```python
def test_pet_cards_fit_the_same_scroll_viewport_without_losing_information(self):
    self.pet.state["pets"] = {
        "lunch_meat": {"name": "午餐肉"},
        "ice_cream": {"name": "冰淇淋"},
    }
    self.pet.state["owned_pet_ids"] = ["lunch_meat", "ice_cream"]
    self.pet.state["active_pet_id"] = "ice_cream"
    shop = ShopWindow(self.pet, Mock())
    self.windows = [shop]
    shop.show()
    QApplication.processEvents()

    viewport = shop.scroll.viewport()
    cards = [
        shop.findChild(QFrame, "petCard_lunch_meat"),
        shop.findChild(QFrame, "petCard_ice_cream"),
    ]
    for card in cards:
        right = card.mapTo(viewport, card.rect().bottomRight()).x()
        self.assertLessEqual(right, viewport.rect().right())
    self.assertFalse(shop.findChild(QLabel, "petDescription_ice_cream").wordWrap())
    self.assertIsNotNone(shop.findChild(QLabel, "petPrice_ice_cream"))
    self.assertIsNotNone(shop.findChild(QLabel, "petStatus_ice_cream"))
    self.assertIsNotNone(shop.findChild(QPushButton, "petAction_ice_cream"))
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m pytest -q tests/test_progression_ui.py::ProgressionWindowUiTests::test_pet_cards_fit_the_same_scroll_viewport_without_losing_information`

Expected: FAIL because the existing fixed 180-pixel action column pushes the pet card past the viewport or because the named compact-row controls do not yet exist.

- [ ] **Step 3: Implement the minimal shared card structure**

In `_pet_card`, add the status badge to `title_row`, place `price_label` and `button` in one bottom `action_row`, name them `petStatus_<pet_id>` and `petAction_<pet_id>`, and remove the separate fixed-width `actions` frame. Keep the preview at its current aspect-preserving size and keep `description.setWordWrap(False)`.

- [ ] **Step 4: Run focused UI tests and verify GREEN**

Run: `python -m pytest -q tests/test_progression_ui.py`

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_progression_ui.py petpet/progression/ui.py
git commit -m "fix: align pet shop cards"
```

### Task 2: Prevent Cross-Pet Outfit Rendering

**Files:**
- Modify: `tests/test_progression.py`
- Modify: `tests/test_pet_window_boundary.py`
- Modify: `petpet/progression/core.py:1041-1049`

**Interfaces:**
- Consumes: `equipped_outfit(state: dict) -> str | None`, `OUTFIT_DEFINITIONS[outfit_id]["pet_id"]`, and `state["active_pet_id"]`.
- Produces: the same lookup returning `None` for an outfit owned by a different pet while leaving `state["equipped_outfit"]` untouched.

- [ ] **Step 1: Write failing cross-pet tests**

Add one core test and one desktop boundary test:

```python
def test_equipped_outfit_is_inactive_for_a_different_selected_pet():
    state = ensure_progression({
        "active_pet_id": "ice_cream",
        "owned_outfits": ["dinosaur_suit"],
        "equipped_outfit": "dinosaur_suit",
    })
    assert equipped_outfit(state) is None
    assert state["equipped_outfit"] == "dinosaur_suit"
    state["active_pet_id"] = "lunch_meat"
    assert equipped_outfit(state) == "dinosaur_suit"
```

```python
def test_drag_preview_does_not_use_an_outfit_from_another_pet(self):
    from petpet.app.pet_window import PetWindow

    window = PetWindow.__new__(PetWindow)
    window.state = {
        "active_pet_id": "ice_cream",
        "owned_outfits": ["dinosaur_suit"],
        "equipped_outfit": "dinosaur_suit",
    }
    window._outfit_preview_cache = {}

    with patch("petpet.app.pet_window.QPixmap") as pixmap:
        self.assertIsNone(window._equipped_outfit_preview())
        pixmap.assert_not_called()
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest -q tests/test_progression.py::test_equipped_outfit_is_inactive_for_a_different_selected_pet tests/test_pet_window_boundary.py::PetWindowBoundaryTests::test_drag_preview_does_not_use_an_outfit_from_another_pet`

Expected: FAIL because the current lookup returns `dinosaur_suit` regardless of `active_pet_id`.

- [ ] **Step 3: Add the ownership guard at the shared lookup**

Update `equipped_outfit` to read the definition and return `None` when its declared `pet_id` differs from `state.get("active_pet_id", "lunch_meat")`. Do not mutate the stored outfit ID.

```python
outfit_id = state["equipped_outfit"]
definition = OUTFIT_DEFINITIONS.get(outfit_id)
if definition and definition.get("pet_id", "lunch_meat") != state.get(
    "active_pet_id", "lunch_meat"
):
    return None
return outfit_id
```

- [ ] **Step 4: Run focused progression and desktop tests**

Run: `python -m pytest -q tests/test_progression.py tests/test_pet_window_boundary.py`

Expected: all focused tests pass and the persisted outfit is restored when switching back.

- [ ] **Step 5: Commit**

```bash
git add tests/test_progression.py tests/test_pet_window_boundary.py petpet/progression/core.py
git commit -m "fix: isolate outfits by active pet"
```

### Task 3: Normalize Home Idle Bounds and Shadow Contact

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `petpet/home/rendering.py:209-214`
- Modify: `petpet/home/window.py:933-959`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/开发记录/2026-08-21 宠物界面与动画一致性修复.md`

**Interfaces:**
- Consumes: `home_pet_static_source_rect(pixmap: QPixmap) -> QRect` and `home_pet_shadow_rect(body: QRectF, contact) -> QRectF`.
- Produces: an alpha-bounded source rectangle with full-canvas fallback, rendered at the existing walk height and anchored to the same world-space feet.

- [ ] **Step 1: Write failing alpha-bound and idle geometry tests**

```python
def test_static_source_rect_crops_transparent_padding(self):
    pixmap = QPixmap(100, 120)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.fillRect(QRect(20, 10, 60, 90), Qt.white)
    painter.end()
    self.assertEqual(home_scene.home_pet_static_source_rect(pixmap), QRect(20, 10, 60, 90))
```

Add a home render-spec assertion that a shared idle pixmap with transparent padding uses the cropped source, produces the same `home_pet_render_rect(...).height()` as a front walk spec, and keeps both rectangles' bottom equal to `home_pet.position[1]`. Assert the resulting shadow center is horizontally aligned with the cropped idle body's contact center and remains above the body bottom.

- [ ] **Step 2: Run the home tests and verify RED**

Run: `python -m pytest -q tests/test_home_scene.py -k "static_source_rect or shared_idle"`

Expected: FAIL because static pixmaps currently return the full transparent canvas.

- [ ] **Step 3: Crop static pixmaps and keep existing foot anchoring**

Use `QRegion(pixmap.mask()).boundingRect()` in `home_pet_static_source_rect`; return the full pixmap rectangle when the mask is empty. Keep `home_pet_draw_rect` as the single height baseline. For shared idle specs, retain centered contact data `(0.5, 0.7, 0.98)` so the now-cropped body and its shadow use the same visible bounds.

- [ ] **Step 4: Run focused and complete verification**

Run: `python -m pytest -q tests/test_home_scene.py tests/test_home_window_boundary.py tests/test_progression_ui.py tests/test_progression.py tests/test_pet_window_boundary.py`

Then run: `python -m pytest -q`

Then run: `python -m compileall -q petpet pet.py tests`

Then run: `git diff --check`

Expected: every command exits 0.

- [ ] **Step 5: Update Obsidian and commit**

Write an Obsidian note with frontmatter, a `> [!success]` verification callout, links to `[[Petpet 总档案]]`, and sections for symptoms, root causes, implementation, tests, and manual checks.

```bash
git add tests/test_home_scene.py petpet/home/rendering.py petpet/home/window.py docs/superpowers/plans/2026-08-21-pet-shop-drag-home-visual-fixes.md
git commit -m "fix: normalize home pet idle rendering"
```

- [ ] **Step 6: Restart the verified main application**

Stop only the running Python process whose command line contains the resolved `D:\Agent_project\Petpet\pet.py`, then launch the same absolute entry point with `pythonw.exe` and `-WindowStyle Hidden`. Verify the new PID remains alive after two seconds.
