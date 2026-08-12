# Petpet Rounded Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the verbose chat-mode menu with the confirmed rounded `免费｜自定义` segmented control and simplify the chat window’s visual hierarchy and player-facing copy.

**Architecture:** Keep all network, config, memory, and attachment behavior intact. Refactor only `ChatWindow`: two checkable buttons render the mode selector, one centralized refresh method controls mode/tool visibility and enabled state, and existing dialogs/actions remain the implementation behind compact icon buttons.

**Tech Stack:** Python 3, PyQt5 widgets/QSS, unittest/pytest.

## Global Constraints

- Modify only the current worktree; preserve all existing uncommitted changes.
- Do not use `git reset` or `git checkout`, and do not commit or push.
- Write failing tests before implementation.
- Use warm rounded UI; no blue highlight and no decorative emoji in button text.
- Keep `default` / `personal` config values and all existing chat transport behavior unchanged.
- Run focused tests and complete `pytest -q`, then launch this worktree’s `pet.py` for visual verification.
- Sync the implementation result to Obsidian and `Petpet 总档案.md`.

---

### Task 1: Segmented mode selector and conditional tools

**Files:**
- Modify: `tests/test_chat_tools.py`
- Modify: `pet.py:563-930`

**Interfaces:**
- Consumes: `ai.get_chat_mode()`, `ai.get_api_key_source()`, `ai.is_vision_model()`, `ChatWindow.configure_api_key()`.
- Produces: `ChatWindow.free_mode_btn`, `ChatWindow.personal_mode_btn`, `ChatWindow.model_btn`, `ChatWindow.settings_btn`, and `_refresh_ai_tool_buttons()` state synchronization.

- [ ] **Step 1: Write failing tests**

Add tests asserting that both `免费` and `自定义` buttons exist, only the active mode is checked, free mode hides model/image/settings, personal mode shows model/settings and shows image only for the visual model, and selecting personal without a Key calls configuration without changing mode when cancelled.

- [ ] **Step 2: Run the new focused tests and confirm failure**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: FAIL because the segmented widgets do not exist and the old menu button remains.

- [ ] **Step 3: Implement the segmented controls**

Create two checkable buttons in an exclusive `QButtonGroup`, connect them to `select_chat_mode("default")` and `select_chat_mode("personal")`, and replace the old popup menu. Add compact `GLM-4.6V`, upload, API settings, and clear-memory controls. Make `_refresh_ai_tool_buttons()` the single place that updates checked state, visibility, labels, tooltips, and busy-state enablement.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: PASS.

### Task 2: Rounded visual hierarchy and concise notices

**Files:**
- Modify: `tests/test_chat_tools.py`
- Modify: `pet.py:595-820`
- Modify: `pet.py:1380-1465`

**Interfaces:**
- Consumes: the Task 1 widget object names and `_refresh_ai_tool_buttons()`.
- Produces: rounded QSS tokens and concise notice strings.

- [ ] **Step 1: Write failing tests**

Add assertions for the 24px chat surface, 18px message bubbles/panels, 15px composer controls, circular compact tools, and exact concise quota/provider notices.

- [ ] **Step 2: Run tests and confirm failure**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: FAIL on old radii and verbose notice text.

- [ ] **Step 3: Apply the confirmed visual design**

Update QSS and native message-label styles to the warm rounded hierarchy, remove decorative emoji from control text, shorten placeholders where needed, and map free-provider errors to `今日免费次数已用完，可切换自定义。` and `免费聊天暂不可用，请稍后再试。` Disable the mode selector while a request is active and restore it in both success/error completion paths.

- [ ] **Step 4: Run focused chat tests**

Run: `python -m pytest tests/test_chat_tools.py tests/test_ai_config.py -q`

Expected: PASS.

### Task 3: Regression, visual verification, and records

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\聊天系统\圆角精简聊天界面设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

**Interfaces:**
- Consumes: completed UI and passing focused tests.
- Produces: verified implementation record and current project archive entry.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest -q`

Expected: all tests pass; compare the new total with the previous 350-test baseline.

- [ ] **Step 2: Start the current worktree source and capture the chat window**

Start `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py`, open chat through the pet’s right-click menu, and capture free and personal toolbar states. Verify no clipping at the configured narrow width, all surfaces are rounded, and only relevant tools are visible.

- [ ] **Step 3: Update Obsidian records**

Append the exact implementation behavior, verification commands/results, and any visual limitations to `圆角精简聊天界面设计.md`; append a concise status entry to `Petpet 总档案.md`.

- [ ] **Step 4: Inspect final Git status**

Run: `git status --short`

Expected: only preserved user changes plus this task’s intended changes; no secrets, generated diagnostics, or commits.
