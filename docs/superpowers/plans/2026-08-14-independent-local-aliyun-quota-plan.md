# 阿里云本地额度与 Cloudflare 独立额度实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让阿里云线路在桌面客户端本地独立计算每天 20 次额度，并彻底移除阿里云到 Cloudflare 的额度请求。

**Architecture:** `buddy_ai.py` 在 `DATA_DIR/chat_quota_state.json` 中维护北京时间自然日的阿里云成功请求计数；达到 20 次后跳过阿里云并直接尝试 Cloudflare。阿里云函数只校验请求并调用 `glm-4.7-flash`，Cloudflare Worker 保持现有 Durable Object 独立 20 次额度。

**Tech Stack:** Python 3、requests、JSON 原子文件写入、Node.js 20 Web Function、Cloudflare Worker、unittest/pytest、Node test runner。

## Global Constraints

- 阿里云与 Cloudflare 每条线路各自每天 20 次，最多约 40 次。
- 阿里云本地额度按北京时间自然日重置。
- 只有阿里云 HTTP 200 响应扣除本地额度，同一 `request_id` 只扣一次。
- 收到任何阿里云 HTTP 响应后不切换 Cloudflare；仅连接前失败或本地额度耗尽时切换。
- 不记录聊天正文、IP、API Key 或额度 Secret。
- 不新增第三方 Python 或 Node 依赖。
- 保留所有无关未提交改动，不执行 `git reset` 或 `git checkout`。
- 按用户要求不创建 Git 提交、标签或推送。

---

## File Structure

- Modify: `buddy_ai.py` — 本地额度状态读写与默认聊天线路选择。
- Modify: `tests/test_ai_config.py` — 本地额度、计数幂等和线路切换测试。
- Modify: `aliyun-chat/src/server.js` — 删除跨境额度调用，直接调用智谱。
- Modify: `aliyun-chat/test/server.test.js` — 验证无额度配置时仍可调用智谱，且只有一次上游请求。
- Modify: `config.json.example` — 发布配置启用阿里云主入口。
- Modify: `tests/test_packaging_assets.py` — 固化公开主入口与 Cloudflare 兜底地址。
- Generate: `aliyun-chat/dist/petpet-aliyun-chat-root.zip` — 阿里云根目录部署包。
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/阿里云本地额度与 Cloudflare 独立额度实施记录.md` — 实施与验证记录。

### Task 1: 本地阿里云额度账本

**Files:**
- Modify: `buddy_ai.py:25-28, 220-285`
- Test: `tests/test_ai_config.py`

**Interfaces:**
- Produces: `ALIYUN_LOCAL_DAILY_LIMIT: int = 20`
- Produces: `CHAT_QUOTA_STATE_PATH: str`
- Produces: `_aliyun_quota_today(now=None) -> str`
- Produces: `_aliyun_quota_available(today=None) -> bool`
- Produces: `_record_aliyun_quota_success(request_id, today=None) -> bool`

- [ ] **Step 1: Write failing state tests**

Add tests that patch `buddy_ai.CHAT_QUOTA_STATE_PATH` to the test temporary directory:

```python
def test_aliyun_local_quota_recovers_from_invalid_file_and_resets_next_day(self):
    with open(ai.CHAT_QUOTA_STATE_PATH, "w", encoding="utf-8") as file:
        file.write("not json")
    self.assertTrue(ai._aliyun_quota_available("2026-08-14"))
    for index in range(20):
        self.assertTrue(ai._record_aliyun_quota_success(
            f"00000000-0000-4000-8000-{index:012d}", "2026-08-14"
        ))
    self.assertFalse(ai._aliyun_quota_available("2026-08-14"))
    self.assertTrue(ai._aliyun_quota_available("2026-08-15"))

def test_aliyun_local_quota_counts_each_request_once(self):
    request_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    self.assertTrue(ai._record_aliyun_quota_success(request_id, "2026-08-14"))
    self.assertFalse(ai._record_aliyun_quota_success(request_id, "2026-08-14"))
    with open(ai.CHAT_QUOTA_STATE_PATH, encoding="utf-8") as file:
        state = json.load(file)
    self.assertEqual(state["aliyun"]["count"], 1)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
