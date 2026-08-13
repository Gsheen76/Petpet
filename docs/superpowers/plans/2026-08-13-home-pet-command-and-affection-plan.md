# Home Pet Commands and Affection Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move home commands into the header, separate desktop/home autonomy, add passive affection and zero-stat warnings, and improve treasure, speech, and reward behavior.

**Architecture:** Pure balance and notification rules live in `progression.py`; Qt-free home movement scheduling lives in `home_pet.py`; `home_scene.py` and `pet.py` consume those interfaces for presentation. Existing save fields are preserved and new fractional/cooldown state is migrated with defaults.

**Tech Stack:** Python 3.11+, PyQt5, unittest/pytest, existing JSON persistence.

## Global Constraints

- Keep the home canvas at 900×768 and the decoration sidebar at 338×768.
- Preserve existing uncommitted/user data and never reset names, levels, currency, furniture, avatars, settings, or chat memory.
- Home autonomous walks occur only after 12–25 idle seconds.
- Passive affection is 0.01/second and is multiplied by 0.5 for every stat at zero.
- Affection requirements use `min(200, 30 + 10 * (level - 1))`.
- Desktop low-stat reminders use independent ten-minute cooldowns and priority energy, hunger, mood.
- New mini-game and treasure base rewards are doubled; stored pending treasure is unchanged.
- Every production change follows a failing focused test, then focused and full verification.

---

### Task 1: Affection, zero-stat, and reward rule layer

**Files:**
- Modify: `progression.py`
- Modify: `tests/test_progression.py`

**Interfaces:**
- Produces: `passive_affection_per_second(state) -> float`
- Produces: `passive_affection_per_minute(state) -> float`
- Produces: `zero_stat_interaction_actions(state) -> frozenset[str]`
- Updates: `affection_to_next`, `AFFECTION_ACTION_GAINS`, `AFFECTION_ACTION_COOLDOWNS`, `DIG_REWARD_TIERS`

- [ ] Write failing tests asserting rates 0.01, 0.005, 0.0025, 0.00125; threshold sequence 30/40/200; exact action mappings; approved gains/cooldowns; doubled treasure tiers; and migration of `passive_affection_buffer`.
- [ ] Run `python -m pytest tests/test_progression.py -q` and confirm failures are caused by missing/new rule behavior.
- [ ] Implement the constants and pure functions, normalize the buffer to `[0, 1)`, and keep existing `pending_dig_reward` unchanged.
- [ ] Run `python -m pytest tests/test_progression.py -q` and confirm it passes.
- [ ] Commit `progression.py` and `tests/test_progression.py`.

### Task 2: Passive affection tick and property display

**Files:**
- Modify: `pet.py`
- Modify: `tests/test_progression_integration.py`
- Modify: `tests/test_menu_ui.py`

**Interfaces:**
- Consumes: `progression.passive_affection_per_second/minute`
- Produces: `PetWindow.on_passive_growth()` or equivalent single one-second timer callback that accrues both XP and affection without rounding loss.

- [ ] Write failing integration tests for fractional buffering, level rollover with remainder, zero-stat penalty, persistence, and the property panel text containing both `EXP/分钟` and `好感/分钟`.
- [ ] Run the new focused tests and verify the expected failures.
- [ ] Add one-second affection accumulation alongside the current XP timer, save only when whole affection is awarded, and render both current rates in `StatBubble`.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit the passive-growth implementation and tests.

### Task 3: Desktop autonomy and spoken reminders

**Files:**
- Modify: `pet.py`
- Modify: `tests/test_progression_integration.py`
- Modify: `tests/test_menu_ui.py`

**Interfaces:**
- Produces: reminder selection returning `energy`, `hunger`, `mood`, or `None`
- Persists: per-stat reminder timestamps under a normalized state mapping

