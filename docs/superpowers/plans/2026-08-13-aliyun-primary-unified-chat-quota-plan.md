# Aliyun Primary Unified Chat Quota Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route free chat through an Alibaba Cloud Function Compute Web function first, fall back to Cloudflare only before an Aliyun response begins, and enforce one shared daily quota across both paths.

**Architecture:** The desktop generates one UUID v4 `request_id` per logical message and sends it to both possible entry points. A Cloudflare Durable Object remains the single transactional quota ledger; Aliyun calls a secret-protected internal Worker endpoint before invoking GLM-4.7-Flash. Aliyun is the primary SSE endpoint and Cloudflare is the one-way disaster-recovery endpoint.

**Tech Stack:** Python 3, PyQt5, requests, pytest, JavaScript ES modules, Cloudflare Workers/Durable Objects, Node test runner, Alibaba Cloud Function Compute 3.0 Web function, Node.js HTTP server/SSE.

## Global Constraints

- Preserve all unrelated uncommitted changes in `codex/home-scene-system`.
- Do not commit, push, or publish a desktop release unless explicitly requested.
- Installation ID and source IP each have one combined limit of 20 requests per UTC day across Aliyun and Cloudflare.
- Every logical message uses one UUID v4 `request_id`; a matching repeated ID never increments quota twice.
- Never store prompts, replies, model keys, quota secrets, or raw IP addresses in logs or repositories.
- Aliyun is always the primary free-chat endpoint; Cloudflare fallback is one-way and only before any Aliyun HTTP response exists.
- `ReadTimeout`, HTTP responses, and started SSE streams never trigger a second provider endpoint.

---

### Task 1: Add idempotent unified quota to Cloudflare

**Files:**
- Modify: `cloudflare-worker/src/index.js`
- Modify: `cloudflare-worker/test/index.test.js`
- Modify: `cloudflare-worker/.dev.vars.example`
- Modify: `cloudflare-worker/README.md`

**Interfaces:**
- Consumes: `request_id`, `install_id`, source IP, `env.QUOTA_SHARED_SECRET`
- Produces: transactional quota result `new`, `existing`, `exhausted`, or `identity_mismatch`

- [x] Add failing tests for request identity and prove the same logical request only increments installation/IP counts once. Public chat keeps a server-generated-ID compatibility path for released clients.
- [x] Add failing tests proving a reused request ID with a different installation returns `409 request_identity_mismatch`; a route IP change remains idempotent.
- [x] Add failing tests for `POST /internal/quota/consume`: missing/wrong bearer secret returns 401, valid secret calls the same Durable Object transaction, and no chat content is accepted.
- [x] Run `npm.cmd test` and verify the new cases fail because the current Durable Object always increments.
- [x] Extend the Durable Object transaction to hash/store the request identity before incrementing and return distinct statuses without storing raw identifiers.
- [x] Route both `/v1/chat` and `/internal/quota/consume` through the same quota operation; keep model calls exclusively on `/v1/chat`.
- [x] Document `QUOTA_SHARED_SECRET=` as an empty local variable and the Wrangler secret command without recording a value.
- [x] Run `npm.cmd test` and verify the complete Worker suite passes.

### Task 2: Build the Aliyun Web function

**Files:**
- Create: `aliyun-chat/package.json`
- Create: `aliyun-chat/src/server.js`
- Create: `aliyun-chat/test/server.test.js`
- Create: `aliyun-chat/.env.example`
- Create: `aliyun-chat/README.md`
- Create: `aliyun-chat/s.yaml.example`

**Interfaces:**
- Consumes: `POST /v1/chat` with `{request_id, install_id, messages}`; trusted source address; `ZHIPU_API_KEY`, `QUOTA_ENDPOINT`, `QUOTA_SHARED_SECRET`, `ZHIPU_MODEL`
- Produces: existing Petpet SSE format or stable JSON errors

