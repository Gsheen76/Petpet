# 智谱付费聊天模型与充分上下文 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将阿里云默认聊天切换到 `glm-4.7-flashx`，在保持短输出与成本控制的同时，为相关请求提供准确游戏知识、人设和去重后的近期记忆。

**Architecture:** 桌面端负责按需构造人设、长期资料、相关游戏知识和最近对话，并在统一公开契约内裁剪。阿里云和 Cloudflare 使用相同的 32KB/12 消息输入契约；阿里云以低价智谱模型为主，Cloudflare 保持现有故障兜底。游戏知识检索继续是本地确定性关键词匹配，普通陪伴聊天不注入知识。

**Tech Stack:** Python 3、PyQt5、pytest、Node.js 20、node:test、阿里云函数计算、Cloudflare Workers、JSON 游戏知识库、PowerShell ZIP 打包。

## Global Constraints

- 默认模型必须是 `glm-4.7-flashx`，但 `ZHIPU_MODEL` 环境变量优先。
- 请求体最大 32768 字节；系统消息最大 8000 字符；普通消息最大 1600 字符；最多 12 条消息。
- 发送最近 10 条历史消息和当前问题；近期对话不得重复嵌入系统提示词。
- 只有游戏相关问题才检索知识库；普通聊天不得出现 `# 游戏资料`。
- 游戏问题最多注入 5 条相关资料，宽泛介绍问题必须命中游戏概览。
- 最大输出保持 200 Tokens，思考模式保持关闭。
- 不修改个人 `GLM-4.6V-Flash` 图文聊天。
- 不执行 Git commit、push、release 或阿里云部署。

---

### Task 1: 按需游戏知识与准确概览

**Files:**
- Modify: `assets/knowledge/game_knowledge.json`
- Modify: `game_knowledge.py`
- Modify: `tests/test_game_knowledge.py`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Consumes: `game_knowledge.find_relevant_entries(user_text: str, limit: int = 3) -> list[dict]`
- Produces: `game_knowledge.find_relevant_entries(user_text: str, limit: int = 5) -> list[dict]`，其中宽泛游戏问题返回 `game_overview`，无游戏关键词返回空列表。

- [ ] **Step 1: 写知识概览与按需注入失败测试**

在 `tests/test_game_knowledge.py` 增加：

```python
def test_broad_game_question_selects_current_overview():
    entries = game_knowledge.find_relevant_entries("Petpet 是什么游戏，怎么玩？")
    assert entries[0]["id"] == "game_overview"
    assert "桌面" in entries[0]["content"]
    assert "小屋" in entries[0]["content"]
    assert "Pet币" in entries[0]["content"]


def test_daily_companion_chat_does_not_select_game_knowledge():
    assert game_knowledge.find_relevant_entries("今天上班有点累，陪我聊聊") == []
```

在 `tests/test_ai_config.py` 增加：

```python
def test_daily_chat_does_not_inject_game_knowledge(self):
    messages = ai._build_messages("今天有点累", ai._default_memory())
    self.assertNotIn("# 游戏资料", messages[0]["content"])


def test_game_overview_injects_up_to_five_relevant_entries(self):
    messages = ai._build_messages("介绍一下 Petpet 游戏怎么玩", ai._default_memory())
    system = messages[0]["content"]
    self.assertIn("# 游戏资料", system)
    self.assertIn("Petpet 游戏概览", system)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest -q tests/test_game_knowledge.py tests/test_ai_config.py -k "broad_game or daily_companion or daily_chat or game_overview"`

Expected: FAIL，缺少 `game_overview` 或默认 limit 仍为 3。

- [ ] **Step 3: 实现最小知识库更新**

在 `assets/knowledge/game_knowledge.json` 首项增加 `game_overview`，关键词至少包含 `Petpet`、`游戏介绍`、`怎么玩`、`什么游戏`、`功能`；内容只描述当前已发布的桌面陪伴、小屋、互动、属性成长、好感、Pet币、家具装修、小游戏、宝藏、设置和聊天。逐条校准其余条目，移除与当前代码不一致的说明。

在 `game_knowledge.py` 改为：

```python
def find_relevant_entries(user_text: str, limit: int = 5) -> list[dict]:
    ...
```

在 `buddy_ai._build_messages()` 使用：

```python
relevant_entries = game_knowledge.find_relevant_entries(user_text, limit=5)
```

- [ ] **Step 4: 运行知识与提示词测试**

Run: `python -m pytest -q tests/test_game_knowledge.py tests/test_ai_config.py -k "knowledge or game_question or daily_chat or game_overview"`

Expected: PASS。

- [ ] **Step 5: 检查本任务差异，不提交**

Run: `git diff --check -- assets/knowledge/game_knowledge.json game_knowledge.py buddy_ai.py tests/test_game_knowledge.py tests/test_ai_config.py`

Expected: 无 whitespace error；保留未提交改动。

---

### Task 2: 去重并扩充桌面上下文契约

