# Petpet Chat Mode Selection Implementation Plan

> **For agentic workers:** Implement inline in the current worktree. Follow test-driven development for every behavior change; do not commit, push, reset, checkout, or overwrite unrelated work.

**Goal:** Replace automatic Key-based chat routing with an explicit free/personal choice and safely enlarge the default proxy system prompt.

**Architecture:** `buddy_ai.py` owns persisted mode/model normalization and request budgeting. `pet.py` exposes one mode button and a combined personal API/model dialog. The Cloudflare Worker validates role-specific content limits while retaining the total byte and quota limits.

**Tech Stack:** Python 3, PyQt5, unittest/pytest, Cloudflare Workers JavaScript, Node test runner.

## Global Constraints

- Preserve every existing uncommitted change.
- Use `apply_patch` for manual edits.
- Do not commit, push, publish a release, reset, or checkout.
- Mirror project documentation to the Petpet Obsidian vault.

---

### Task 1: Explicit chat mode state

**Files:** `tests/test_ai_config.py`, `buddy_ai.py`

- [ ] Add failing tests for explicit `default`/`personal` persistence, legacy migration, retaining a saved Key in free mode, and personal mode without a Key.
- [ ] Run the focused tests and verify the failures describe the automatic-routing behavior.
- [ ] Add normalized `chat_mode`, `set_chat_mode()`, and model persistence independent of mode.
- [ ] Run focused tests until green.

### Task 2: Single chat mode control and personal configuration dialog

**Files:** `tests/test_chat_tools.py`, `pet.py`

- [ ] Add failing UI tests for a single mode button, free selection, personal configuration entry, and visual upload visibility.
- [ ] Run the UI tests and verify the old dual-button toolbar fails them.
- [ ] Replace the separate Key/model controls with a single mode menu and add the model selector to the personal API dialog.
- [ ] Ensure sending in personal mode without a Key yields the existing Key-required notice.
- [ ] Run the UI tests until green.

### Task 3: Role-specific proxy limits

**Files:** `tests/test_ai_config.py`, `buddy_ai.py`, `cloudflare-worker/test/index.test.js`, `cloudflare-worker/src/index.js`

- [ ] Add failing Python and Worker tests for 4000-character system content, 1200-character turns, and the 16 KiB UTF-8 payload cap.
- [ ] Run both focused suites and verify boundary failures.
- [ ] Implement role-aware character clipping and total-payload budgeting in the client.
- [ ] Implement role-aware validation in the Worker.
- [ ] Run both focused suites until green.

### Task 4: Documentation, deployment, and verification

**Files:** `README.md`, `cloudflare-worker/README.md`, Obsidian chat notes and Petpet master archive

- [ ] Update user instructions, labels, privacy flow, limits, and deployment contract.
- [ ] Run Worker tests, focused Python tests, full `pytest -q`, syntax checks, `git diff --check`, and a credential-pattern scan.
- [ ] Deploy the Worker, verify the public endpoint without exposing credentials, and restart the current worktree's `pet.py`.
