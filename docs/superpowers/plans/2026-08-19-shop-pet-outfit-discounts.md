# Shop Pet, Outfit, and Furniture Discounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Unify shop presentation while adding independent first-purchase 24% discounts, pet nickname labels, and pet-specific outfit filtering.

**Architecture:** Keep discount ownership in shared progression state, with one consumed flag per shop category (`pets`, `outfits`, `home`). Centralize display pricing in small helpers used by the existing shop cards. Store outfit pet ownership in definitions and filter the existing outfit catalog without changing outfit save format.

**Tech Stack:** Python 3.11, PyQt5, JSON state, pytest.

## Global Constraints

- First successful purchase in each of pets, outfits, and furniture is discounted to 76% and consumes only that category's privilege.
- The UI shows original price struck through, discounted price, and a `-24%` badge for an eligible first purchase.
- Pet cards show a player nickname followed by the registered default name in parentheses only when the nickname differs.
- Existing outfits belong to `lunch_meat`; the `ice_cream` outfit filter is present but empty.
- Existing purchases and saves remain backward compatible; missing discount flags mean unused privileges.

### Task 1: Discount state and pricing helpers

**Files:**
- Modify: `petpet/progression/core.py`
- Test: `tests/test_progression.py`

- [ ] Add failing tests for independent first-purchase discount calculation and consumption across pet, outfit, and home purchases.
- [ ] Run the focused tests and confirm failure.
- [ ] Add normalized shared flags plus helpers that return original price, effective price, discount percentage, and consume exactly one category flag on successful purchase.
- [ ] Update `purchase_pet`, `purchase_outfit`, and `purchase_home_decoration` to use the category helper while preserving existing result fields.
- [ ] Run progression tests and confirm all pass.

### Task 2: Unified pet cards and outfit pet filter

**Files:**
- Modify: `petpet/progression/core.py`
- Modify: `petpet/progression/ui.py`
- Test: `tests/test_progression_ui_boundary.py`

- [ ] Add failing UI tests for original/discounted prices, `-24%`, nickname formatting, and outfit pet tabs with an empty ice-cream state.
- [ ] Run those tests and confirm failure.
- [ ] Add `pet_id: "lunch_meat"` to the two existing outfit definitions, add the filter control, and render only matching outfits.
- [ ] Render pet names as `昵称（默认名）` only when distinct; render original struck-through price, effective price, and discount badge for eligible purchases.
- [ ] Apply the same price presentation to outfit and furniture cards.
- [ ] Run progression UI tests and related shop regressions.

### Task 3: Regression verification and records

**Files:**
- Modify: `tests/test_release_metadata.py` only if needed for stable player-facing copy.
- Verify: `README.md`, `assets/runtime/knowledge/game_knowledge.json`.

- [ ] Run the focused shop/progression suite, full pytest suite, compileall, and diff check.
- [ ] Verify no internal state field names leak into player-facing copy.
- [ ] Record exact test counts and any GUI limitation in the existing local report; do not change version or release metadata.