**Files:**
- Modify: `buddy_ai.py`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Consumes: `_build_messages(user_text, mem, pet_name=None, image_attachment=None) -> list[dict]`
- Produces: 同一接口，但系统提示词不含逐句历史，实际消息包含最近 10 条历史；`_default_proxy_stream()` 最多发送 12 条消息。

- [ ] **Step 1: 写上下文预算与去重失败测试**

在 `tests/test_ai_config.py` 更新既有代理限制测试并新增：

```python
def test_persona_does_not_duplicate_recent_history(self):
    memory = ai._default_memory()
    memory["history"] = [
        {"role": "user", "content": "唯一历史问题"},
        {"role": "assistant", "content": "唯一历史回答"},
    ]
    messages = ai._build_messages("继续聊", memory)
    self.assertNotIn("唯一历史问题", messages[0]["content"])
    self.assertEqual(messages[-3]["content"], "唯一历史问题")


def test_default_proxy_keeps_ten_recent_history_messages(self):
    memory = ai._default_memory()
    memory["history"] = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn-{i}"}
        for i in range(14)
    ]
    # 捕获 requests POST payload
    ...
    self.assertEqual(len(body["messages"]), 12)
    self.assertEqual(body["messages"][1]["content"], "turn-4")
```

并把边界预期更新为：系统 8000、普通消息 1600、请求体 32768 字节。

- [ ] **Step 2: 运行代理构造测试并确认失败**

Run: `python -m pytest -q tests/test_ai_config.py -k "default_proxy or persona_does_not_duplicate or ten_recent"`

Expected: FAIL，现有常量仍为 4000/1200/16384，历史最多 6 条且系统提示词重复历史。

- [ ] **Step 3: 实现统一桌面输入预算**

在 `buddy_ai.py` 设置：

```python
DEFAULT_PROXY_MAX_SYSTEM_CHARS = 8000
DEFAULT_PROXY_MAX_TURN_CHARS = 1600
DEFAULT_PROXY_MAX_BODY_BYTES = 32768
DEFAULT_PROXY_MAX_MESSAGES = 12
DEFAULT_PROXY_HISTORY_MESSAGES = 10
```

从 `PERSONA` 删除 `{history}` 段及 `.format(history=...)` 参数；`_build_messages()` 改取 `mem["history"][-10:]`；`_default_proxy_stream()` 使用系统消息加最后 11 条非系统消息，并保证总数不超过 12。`_fit_default_proxy_payload()` 继续优先删除最旧历史，保留系统和当前问题。

- [ ] **Step 4: 运行桌面聊天测试**

Run: `python -m pytest -q tests/test_ai_config.py tests/test_chat_tools.py`

Expected: PASS。

- [ ] **Step 5: 检查本任务差异，不提交**

Run: `git diff --check -- buddy_ai.py tests/test_ai_config.py`

Expected: 无 whitespace error。

---

### Task 3: 阿里云付费模型与安全业务错误码

**Files:**
- Modify: `aliyun-chat/src/server.js`
- Modify: `aliyun-chat/test/server.test.js`
- Modify: `aliyun-chat/.env.example`
- Modify: `aliyun-chat/s.yaml.example`
- Modify: `aliyun-chat/README.md`

**Interfaces:**
- Consumes: `handleRequest(request, { env, fetchImpl, sourceIp, log }) -> Promise<Response>`
- Produces: 相同接口；默认上游模型 `glm-4.7-flashx`；非 200 日志仅增加 `upstreamCode: number | null`。

- [ ] **Step 1: 写阿里云模型、契约和错误码失败测试**

在 `aliyun-chat/test/server.test.js` 更新/新增：

```javascript
test("uses paid GLM-4.7-FlashX with the expanded input contract", async () => {
  const request = validRequest({
    messages: [
      { role: "system", content: "人".repeat(8000) },
      ...Array.from({ length: 11 }, (_, index) => ({
        role: index % 2 ? "assistant" : "user",
        content: `turn-${index}`,
      })),
    ],
  });
  await handleRequest(request, { env: { ZHIPU_API_KEY: "test-only-secret" }, fetchImpl });
  const payload = JSON.parse(fetchImpl.mock.calls[0][1].body);
  assert.equal(payload.model, "glm-4.7-flashx");
  assert.equal(payload.max_tokens, 200);
  assert.deepEqual(payload.thinking, { type: "disabled" });
});


test("logs only numeric Zhipu business code on HTTP failure", async () => {
  const logs = [];
  const fetchImpl = async () => Response.json(
    { error: { code: "1304", message: "private upstream text" } },
    { status: 429 },
  );
  await handleRequest(validRequest(), { env, fetchImpl, log: entry => logs.push(entry) });
  assert.equal(logs.at(-1).upstreamCode, 1304);
  assert.equal(JSON.stringify(logs).includes("private upstream text"), false);
});
```

- [ ] **Step 2: 运行 Node 测试并确认失败**

Run: `npm test --prefix aliyun-chat`

