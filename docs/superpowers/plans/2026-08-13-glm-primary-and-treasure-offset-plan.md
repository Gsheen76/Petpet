# GLM Primary and Treasure Offset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GLM-4.7-Flash the fast primary free-chat provider and move the treasure badge 20px upward.

**Architecture:** Reuse the Worker's existing first-content stream gate, applying it to GLM before a one-way OpenRouter fallback. Keep treasure geometry inside the existing desktop bubble positioning method.

**Tech Stack:** JavaScript Cloudflare Worker, Node test runner, Python, PyQt5, pytest.

## Global Constraints

- Preserve all unrelated uncommitted changes.
- Do not commit, push, or publish a desktop release.
- The provider first-content timeout is exactly 5000ms.
- Do not log prompts, replies, or API keys.

---

### Task 1: Reverse the free-chat provider order

**Files:**
- Modify: `cloudflare-worker/src/index.js`
- Test: `cloudflare-worker/test/index.test.js`

**Interfaces:**
- Consumes: `requestProvider(url, apiKey, payload, firstContentTimeoutMs)`
- Produces: GLM-first response stream with OpenRouter fallback

- [ ] Write tests asserting GLM is first and that GLM failure or missing timely content calls OpenRouter second.
- [ ] Run the focused Node tests and confirm they fail because the current order is OpenRouter-first.
- [ ] Reverse the provider construction while preserving GLM and OpenRouter request parameters.
- [ ] Run the Worker test suite and confirm all tests pass.

### Task 2: Move the treasure badge upward

**Files:**
- Modify: `pet.py`
- Test: `tests/test_dig_reward.py`

**Interfaces:**
- Consumes: desktop pet geometry from `InteractiveBubble.pet.geometry()`
- Produces: treasure bubble bottom positioned 22px above the pet top

- [ ] Change the geometry assertion to require the extra 20px gap and confirm it fails.
- [ ] Adjust only the treasure bubble vertical offset.
- [ ] Run `tests/test_dig_reward.py` and confirm it passes.

### Task 3: Deploy and verify

**Files:**
- Modify: Obsidian chat implementation record and `Petpet 总档案.md`

**Interfaces:**
- Consumes: tested Worker and desktop code
- Produces: deployed Worker, online timing evidence, current maintenance notes

- [ ] Deploy with `npx.cmd wrangler deploy`.
- [ ] Send a fixed no-private-content request and record actual model/provider and timings.
- [ ] Run `python -m pytest -q`, Worker tests, and `git diff --check`.
- [ ] Update Obsidian with the final provider order, timeout, treasure offset, deployment ID, and verification counts.