pytest -q tests/test_ai_config.py -k "aliyun_local_quota"
```

Expected: FAIL because the quota constants and functions do not exist.

- [ ] **Step 3: Implement minimal atomic local ledger**

In `buddy_ai.py`, use fixed UTC+8 rather than an external timezone database:

```python
ALIYUN_LOCAL_DAILY_LIMIT = 20
CHAT_QUOTA_STATE_PATH = os.path.join(DATA_DIR, "chat_quota_state.json")

def _aliyun_quota_today(now=None):
    current = now or datetime.now(timezone(timedelta(hours=8)))
    return current.date().isoformat()
```

Implement a private loader that accepts only an object containing the requested date, integer `count` in `0..20`, and a list of UUID strings. Missing or invalid data returns a fresh state. Save with `tempfile.mkstemp`, UTF-8 JSON, `flush`, `os.fsync`, and `os.replace`; clean the temporary file in `finally`.

`_record_aliyun_quota_success` must return `False` without writing when `request_id` already exists or the count is already 20; otherwise append the request ID, increment once, atomically save, and return `True`.

- [ ] **Step 4: Run focused tests and verify GREEN**

```powershell
pytest -q tests/test_ai_config.py -k "aliyun_local_quota"
```

Expected: all selected tests pass.

- [ ] **Step 5: Inspect only this task's diff**

```powershell
git diff -- buddy_ai.py tests/test_ai_config.py
```

Confirm no config, memory, chat history, or unrelated user state is changed.

### Task 2: 路由接入本地额度

**Files:**
- Modify: `buddy_ai.py:626-770`
- Test: `tests/test_ai_config.py:360-443`

**Interfaces:**
- Consumes: `_aliyun_quota_available(today=None) -> bool`
- Consumes: `_record_aliyun_quota_success(request_id, today=None) -> bool`
- Preserves: `_default_proxy_stream(primary_endpoint, fallback_endpoint, user_text, mem, timeout, pet_name=None)` event stream API.

- [ ] **Step 1: Write failing route tests**

Add these behavior tests; each test first saves the same primary and fallback URLs used by the existing route tests:

```python
def test_aliyun_http_200_records_one_local_use(self):
    ai.set_default_chat_consent(True)
    config = ai.load_config()
    config.update({
        "default_chat_primary_url": "https://aliyun.example/v1/chat",
        "default_chat_fallback_url": "https://cloudflare.example/v1/chat",
    })
    ai.save_config(config)
    response = FakeRequestsStreamResponse([
        b'data: {"choices":[{"delta":{"content":"hi"}}]}',
        b'data: [DONE]',
    ])
    with patch("buddy_ai.requests.Session") as session_type, patch.object(
        ai, "_record_aliyun_quota_success"
    ) as record:
        session_type.return_value.post.return_value = response
        events = list(ai.chat_stream("hello", ai._default_memory(), timeout=5))
    body = json.loads(
        session_type.return_value.post.call_args.kwargs["data"].decode("utf-8")
    )
    record.assert_called_once_with(body["request_id"])
    self.assertEqual(events[-1], ("done", "hi"))

def test_aliyun_connection_failure_does_not_record_local_use(self):
    ai.set_default_chat_consent(True)
    config = ai.load_config()
    config.update({
        "default_chat_primary_url": "https://aliyun.example/v1/chat",
        "default_chat_fallback_url": "https://cloudflare.example/v1/chat",
    })
    ai.save_config(config)
    fallback = FakeRequestsStreamResponse([b'data: [DONE]'])
    with patch("buddy_ai.requests.Session") as session_type, patch(
        "buddy_ai.requests.post", return_value=fallback
    ), patch.object(ai, "_record_aliyun_quota_success") as record:
        session_type.return_value.post.side_effect = \
            ai.requests.ConnectTimeout("offline")
        list(ai.chat_stream("hello", ai._default_memory(), timeout=5))
    record.assert_not_called()