Expected: FAIL，默认模型和请求边界仍为旧值，日志没有 `upstreamCode`。

- [ ] **Step 3: 实现阿里云变更**

设置 `MAX_MESSAGES=12`、`MAX_SYSTEM_CONTENT_CHARS=8000`、`MAX_TURN_CONTENT_CHARS=1600`、`MAX_BODY_BYTES=32768`，并将默认模型改为：

```javascript
model: env.ZHIPU_MODEL || "glm-4.7-flashx",
```

仅在 `!upstream.ok` 时读取错误 JSON，使用有限类型转换提取数值 code，记录：

```javascript
log({
  event: "zhipu_response",
  status: upstream.status,
  upstreamCode,
  elapsedMs: Date.now() - zhipuStarted,
});
```

不要记录 `message`、响应体、请求内容或 Key。同步三个部署示例与 README。

- [ ] **Step 4: 运行阿里云测试**

Run: `npm test --prefix aliyun-chat`

Expected: PASS。

- [ ] **Step 5: 检查本任务差异，不提交**

Run: `git diff --check -- aliyun-chat`

Expected: 无 whitespace error。

---

### Task 4: Cloudflare 统一输入契约

**Files:**
- Modify: `cloudflare-worker/src/index.js`
- Modify: `cloudflare-worker/test/index.test.js`
- Modify: `cloudflare-worker/README.md`

**Interfaces:**
- Consumes: Cloudflare public `/v1/chat` request contract.
- Produces: 与阿里云一致的 32768 字节、8000 系统字符、1600 普通字符、12 消息契约；现有 provider 顺序、模型和额度逻辑不变。

- [ ] **Step 1: 更新 Cloudflare 边界失败测试**

把既有 4000/4001、1200/1201 和 16384 字节测试改为 8000/8001、1600/1601 和 32768 字节，并新增 12 条允许、13 条拒绝的断言。

- [ ] **Step 2: 运行 Worker 测试并确认失败**

Run: `npm test --prefix cloudflare-worker`

Expected: FAIL，Worker 仍使用旧输入契约。

- [ ] **Step 3: 实现常量变更**

在 `cloudflare-worker/src/index.js` 设置：

```javascript
const MAX_MESSAGES = 12;
const MAX_SYSTEM_CONTENT_CHARS = 8000;
const MAX_TURN_CONTENT_CHARS = 1600;
const MAX_BODY_BYTES = 32768;
```

保持 Cloudflare 当前模型池、Durable Object 配额和最大输出 200 不变；同步 README 契约说明。

- [ ] **Step 4: 运行 Worker 测试**

Run: `npm test --prefix cloudflare-worker`

Expected: PASS。

- [ ] **Step 5: 检查本任务差异，不提交**

Run: `git diff --check -- cloudflare-worker`

Expected: 无 whitespace error。

---

### Task 5: 部署包、记录与完整验证

**Files:**
- Replace: `aliyun-chat/dist/petpet-aliyun-chat-root.zip`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/智谱付费模型与充分上下文设计.md`
- Create: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/智谱付费模型与充分上下文实施记录.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/Petpet 总档案.md`

**Interfaces:**
- Consumes: 已验证的 `aliyun-chat/package.json` 与 `aliyun-chat/src/server.js`。
- Produces: 根目录含 `package.json` 和 `src/server.js` 的可上传 ZIP，以及 SHA-256 实施记录。

- [ ] **Step 1: 运行全部 focused tests**

Run:

```powershell
python -m pytest -q tests/test_ai_config.py tests/test_chat_tools.py tests/test_game_knowledge.py
npm test --prefix aliyun-chat
npm test --prefix cloudflare-worker
```

Expected: 全部 PASS。

- [ ] **Step 2: 运行完整 Python 回归**

Run: `python -m pytest -q`

Expected: 全部 PASS。

- [ ] **Step 3: 重建阿里云根目录 ZIP**

仅从已解析且验证位于 `aliyun-chat` 工作区内的 `package.json` 和 `src` 创建临时目录，再用 `Compress-Archive` 覆盖 `aliyun-chat/dist/petpet-aliyun-chat-root.zip`。不得包含 `.env`、Key、测试或旧 ZIP。

- [ ] **Step 4: 验证 ZIP 内容与哈希**

Run:

```powershell
tar -tf aliyun-chat/dist/petpet-aliyun-chat-root.zip
Get-FileHash aliyun-chat/dist/petpet-aliyun-chat-root.zip -Algorithm SHA256
```

Expected: 仅包含 `package.json` 与 `src/server.js`；记录 SHA-256。

- [ ] **Step 5: 更新 Obsidian 实施记录**

记录模型 ID、输入契约、按需知识、错误码日志、focused/full 测试数字、ZIP 路径与 SHA-256；总档案链接实施记录。不得记录 API Key 或用户聊天内容。

- [ ] **Step 6: 最终格式与状态检查**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无 whitespace error；只报告现有未提交改动，不提交、不推送、不部署。
