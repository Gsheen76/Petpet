# Default Free Chat Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let players without a personal API key use a consented, quota-limited default text chat service without shipping the project API key.

**Architecture:** A standalone Cloudflare Worker validates a compact text transcript, applies dual daily limits using KV, and streams an OpenCode Zen response without exposing upstream details. Petpet selects direct GLM-4.6V when a personal key exists; otherwise it uses a configured Worker endpoint after one persisted data-use confirmation.

**Tech Stack:** Python 3/PyQt5/unittest/pytest; TypeScript/Cloudflare Workers/Wrangler/Vitest/KV; OpenAI-compatible SSE.

**Implementation status (2026-08-11):** Tasks 1–5 are implemented in the current worktree. The Worker intentionally uses plain ES modules plus Node's native test runner instead of TypeScript/Vitest, so it has no runtime or test dependency to install. Deployment remains an explicit project-owner step because the repository contains neither a Cloudflare account binding nor a provider Secret.

**Verification result:** Worker contract tests `8 passed`; focused Python tests `43 passed`; full Python suite `340 passed`. Final compile, diff and credential-shape checks are listed in the Obsidian implementation record.

## Global Constraints

- Do not store, paste, log, test with, or commit any real API key; Cloudflare receives a newly generated `OPENCODE_API_KEY` only as a Worker Secret.
- Default provider model is configurable in the Worker and initially `deepseek-v4-flash-free`; it is a limited-time service and its free-period content may be used for model improvement.
- Default chat accepts text only and allows at most 20 requests per installation ID and source IP per UTC day, with a fixed maximum of 200 output tokens.
- GLM-4.6V-Flash is the only retained direct model and remains the personal-key image-chat provider.
- The current worktree's `pet.py` is the only source launch target. Preserve existing uncommitted changes; use `apply_patch`; do not reset, checkout, commit, push, or deploy.
- Mirror every new project Markdown record to `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/`.

---

### Task 1: Cloudflare Worker request, validation and quota boundary

**Files:**
- Create: `cloudflare-worker/src/index.ts`
- Create: `cloudflare-worker/test/index.test.ts`
- Create: `cloudflare-worker/package.json`
- Create: `cloudflare-worker/wrangler.toml`
- Create: `cloudflare-worker/vitest.config.ts`

**Interfaces:**
- Produces: `export interface Env { CHAT_QUOTA: KVNamespace; OPENCODE_API_KEY: string; OPENCODE_MODEL?: string; OPENCODE_ENDPOINT?: string }`.
- Produces: a Worker `fetch(request, env, context)` that accepts `POST /v1/chat` with `{install_id: string, messages: Array<{role: "system"|"user"|"assistant", content: string}>}`.
- Produces: only `default_quota_exhausted`, `default_provider_unavailable`, or `invalid_default_chat_request` JSON error codes for default-service failures.

- [ ] **Step 1: Write the failing Worker tests**

```ts
it("returns quota exhaustion before invoking the upstream provider", async () => {
  const env = fakeEnv({ "quota:day:install:abc": "20" })
  const response = await worker.fetch(requestFor("abc"), env, executionContext)

  expect(response.status).toBe(429)
  await expect(response.json()).resolves.toEqual({
    error: "default_quota_exhausted",
  })
  expect(fetch).not.toHaveBeenCalled()
})

it("forwards only bounded text messages with fixed model and token limits", async () => {
  fetch.mockResolvedValue(sseResponse("汪！"))
  const response = await worker.fetch(requestFor("abc"), fakeEnv(), executionContext)

  const upstream = fetch.mock.calls[0][0] as Request
  const body = await upstream.json()
  expect(body).toMatchObject({
    model: "deepseek-v4-flash-free",
    stream: true,
    max_tokens: 200,
  })
  expect(response.headers.get("content-type")).toContain("text/event-stream")
})
```

- [ ] **Step 2: Run the RED test**

Run: `npm test -- --run test/index.test.ts` from `cloudflare-worker`

Expected: FAIL because no Worker module or package scripts exist.

- [ ] **Step 3: Implement the minimal secure Worker**