- [ ] Write failing tests proving desktop autonomy never selects `walk`, low-stat clickable feed/play bubbles are not created, reminder priority is energy/hunger/mood, each stat has a 600-second cooldown, and treasure visibility suppresses reminders/proactive speech.
- [ ] Run the focused tests and verify the failures.
- [ ] Remove `walk` from desktop random autonomy, replace `maybe_show_interactive_bubble` with spoken reminder selection, and suppress ordinary speech while a treasure bubble is active.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit the desktop behavior changes and tests.

### Task 4: Home autonomous movement controller

**Files:**
- Modify: `home_pet.py`
- Modify: `home_scene.py`
- Modify: `tests/test_home_pet.py`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Produces: deterministic idle deadline helpers using injected `now` and RNG
- Consumes: existing `HomePetController.command_move`, sleep requests, and walkable clamping

- [ ] Write failing tests for a 12–25 second deadline, no autonomous move during manual movement/sleep/decoration, valid random floor targets, and rescheduling after arrival or direct user input.
- [ ] Run the home focused tests and verify expected failures.
- [ ] Add scheduling state to the controller/window, inject random targets through `clamp_to_walkable`, and record completed autonomous walks without disturbing manual route footprints.
- [ ] Run the home focused tests and confirm they pass.
- [ ] Commit the home autonomy implementation and tests.

### Task 5: Home header commands, dropdown, and red dots

**Files:**
- Modify: `home_scene.py`
- Modify: `pet.py`
- Modify: `tests/test_home_scene.py`
- Modify: `tests/test_menu_ui.py`

**Interfaces:**
- Consumes: `progression.zero_stat_interaction_actions(state)`
- Reuses: existing property, shop, petting, feeding, play, and sleep callbacks

- [ ] Write failing UI tests for exact header order, dropdown actions, dropdown dismissal, right-click no-op, callbacks to existing windows/actions, and red-dot visibility on pet/header/action items.
- [ ] Run focused UI tests and verify failures.
- [ ] Implement warm rounded header buttons and an in-window dropdown, remove `open_home_pet_menu`, connect shared actions, and paint/refresh red dots from pure rule output.
- [ ] Run focused UI tests and confirm they pass.
- [ ] Commit the header/dropdown implementation and tests.

### Task 6: Circular treasure bubble and dynamic speech pointer

**Files:**
- Modify: `pet.py`
- Modify: `tests/test_menu_ui.py`
- Modify: `tests/test_speech_bubble.py`

**Interfaces:**
- Produces: treasure bubble visibility methods that distinguish temporary menu hiding from reward removal
- Produces: speech-tail geometry based on bubble rectangle and current pet head-center anchor

- [ ] Write failing tests for circular treasure geometry above the pet, right-menu hide/restore, speech suppression while treasure is visible, and tail X clamping that points toward pets at both screen edges.
- [ ] Run the focused bubble tests and verify failures.
- [ ] Add the circular treasure widget/state, hook menu open/close, make `say()` respect treasure priority, and calculate the tail from the current global pet anchor in `follow_pet`/paint.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit bubble behavior and tests.

### Task 7: Double mini-game rewards and finish documentation

**Files:**
- Modify: `minigames.py`
- Modify: `tests/test_minigames.py`
- Modify: `README.md` if user-visible behavior is summarized there
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\小屋宠物功能分流与好感成长设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

**Interfaces:**
- Updates: Coin Catch hit values 2/4 and Lucky Paws round values 10/20/30

- [ ] Write failing tests for exact Coin Catch and Lucky Paws doubled values and unchanged settlement accounting.
- [ ] Run `python -m pytest tests/test_minigames.py tests/test_progression.py -q` and verify failures.
- [ ] Update visible values and settlement inputs once, avoiding a second multiplier in `award_minigame_coins`.
- [ ] Run all affected focused tests: progression, home pet/scene, menus, speech bubbles, and mini-games.
- [ ] Run `python -m pytest -q`, `python -m py_compile` for tracked Python files, and `git diff --check`.
- [ ] Update Obsidian with implemented behavior, final test counts, and remaining visual/manual verification notes.
- [ ] Commit the final implementation/docs without publishing a new version.