def test_exhausted_aliyun_local_quota_skips_primary_and_uses_cloudflare(self):
    ai.set_default_chat_consent(True)
    config = ai.load_config()
    config.update({
        "default_chat_primary_url": "https://aliyun.example/v1/chat",
        "default_chat_fallback_url": "https://cloudflare.example/v1/chat",
    })
    ai.save_config(config)
    fallback = FakeRequestsStreamResponse([b'data: [DONE]'])
    with patch.object(ai, "_aliyun_quota_available", return_value=False), patch(
        "buddy_ai.requests.Session"
    ) as session_type, patch(
        "buddy_ai.requests.post", return_value=fallback
    ) as fallback_post:
        list(ai.chat_stream("hello", ai._default_memory(), timeout=5))
    session_type.assert_not_called()
    self.assertEqual(
        fallback_post.call_args.args[0], "https://cloudflare.example/v1/chat"
    )
```

The first test must decode `session.post.call_args.kwargs["data"]`, take its `request_id`, and compare it to the recorder call so the assertion covers the real logical request.

- [ ] **Step 2: Run tests and verify RED**

```powershell
pytest -q tests/test_ai_config.py -k "aliyun_http_200_records or aliyun_connection_failure_does_not_record or exhausted_aliyun_local_quota"
```

Expected: FAIL because routing does not consult or update the local ledger.

- [ ] **Step 3: Implement the minimal route integration**

At the start of `_default_proxy_stream`, generate `request_id` as today. Before constructing a direct session, require both `primary_endpoint` and `_aliyun_quota_available()`.

If the local quota is exhausted, set `route = "cloudflare"`, skip the direct session entirely, and use the same payload against the fallback. Immediately after a primary response with `status_code == 200`, call `_record_aliyun_quota_success(request_id)` exactly once. Do not record for exceptions or non-200 responses.

Keep current behavior that `ConnectTimeout`/`ConnectionError` may fall back, while `ReadTimeout` and HTTP responses do not.

- [ ] **Step 4: Run route regression tests**

```powershell
pytest -q tests/test_ai_config.py -k "aliyun or default_proxy"
```

Expected: all selected tests pass, including the existing same-payload fallback, read-timeout, and HTTP-error tests.

- [ ] **Step 5: Run the complete Python chat test set**

```powershell
pytest -q tests/test_ai_config.py tests/test_chat_tools.py tests/test_packaging_assets.py
```

Expected: all tests pass.

### Task 3: 移除阿里云跨境额度调用

**Files:**
- Modify: `aliyun-chat/src/server.js:35-116`
- Test: `aliyun-chat/test/server.test.js`

**Interfaces:**
- Consumes environment: `ZHIPU_API_KEY`, optional `ZHIPU_ENDPOINT`, optional `ZHIPU_MODEL`.
- No longer consumes: `QUOTA_ENDPOINT`, `QUOTA_SHARED_SECRET`.
- Preserves: `handleRequest(request, { env, fetchImpl, sourceIp, log }) -> Promise<Response>`.

- [ ] **Step 1: Replace quota-first tests with failing direct-upstream tests**

Remove tests whose required behavior is specifically the deleted cross-cloud quota call. Change the test environment to omit quota variables and add:

```javascript
test("calls GLM once without Cloudflare quota configuration", async () => {
  const calls = [];
  const response = await handleRequest(request(), {
    env: { ZHIPU_API_KEY: "test-only-key", ZHIPU_MODEL: "glm-4.7-flash" },
    fetchImpl: async (url, options) => {
      calls.push({ url: String(url), options });
      return new Response("data: [DONE]\n\n", {
        status: 200, headers: { "content-type": "text/event-stream" },
      });
    },
  });
  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].options.body).model, "glm-4.7-flash");
});
```

Update diagnostics expectations to contain only `zhipu_response`.

- [ ] **Step 2: Run Node tests and verify RED**

```powershell
Set-Location aliyun-chat
npm.cmd test
```

Expected: FAIL because the function still requires quota variables and calls the quota endpoint first.

- [ ] **Step 3: Delete only the quota dependency**

In `handleRequest`:

- Require only `ZHIPU_API_KEY` in `configuration_missing`.
- Delete the `QUOTA_ENDPOINT` fetch, its authorization header, quota response mapping, and `quota_exception` logging.
- Keep request validation unchanged.
- Keep the existing智谱 request, SSE forwarding, `zhipu_response` and safe `zhipu_exception` diagnostics unchanged.

- [ ] **Step 4: Run Aliyun tests and verify GREEN**

```powershell
npm.cmd test
```

Expected: all Aliyun tests pass and every successful request makes exactly one mocked fetch call.

- [ ] **Step 5: Rebuild and inspect the root ZIP**

```powershell
$artifact = "dist\petpet-aliyun-chat-root.zip"
Compress-Archive -LiteralPath "src\server.js","package.json" -DestinationPath $artifact -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $artifact))
$zip.Entries | Select-Object FullName,Length
$zip.Dispose()
```

Expected entries: root-level `server.js` and `package.json` only.

### Task 4: 启用公开阿里云主入口

**Files:**
- Modify: `config.json.example:7`
- Modify: `tests/test_packaging_assets.py:10-20`

**Interfaces:**
- Produces public primary endpoint: `https://petpet-yun-chat-zqblnbrnfs.cn-hangzhou.fcapp.run/v1/chat`
- Preserves fallback endpoint: `https://petpet-default-chat.gsheen-petpet.workers.dev/v1/chat`

