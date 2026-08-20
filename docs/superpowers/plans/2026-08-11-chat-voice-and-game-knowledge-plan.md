# 小狗聊天台词与游戏知识库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present clean, natural dog dialogue and answer current Petpet gameplay questions from a versioned local knowledge base.

**Architecture:** A new pure `game_knowledge.py` module reads and validates a bundled JSON file, scores keyword matches and returns at most three relevant player-facing entries. `buddy_ai.py` injects those entries into the system prompt and exposes a single reply-cleaning function; `ChatWindow` applies that cleaner to assistant rendering, history writes and speech bubbles.

**Tech Stack:** Python standard library (`json`, `re`, `pathlib`), existing PyQt5 UI, unittest, pytest.

## Global Constraints

- Preserve all existing user changes; never use git reset or checkout.
- Use the current worktree's `pet.py` for manual launch.
- Assistant bubbles and title contain no automatic dog emoji; the user will provide a future avatar separately.
- Remove paired Chinese and ASCII parenthetical action text from new assistant replies; do not alter user messages or already-saved history.
- Bundle `assets/knowledge/game_knowledge.json`; do not make network requests or read Obsidian notes at runtime.
- The knowledge `version` is exactly `VERSION` from `version.py`; entries contain only player-facing released features.
- Inject at most three matched entries per request; unmatched casual chat receives no game-material prompt.
- Manual edits use `apply_patch`; write matching records under `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/`.
- Do not commit, push or release unless the user explicitly asks.

---

### Task 1: Bundled versioned knowledge module

**Files:**
- Create: `assets/knowledge/game_knowledge.json`
- Create: `game_knowledge.py`
- Create: `tests/test_game_knowledge.py`

**Interfaces:**
- Produces: `load_game_knowledge() -> list[dict]`.
- Produces: `find_relevant_entries(user_text: str, limit: int = 3) -> list[dict]`.
- Consumes: `app_paths.ASSETS_DIR`, `version.VERSION` and `assets/knowledge/game_knowledge.json`.

- [ ] **Step 1: Write the failing knowledge tests**

```python
def test_knowledge_file_is_current_and_player_facing(self):
    entries = knowledge.load_game_knowledge()
    self.assertEqual(knowledge.knowledge_version(), VERSION)
    self.assertGreaterEqual(len(entries), 6)
    self.assertTrue(all(
        entry["id"] and entry["title"] and entry["keywords"] and entry["content"]
        for entry in entries
    ))

def test_game_questions_select_only_relevant_entries(self):
    matches = knowledge.find_relevant_entries("小屋里怎么装修家具？")
    self.assertEqual(matches[0]["id"], "home_and_decoration")
    self.assertLessEqual(len(matches), 3)
    self.assertEqual(knowledge.find_relevant_entries("今天有点累"), [])
```

- [ ] **Step 2: Run the RED test**

Run: `python -m pytest tests/test_game_knowledge.py -q`

Expected: FAIL because the module and bundled file do not exist.

- [ ] **Step 3: Implement the data and matching boundary**

Create a JSON object with `version: "1.4.0"` and exactly these initial entry identifiers: `basic_interactions`, `quick_menu`, `home_and_decoration`, `growth_and_coins`, `mini_games`, `chat_and_images`. Each entry has concise, released-feature-only content and two or more Chinese keywords. Implement strict validation: non-object data, an unequal version, malformed entries or an empty `entries` list returns an empty list rather than crashing chat. Score a message by the number of distinct `keywords` that occur in `user_text.casefold()`, order by descending score then original file order, and return the requested positive limit.

```python
def find_relevant_entries(user_text, limit=3):
    text = str(user_text or "").casefold()
    ranked = []
    for index, entry in enumerate(load_game_knowledge()):
        score = sum(keyword.casefold() in text for keyword in entry["keywords"])
        if score:
            ranked.append((-score, index, entry))
    return [item[2] for item in sorted(ranked)[:max(0, int(limit))]]
```

- [ ] **Step 4: Run the GREEN test**

Run: `python -m pytest tests/test_game_knowledge.py -q`

Expected: PASS.

### Task 2: Persona constraints, knowledge injection and reply cleanup

**Files:**
- Modify: `buddy_ai.py:68-100, _build_messages(), fallback_reply()`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Consumes: `game_knowledge.find_relevant_entries(user_text)`.
- Produces: `clean_assistant_reply(text: str) -> str`.
- Produces: `_build_messages(...)[0]["content"]` containing `# 游戏资料` only when relevant entries exist.

- [ ] **Step 1: Write failing prompt and cleanup tests**

