# Shop Card Visual Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the first-purchase discount only for pets while giving pet cards, outfit filters, and the ice-cream empty state the same framed visual language as the rest of the shop.

**Architecture:** Narrow the existing first-purchase pricing helper to the `pets` category and restore direct definition prices for outfits and home furniture. Reuse the current Qt card and tab QSS through object names and dynamic properties; keep the existing shop classes and data flow.

**Tech Stack:** Python 3.11, PyQt5, pytest.

## Global Constraints

- Only the pets category has a first-purchase 76% price.
- Existing `outfits` and `home` discount flags in old saves are ignored without destructive migration.
- Pet discount markup uses a separate small `-24%` bubble at the upper right of the pet card.
- Outfit and furniture purchases display and charge their definition prices.
- The outfit pet selector has a framed container and distinct checked and unchecked colors.
- Ice cream has no fake outfit product; its page shows a framed preparation card.
- Do not change version, release metadata, pet assets, or outfit assets.

---

### Task 1: Restore Outfit and Furniture Prices

**Files:**
- Modify: `tests/test_progression.py`
- Modify: `petpet/progression/core.py`

**Interfaces:**
- Consumes: `first_purchase_price(state, category, original_price) -> dict`
- Produces: pet-only discount state; `purchase_outfit` and `purchase_home_decoration` return definition prices.

- [ ] **Step 1: Write failing economic tests**

Replace the independent-category discount assertions with:

```python
def test_first_purchase_discount_only_applies_to_pets():
    state = fresh_state(pet_coins=2000)
    assert progression.purchase_pet(state, "ice_cream")["price"] == 760
    assert progression.purchase_outfit(state, "dinosaur_suit")["price"] == 680
    assert progression.purchase_home_decoration(state, "home_sofa")["price"] == 240
    assert state["pet_coins"] == 320


def test_old_outfit_and_home_discount_flags_are_ignored():
    state = fresh_state(
        pet_coins=1000,
        shop_first_purchase_discounts={
            "pets": True,
            "outfits": True,
            "home": True,
        },
    )
    assert progression.purchase_outfit(state, "dinosaur_suit")["price"] == 680
    assert progression.purchase_home_decoration(state, "home_rug")["price"] == 120
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q tests/test_progression.py -k "first_purchase or discount_flags"
```

Expected: FAIL because outfits and furniture still receive the 76% discount.

- [ ] **Step 3: Implement pet-only pricing**

Set `FIRST_PURCHASE_CATEGORIES = ("pets",)`. In `purchase_outfit` and `purchase_home_decoration`, use `int(definition.get("price", 0))` directly, remove discount consumption, and return only the normal `price` metadata used by existing callers.

- [ ] **Step 4: Run progression tests**

Run:

```powershell
python -m pytest -q tests/test_progression.py
```

Expected: PASS.

### Task 2: Frame Pet Cards and Refine Discount Badge

**Files:**
- Modify: `tests/test_progression_ui_boundary.py`
- Modify: `petpet/progression/ui.py`

**Interfaces:**
- Consumes: `ShopWindow._pet_card(pet_id) -> QFrame`
- Produces: pet cards with `shopCard=true`; `discountBadge_ice_cream` as a separate small label in the right action column.

- [ ] **Step 1: Write failing pet-card tests**

Add assertions that both pet cards expose the shared framed-card property, that the ice-cream badge text is `-24%`, its font is smaller than the discounted price, and its layout position is above the status and purchase controls. Assert that outfit and home pages contain no discount badge labels.

- [ ] **Step 2: Run the pet-card tests and verify red**

Run:

```powershell
python -m pytest -q tests/test_progression_ui_boundary.py -k "pet_card or discount_badge or no_discount"
```

Expected: FAIL because pet cards are unstyled and the discount badge is still in the price row.

- [ ] **Step 3: Reuse card QSS and create the right action column**

Extend the existing card selector with `QFrame[shopCard="true"]`. Set that property on each dynamic pet card. Keep original and discounted prices in the left price row; place the discount badge, ownership badge, and button in a right-aligned vertical layout. Add one QSS selector for labels with `discountBubble=true`, using a small bold font, warm coral foreground, pale peach background, padding, and rounded corners.

- [ ] **Step 4: Restore outfit and home UI prices**

Remove `_price_labels` calls from outfit and home cards. Use their definition price for the label, button text, and balance check. Keep `_price_labels` only for eligible pet cards.

- [ ] **Step 5: Run focused UI tests**

Run:

```powershell
python -m pytest -q tests/test_progression_ui_boundary.py
```

Expected: PASS.

### Task 3: Frame the Outfit Selector and Ice-Cream Empty State

**Files:**
- Modify: `tests/test_progression_ui_boundary.py`
- Modify: `petpet/progression/ui.py`

**Interfaces:**
- Produces: `outfitPetSelector` frame; checkable `outfitPet_<pet_id>` buttons with `outfitPetTab=true`; `outfitEmptyCard` placeholder frame.

- [ ] **Step 1: Write failing selector and empty-card tests**

Assert that the selector frame exists, lunch meat begins checked, ice cream begins unchecked, clicking ice cream swaps the states, and the ice-cream page contains `outfitEmptyCard` with title `冰淇淋套装正在准备` plus the existing preparation note.

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest -q tests/test_progression_ui_boundary.py -k "outfit_selector or ice_cream_empty"
```

Expected: FAIL because the selector has no frame styling and the empty state is a plain label.

- [ ] **Step 3: Implement the shared visual treatment**

Set the selector frame object name to `outfitPetSelector` and reuse the category-tab frame colors. Keep each button's unique object name and style it through `outfitPetTab=true`, with transparent brown unchecked state, pale peach hover, and coral/white checked state. Replace the empty label with a `placeholderCard`-styled frame named `outfitEmptyCard`, containing the specified title and note.

- [ ] **Step 4: Run focused and full verification**

Run:

```powershell
python -m pytest -q tests/test_progression.py tests/test_progression_ui_boundary.py tests/test_desktop_surfaces_boundary.py tests/test_home_window_boundary.py tests/test_chat_window_boundary.py
python -m pytest -q
python -m compileall -q petpet pet.py tests
git diff --check
```

Expected: all tests and static checks pass.