- [ ] **Step 1: Change the packaging expectation first**

```python
self.assertEqual(
    config["default_chat_primary_url"],
    "https://petpet-yun-chat-zqblnbrnfs.cn-hangzhou.fcapp.run/v1/chat",
)
```

- [ ] **Step 2: Run the packaging test and verify RED**

```powershell
pytest -q tests/test_packaging_assets.py -k default_chat
```

Expected: FAIL because the primary URL is still empty.

- [ ] **Step 3: Update `config.json.example`**

Set `default_chat_primary_url` to the exact HTTPS endpoint above. Do not add API keys or quota secrets.

- [ ] **Step 4: Run packaging and configuration tests**

```powershell
pytest -q tests/test_packaging_assets.py tests/test_ai_config.py
```

Expected: all tests pass.

### Task 5: Documentation, deployment, and final verification

**Files:**
- Create: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/阿里云本地额度与 Cloudflare 独立额度实施记录.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/Petpet 总档案.md`

**Interfaces:**
- Records exact test totals, deployment ZIP SHA-256, Aliyun endpoint, and removed environment variables.

- [ ] **Step 1: Run focused verification**

```powershell
pytest -q tests/test_ai_config.py tests/test_chat_tools.py tests/test_packaging_assets.py
Set-Location aliyun-chat
npm.cmd test
Set-Location ..\cloudflare-worker
npm.cmd test
```

Expected: all three suites pass.

- [ ] **Step 2: Run full Python verification**

```powershell
Set-Location ..
pytest -q
python -m py_compile buddy_ai.py
git diff --check
```

Expected: full suite and compile pass; `git diff --check` reports no whitespace errors.

- [ ] **Step 3: Write Obsidian implementation record**

Record:

- Local state path and 20-per-day behavior.
- Cloudflare's independent 20-per-day behavior.
- Test commands and fresh totals.
- The generated ZIP path and SHA-256.
- The instruction to upload the ZIP and remove `QUOTA_ENDPOINT` and `QUOTA_SHARED_SECRET` from Aliyun after deployment.
- The instruction that no Git commit, push, or release was performed.

- [ ] **Step 4: Deploy and smoke-test Aliyun**

Upload `aliyun-chat/dist/petpet-aliyun-chat-root.zip`, retain startup command `/var/fc/lang/nodejs20/bin/node server.js`, and deploy. Send one valid request and confirm logs show `zhipu_response` with no `quota_response` or `quota_exception`.

- [ ] **Step 5: Restart source Petpet and perform user validation**

Start the current worktree's `pet.py`. In free mode, send one message without a system proxy and confirm the response uses the Aliyun route. Inspect `DATA_DIR/chat_diagnostic.log` for `route: aliyun` and `DATA_DIR/chat_quota_state.json` for count 1 without exposing either file's private content in project logs.