```python
def test_reply_cleaner_removes_parenthetical_actions_but_keeps_dialogue(self):
    reply = ai.clean_assistant_reply("我在呀（摇摇尾巴）！(凑近一点)你想聊什么？")
    self.assertEqual(reply, "我在呀！你想聊什么？")

def test_game_question_injects_matched_knowledge_only(self):
    with patch.object(ai.game_knowledge, "find_relevant_entries", return_value=[{
        "title": "小屋与家具", "content": "进入小屋后可装修家具。"
    }]):
        system = ai._build_messages("怎么装修家具", ai._default_memory())[0]["content"]
    self.assertIn("# 游戏资料", system)
    self.assertIn("进入小屋后可装修家具", system)
```

- [ ] **Step 2: Run the RED test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: FAIL because no cleaner or knowledge-injection boundary exists.

- [ ] **Step 3: Implement narrow assistant-only transformations**

Import `game_knowledge`; add persona rules forbidding parenthetical actions and instructing the dog to use injected player material accurately. `clean_assistant_reply` repeatedly removes `（[^（）]*）` and `\([^()]*\)`, removes unmatched bracket characters, collapses excess inline whitespace and returns a stripped string. Format selected entries as `- <title>：<content>` under a system-prompt `# 游戏资料` heading. Do not add material for no-match messages and do not pass it through `memory.json`.

- [ ] **Step 4: Run the GREEN test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: PASS.

### Task 3: Assistant-only chat UI rendering

**Files:**
- Modify: `pet.py:ChatWindow.__init__(), refresh_pet_name(), _set_log_messages(), on_token(), on_done(), on_error()`
- Modify: `tests/test_chat_tools.py`

**Interfaces:**
- Consumes: `ai.clean_assistant_reply(text)`.
- Produces: assistant `QLabel#chatMessage` text without a `🐶` prefix or parenthetical action text.

- [ ] **Step 1: Write failing UI tests**

```python
def test_assistant_bubble_uses_clean_text_without_dog_emoji(self):
    self.window._set_log_messages([("assistant", "你好（摇尾巴）")])
    bubble = self.window.findChild(QLabel, "chatMessage")
    self.assertEqual(bubble.text(), "你好")

def test_chat_title_uses_only_pet_name(self):
    self.assertEqual(self.window.title.text().strip(), "summer")
```

- [ ] **Step 2: Run the RED test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: FAIL because assistant labels currently prepend `🐶`, retain parenthetical text and the title includes an emoji.

- [ ] **Step 3: Implement UI-only application points**

Keep user bubbles unchanged. Use `ai.clean_assistant_reply` when building assistant labels and when rendering streaming text. In `on_done` and `on_error`, clean the final reply before saving it, rendering it and passing it to `self.pet.say`; if cleaning produces an empty string, use `"我在呢，你再和我说一点吧。"`. Change title construction and `refresh_pet_name()` to `f"  {name}"`.

- [ ] **Step 4: Run the GREEN test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: PASS.

### Task 4: Player documentation, Obsidian maintenance and full verification

**Files:**
- Modify: `README.md:135-157`
- Modify: `docs/superpowers/specs/2026-08-11-chat-voice-and-game-knowledge-design.md`
- Modify: `docs/superpowers/plans/2026-08-11-chat-voice-and-game-knowledge-plan.md`
- Create/Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/小狗聊天台词与游戏知识库实施计划.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/Petpet 总档案.md`

**Interfaces:**
- Consumes: complete knowledge file, prompt injection and UI rendering behaviour.
- Produces: player-facing information on asking the dog about game features and a documented version-maintenance rule.

- [ ] **Step 1: Review player documentation requirements**

Confirm README says the dog can answer current game-feature questions locally, the content ships with the version, and no network/Obsidian notes are required. Do not add source-text assertions: prose checks are change detectors rather than product-behaviour tests.

- [ ] **Step 2: Update records and README**

Document the initial topics and maintenance process: update `game_knowledge.json` and its version whenever a player-visible feature changes. Mirror the final plan/results in Obsidian with frontmatter, link the design note, and update the total archive’s AI-chat section.

- [ ] **Step 3: Run full verification**

Run:

```powershell
python -m pytest tests/test_game_knowledge.py tests/test_ai_config.py tests/test_chat_tools.py -q
python -m pytest -q
python -m py_compile game_knowledge.py buddy_ai.py pet.py
git diff --check
```

Expected: every command exits `0`.

## Self-Review

- Tasks 1–3 cover the data boundary, targeted prompt injection, model constraints, complete UI presentation and persistent reply cleanup; Task 4 covers player documentation and Obsidian synchronization.
- All functions consumed across tasks use identical names and signatures; no entry reads runtime notes or remote state.
- The plan contains no placeholders and stays within released player-facing knowledge, local files and the existing PyQt/chat architecture.

## Implementation Record

- 2026-08-11: Task 1 added the validated JSON boundary and package entries for Windows/macOS.
- 2026-08-11: Task 2 added precise knowledge injection plus reply cleanup; Task 3 applied it only to assistant UI/history/speech output.
- 2026-08-11: Task 4 updated player-facing documentation and the matching Obsidian records. Verification commands are recorded with this implementation run.