- [x] Write failing request-contract tests for method/path/content type, UTF-8 byte size, UUID v4 fields, message roles, seven-message maximum, 4000-character system limit, and 1200-character turn limit.
- [x] Write failing tests proving the function forwards only quota identifiers/IP to `QUOTA_ENDPOINT`, never message text, and maps quota statuses to 409/429/503.
- [x] Write failing tests proving GLM is not called when quota fails and GLM receives `glm-4.7-flash`, `stream: true`, `max_tokens: 200`, and disabled thinking after quota succeeds.
- [x] Write failing tests proving upstream SSE chunks are forwarded unchanged with `text/event-stream` and no-store caching.
- [x] Implement a dependency-injected Node HTTP handler plus a port-9000 startup wrapper suitable for Function Compute Web functions.
- [x] Add environment examples containing names only and an `s.yaml.example` that keeps secrets out of source.
- [x] Run `npm.cmd test` in `aliyun-chat` and verify all tests pass.

### Task 3: Add desktop primary/fallback routing

**Files:**
- Modify: `buddy_ai.py`
- Modify: `config.json.example`
- Modify: `tests/test_ai_config.py`

**Interfaces:**
- Consumes: `default_chat_primary_url`, `default_chat_fallback_url`, one generated UUID v4 request ID
- Produces: one logical SSE chat stream and metadata-only route diagnostics

- [x] Write failing tests proving every new message gets one request ID and the same serialized payload is reused for fallback.
- [x] Write failing tests proving Aliyun uses a `requests.Session` with `trust_env=False` and is attempted before Cloudflare.
- [x] Write failing tests proving only Aliyun DNS/TCP/TLS/`ConnectTimeout` before an HTTP response triggers Cloudflare; `ReadTimeout`, HTTP errors, and stream errors do not.
- [x] Preserve Cloudflare system-proxy behavior and its single proxy `ConnectTimeout` retry.
- [x] Replace the single proxy URL lookup with primary/fallback URL accessors that preserve compatibility with existing `default_chat_proxy_url` configurations.
- [x] Extend metadata diagnostics with `route=aliyun|cloudflare` while preserving the allowlist that excludes content and credentials.
- [x] Run `python -m pytest tests/test_ai_config.py tests/test_chat_tools.py -q` and verify all focused tests pass.

### Task 4: Create and configure cloud resources

**Files:**
- Modify only cloud-managed configuration; never write secret values to repository files

**Interfaces:**
- Consumes: tested `aliyun-chat` package and Worker code
- Produces: Aliyun HTTPS function URL, deployed Worker internal quota endpoint, matching server-side shared secret

- [ ] In Function Compute 3.0, create one Web function in `cn-hangzhou`, custom runtime Node.js, startup command `npm start`, port 9000, timeout 60 seconds, public URL enabled, POST allowed.
- [ ] Configure Aliyun environment variables `ZHIPU_API_KEY`, `QUOTA_ENDPOINT`, `QUOTA_SHARED_SECRET`, and `ZHIPU_MODEL=glm-4.7-flash` through the console or deployment secret mechanism.
- [ ] Generate a new high-entropy shared secret locally without printing it; set the same value in Aliyun and with `npx.cmd wrangler secret put QUOTA_SHARED_SECRET`.
- [ ] Deploy Cloudflare and the Aliyun Web function, recording only deployment IDs and public URLs.
- [ ] Add the Aliyun URL to `config.json.example` as `default_chat_primary_url` and retain Cloudflare as `default_chat_fallback_url`.

### Task 5: Verify failover and combined quota

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\聊天系统\阿里云优先与统一免费额度设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

**Interfaces:**
- Consumes: both deployed HTTPS endpoints
- Produces: evidence that primary routing, failover, idempotency, and limit behavior match the design

- [ ] Send one fixed non-private message without a proxy and record status, model, first-content time, and total time from Aliyun.
- [ ] Reuse the same request ID against Cloudflare and verify quota counts do not increase twice.
- [ ] Use a controlled unreachable Aliyun test URL to verify the desktop falls back to Cloudflare only on connection failure.
- [ ] Verify a simulated Aliyun `ReadTimeout` does not call Cloudflare.
- [ ] Run both Node suites, focused Python tests, `python -m pytest -q`, Python compilation, and `git diff --check`.
- [ ] Update Obsidian with deployment IDs, public non-secret URLs, measured timings, exact test counts, and maintenance instructions.
