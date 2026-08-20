# GLM-4.7-Flash 免费兜底实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将宠物名称限制为最多 6 个字符，并在 OpenRouter 免费池失败时由 Worker 转向智谱官方 `glm-4.7-flash`。

**Architecture:** 客户端仍只请求现有 Cloudflare Worker。Worker 先请求 OpenRouter；仅当上游返回错误、无响应体或网络异常时，使用 `ZHIPU_API_KEY` 请求智谱官方兼容接口，并将成功的 SSE 流原样返回。两个上游都失败时维持现有稳定错误码。

**Tech Stack:** Python、PyQt5、Cloudflare Workers JavaScript、Node.js 测试、pytest。

## Global Constraints

- `ZHIPU_API_KEY` 只能保存为 Cloudflare Secret，不得进入源码、配置示例、日志或测试快照。
- 智谱兜底模型固定为 `glm-4.7-flash`，接口固定为官方 `https://open.bigmodel.cn/api/paas/v4/chat/completions`。
- OpenRouter 免费池保持第一优先级；智谱只处理 OpenRouter 失败的请求。
- 宠物名称的输入、规范化和旧存档读取统一截断为 6 个字符。
- 不提交、不推送，除非用户另行明确要求。

---

### Task 1: 六字符宠物名称

**Files:**
- Modify: `buddy_ai.py`
- Modify: `pet.py`
- Test: `tests/test_ai_config.py`
- Test: `tests/test_menu_ui.py`

**Interfaces:**
- Consumes: `normalize_pet_name(value)`、`PetNameEditDialog`
- Produces: 最多 6 字符的持久名称与输入 UI

- [ ] 写失败测试：长名称规范化为前 6 字符，输入框 `maxLength()` 为 6，提示显示“最多 6 个字符”。
- [ ] 运行聚焦测试并确认因现有 12 字符限制失败。
- [ ] 将规范化、输入框和提示统一改为 6。
- [ ] 运行聚焦测试确认通过。

### Task 2: Worker 智谱官方兜底

**Files:**
- Modify: `cloudflare-worker/src/index.js`
- Modify: `cloudflare-worker/test/index.test.js`
- Modify: `cloudflare-worker/README.md`

**Interfaces:**
- Consumes: `env.OPENROUTER_API_KEY`、`env.ZHIPU_API_KEY`、已校验的 `body.messages`
- Produces: OpenRouter 优先、智谱 `glm-4.7-flash` 次级的 SSE 响应

- [ ] 写失败测试：OpenRouter 非 2xx、无 body 或抛异常时请求智谱官方接口。
- [ ] 写失败测试：智谱请求使用 Bearer Secret、`glm-4.7-flash`、流式输出和关闭思考模式。
- [ ] 写失败测试：两上游都失败时返回 `default_provider_unavailable`，无 Secret 泄漏。
- [ ] 实现只在 OpenRouter 失败时执行的智谱兜底函数。
- [ ] 运行 Worker 全量测试。

### Task 3: 验证与记录

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\聊天系统\默认免费聊天代理设计.md`

**Interfaces:**
- Consumes: Task 1、Task 2 的最终行为
- Produces: 可维护的部署命令和验证记录

- [ ] 运行名称与 Worker 聚焦测试。
- [ ] 运行 `pytest -q`、Worker 全量测试和 `git diff --check`。
- [ ] 同步 Obsidian，记录 `npx wrangler secret put ZHIPU_API_KEY` 和 `npx wrangler deploy`，不记录 Secret 值。