```ts
const DAILY_LIMIT = 20
const MAX_MESSAGES = 7
const MAX_CONTENT_CHARS = 1_200
const MAX_BODY_BYTES = 16_384

async function quotaKey(day: string, subject: string, value: string) {
  const bytes = new TextEncoder().encode(`${subject}:${value}`)
  const digest = await crypto.subtle.digest("SHA-256", bytes)
  return `quota:${day}:${subject}:${[...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0")).join("")}`
}
```

Validate method/path/content type/body size, UUID-format installation ID, message roles, count and string-only text content before any KV or upstream action. Hash installation ID and `CF-Connecting-IP` before writing date-scoped KV keys; increment both counters with a next-midnight TTL. Reject either exhausted subject before calling OpenCode. Build the upstream request using the environment model/endpoint defaults, fixed `stream: true`, `max_tokens: 200`, `thinking: {type: "disabled"}`, and only validated messages. Pass a successful SSE body through; map every invalid, upstream, or unexpected failure to the documented stable response without logs containing message bodies or headers.

- [ ] **Step 4: Run the GREEN Worker test**

Run: `npm test -- --run test/index.test.ts` from `cloudflare-worker`

Expected: PASS.

### Task 2: Worker deployment contract and secret-safe documentation

**Files:**
- Create: `cloudflare-worker/.dev.vars.example`
- Create: `cloudflare-worker/README.md`
- Modify: `cloudflare-worker/wrangler.toml`
- Test: `cloudflare-worker/test/index.test.ts`

**Interfaces:**
- Consumes: Task 1 `Env` bindings.
- Produces: a reproducible local/deployment procedure that never includes an API key value.

- [ ] **Step 1: Write the failing configuration test**

```ts
it("uses only named Worker bindings and never a committed provider key", async () => {
  const config = await readFile("wrangler.toml", "utf8")
  const example = await readFile(".dev.vars.example", "utf8")

  expect(config).toContain('binding = "CHAT_QUOTA"')
  expect(example).toContain("OPENCODE_API_KEY=")
  expect(example).not.toMatch(/sk-[A-Za-z0-9]/)
})
```

- [ ] **Step 2: Run the RED test**

Run: `npm test -- --run test/index.test.ts` from `cloudflare-worker`

Expected: FAIL because the deployment files do not exist.

- [ ] **Step 3: Add exact deployment artefacts**

Set the Worker compatibility date, bind KV as `CHAT_QUOTA`, and declare non-secret defaults for `OPENCODE_MODEL=deepseek-v4-flash-free` and the OpenCode chat-completions endpoint. Put only blank placeholder assignments in `.dev.vars.example`. In `README.md`, document: install dependencies; create a KV namespace; copy its ID into `wrangler.toml`; use `wrangler secret put OPENCODE_API_KEY`; run local tests; deploy; then place the resulting HTTPS URL in Petpet's public `default_chat_proxy_url` release configuration. Include key rotation, model replacement, and the fact that deployment is performed by the project owner.

- [ ] **Step 4: Run the GREEN configuration test**

Run: `npm test -- --run test/index.test.ts` from `cloudflare-worker`

Expected: PASS.

### Task 3: Petpet provider selection and consent state

**Files:**
- Modify: `buddy_ai.py`
- Modify: `config.json.example`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Produces: `FREE_MODEL = "petpet-free"`, `VISION_MODEL = "glm-4.6v-flash"`, `get_chat_mode() -> "default" | "personal"`, `has_default_chat_consent() -> bool`, and `set_default_chat_consent(accepted: bool) -> None`.
- Produces: `chat_stream()` routing personal-key messages to GLM and no-key text messages to `default_chat_proxy_url`.

- [ ] **Step 1: Write the failing Python routing and migration tests**

```python
def test_no_key_uses_default_proxy_after_consent(self):
    ai.set_default_chat_consent(True)
    ai.set_default_chat_proxy_url("https://petpet-chat.example/v1/chat")
    with patch("buddy_ai.urllib.request.urlopen", return_value=FakeStreamResponse()) as open_request:
        events = list(ai.chat_stream("你好", ai._default_memory()))

    request = open_request.call_args.args[0]
    self.assertEqual(request.full_url, "https://petpet-chat.example/v1/chat")
    self.assertEqual(events[-1], ("done", "hi"))

def test_legacy_model_migration_keeps_personal_key_on_glm_vision(self):
    write_config({"api_key": "id.secret", "model": "glm-4.7-flash"})

    self.assertEqual(ai.get_model(), ai.VISION_MODEL)
    self.assertEqual(ai.get_chat_mode(), "personal")
```

Also add tests for no consent returning `default_consent_required`, no endpoint returning `default_provider_unavailable`, image use without a personal key being rejected, and a quota JSON response mapping to `default_quota_exhausted`.

- [ ] **Step 2: Run the RED Python test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: FAIL because the default provider, consent and migration boundaries do not exist.

- [ ] **Step 3: Implement the minimal client routing boundary**

Replace the current GLM-4.7 default with the internal `petpet-free` label. Store only public settings in `config.json`: `default_chat_consent`, a UUID `default_chat_install_id`, and `default_chat_proxy_url`; generate the UUID with `uuid.uuid4()` once. Make direct GLM requests only when `get_api_key()` returns a personal key; keep the existing GLM image payload path intact. For default mode, require consent, reject image attachments, send only the system prompt plus the last six history turns and user text to the configured HTTPS Worker URL, parse SSE using the existing safe parser, and convert stable JSON error codes without inserting raw network text into a dog reply. Normalize legacy `glm-4-flash` and `glm-4.7-flash` according to whether a personal key exists.

- [ ] **Step 4: Run the GREEN Python test**

Run: `python -m pytest tests/test_ai_config.py -q`

Expected: PASS.

### Task 4: Chat window model UI, consent and actionable quota notices

**Files:**
- Modify: `pet.py:ChatWindow`
- Modify: `tests/test_chat_tools.py`

**Interfaces:**
- Consumes: Task 3 provider mode and errors.
- Produces: default-model consent, no default image upload, and non-dog system notices for quota/provider errors.

- [ ] **Step 1: Write the failing UI tests**

```python
def test_no_key_toolbar_identifies_free_text_chat_and_hides_image_upload(self):
    self.window._refresh_ai_tool_buttons()

    self.assertIn("免费聊天", self.window.model_btn.text())
    self.assertTrue(self.window.image_btn.isHidden())

def test_quota_exhaustion_shows_configuration_notice_not_dog_dialogue(self):
    self.window._pending_user = "你好"
    self.window.on_error("default_quota_exhausted")

    self.assertIn("今日免费聊天额度已用完", self.window.chat_notice.text())
    self.assertNotIn("🐶", self.window.chat_notice.text())
```

Add a consent test that patches the confirmation dialog to decline, then verifies no worker thread is created and `default_chat_consent` stays false.

- [ ] **Step 2: Run the RED UI test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: FAIL because the current toolbar treats GLM-4.7 as default and errors as pet replies.

- [ ] **Step 3: Implement consent and notices**

Render the default selection as “免费聊天 · DeepSeek V4 Flash”; only show GLM-4.6V-Flash and image upload once a personal key exists. Before starting a no-key message thread, show one explicit accept/cancel data-use dialog; persist acceptance only after accept. Add a neutral `chat_notice` status label for `default_quota_exhausted` and `default_provider_unavailable`; quota notice focuses the existing Key configuration button, while provider notice offers retry through the normal input flow. Do not persist an assistant dog reply when these default-service errors occur.

- [ ] **Step 4: Run the GREEN UI test**

Run: `python -m pytest tests/test_chat_tools.py -q`

Expected: PASS.

### Task 5: Player documentation, Obsidian records and end-to-end verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-11-default-chat-proxy-design.md`
- Modify: `docs/superpowers/plans/2026-08-11-default-chat-proxy-plan.md`
- Create/Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/聊天系统/默认免费聊天代理实施记录.md`

**Interfaces:**
- Consumes: completed Worker and Petpet provider selection.
- Produces: player-facing, secret-free setup/consent/limit documentation and operator deployment instructions.

- [ ] **Step 1: Review documentation requirements**

Confirm README distinguishes default text chat from personal GLM-4.6V image chat, states the 20/day and 200-token limits, asks for consent before default use, describes how to configure a personal key, and says the free provider may change or be temporarily unavailable.

- [ ] **Step 2: Update project and Obsidian records**

Add the public Worker endpoint setup field to `config.json.example` with an empty value, never a real URL or key. In README, include the player privacy notice and an operator-only link to `cloudflare-worker/README.md`. Mirror final design, plan and verification results in the Obsidian implementation record using frontmatter, callouts and wikilinks. Record only the Worker variable names, not values.

- [ ] **Step 3: Run focused, Worker and full verification**

Run:

```powershell
Push-Location cloudflare-worker; npm test -- --run; Pop-Location
python -m pytest tests/test_ai_config.py tests/test_chat_tools.py -q
python -m pytest -q
python -m py_compile buddy_ai.py pet.py
git diff --check
```

Expected: every command exits `0`; test fixtures contain no real credential-shaped value.

## Self-Review

- Task 1 covers request validation, quota enforcement, upstream isolation and stream forwarding; Task 2 makes deployment reproducible without secrets.
- Tasks 3 and 4 cover all client routes, legacy migration, consent, image restrictions and error UI; Task 5 covers player/owner records and every required verification command.
- Names and data flow are consistent: `default_chat_proxy_url`, `default_chat_consent`, `default_chat_install_id`, `default_quota_exhausted`, and `default_provider_unavailable` are introduced once and reused unchanged.
