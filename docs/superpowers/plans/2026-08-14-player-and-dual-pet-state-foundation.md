# Player and Dual-Pet State Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an idempotent persisted schema containing shared player progress and two independent pet profiles without breaking code that still reads legacy top-level fields.

**Architecture:** `petpet.app.state` owns pure migration and compatibility synchronization functions. During the transition, top-level player and pet fields remain the active facade for existing desktop code; loading hydrates that facade from `player` and `pets.desktop`, while saving captures it back without touching `pets.home`.

**Tech Stack:** Python 3.11, standard-library `copy`, unittest/pytest, existing JSON save pipeline.

## Global Constraints

- Desktop and home are independent pets with separate name, needs, affection, cooldowns, sleeping/location state, and equipped appearance.
- Player level, XP, Pet coins, achievements, owned inventory, upgrades, home decoration state, tutorial state, and lifetime records are shared.
- Existing single-pet data is deep-copied into both pet profiles exactly once.
- Migration is idempotent and must never overwrite a newer home profile.
- Root `pet.py` and top-level state fields remain compatible during later incremental extraction.
- No new dependency, version change, commit, push, tag, or release.
- Use failing tests first, then focused and full regression tests.

---

### Task 1: Add pure schema migration and compatibility synchronization

**Files:**
- Create: `petpet/app/state.py`
- Create: `tests/test_app_state.py`

**Interfaces:**
- Produces: `ensure_state_schema(state: dict, default_pet_name: str, normalize_pet_name: Callable[[object], str]) -> dict`.
- Produces: `prepare_state_for_save(state: dict) -> dict`.
- Produces: `STATE_SCHEMA_VERSION`, `PLAYER_FIELDS`, and `PET_FIELDS`.

- [x] **Step 1: Write failing tests for first migration, idempotence, and save synchronization**

Tests must prove that nested dictionaries are deep copies, changing `pets.home` survives later calls, and top-level changes update only `player` plus `pets.desktop` during save preparation.

- [x] **Step 2: Run the focused tests and verify import failure**

Run: `python -m pytest tests/test_app_state.py -q`

Expected: collection FAILS because `petpet.app.state` does not exist.

- [x] **Step 3: Implement the minimum pure functions**

Use `copy.deepcopy` for every field crossing the compatibility boundary. Detect first migration by the absence of valid `player`/`pets.desktop`/`pets.home` dictionaries, set `state_schema_version`, and hydrate legacy top-level fields from the canonical nested data.

- [x] **Step 4: Run focused schema tests**

Run: `python -m pytest tests/test_app_state.py -q`

Expected: all tests PASS.

### Task 2: Connect the schema to the existing save pipeline

**Files:**
- Modify: `pet.py`
- Create: `tests/test_pet_state_io.py`

**Interfaces:**
- Consumes: `ensure_state_schema` after `progression.ensure_progression`.
- Consumes: `prepare_state_for_save` immediately before JSON serialization.
- Preserves: `load_state() -> dict` and `save_state(state) -> None`.

- [x] **Step 1: Add a failing integration test**

Patch `pet.SAVE_PATH` to a temporary legacy JSON save, call `load_state()`, mutate the top-level desktop name and the nested home name, call `save_state()`, and assert the written file contains the shared player plus both distinct pet names.

- [x] **Step 2: Run the integration test and verify nested schema is missing**

Run: `python -m pytest tests/test_pet_state_io.py -q`

Expected: FAIL because `load_state()` does not create `player` and `pets`.

- [x] **Step 3: Wire migration and preparation into `pet.py`**

Import `petpet.app.state` as `app_state`; normalize progression first, then call `app_state.ensure_state_schema`. Call `app_state.prepare_state_for_save` before `json.dump`.

- [x] **Step 4: Run state and progression focused tests**

Run: `python -m pytest tests/test_app_state.py tests/test_pet_state_io.py tests/test_progression.py tests/test_progression_integration.py -q`

Expected: all tests PASS.

### Task 3: Verify and record the foundation

**Files:**
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/工程结构/项目代码与资源结构重构实施记录.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/Petpet 总档案.md`

- [x] **Step 1: Run `python -m pytest -q`**

Expected: the v1.5.0 baseline, the path-boundary test, and all new state tests PASS.

- [x] **Step 2: Run current-worktree source startup smoke**

Start the current worktree's `pet.py`, verify it remains alive for four seconds, then stop only that smoke process.

- [x] **Step 3: Run `git diff --check` and inspect `git status --short`**

Expected: no whitespace errors and no version/release changes.

- [x] **Step 4: Synchronize Obsidian**

Record the exact schema boundary and tests. State clearly that the nested foundation is active while the home UI will begin consuming `pets.home` in its later extraction slice.
