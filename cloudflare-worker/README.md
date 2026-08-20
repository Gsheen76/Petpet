# Petpet 默认聊天 Cloudflare Worker

该 Worker 在 Petpet 与 OpenRouter 之间保管项目方密钥、校验纯文字请求，并执行默认免费额度。真实密钥不会进入桌面程序、仓库、发布包或日志。

## 模型与统一额度

默认上游已经配置为 OpenRouter 免费路由：

- 接口：`https://openrouter.ai/api/v1/chat/completions`
- 模型：`openrouter/free`
- Secret 名称：`OPENROUTER_API_KEY`

Worker 先使用智谱官方免费模型；智谱失败或首字超时后才使用 OpenRouter 免费池兜底：

- 接口：`https://open.bigmodel.cn/api/paas/v4/chat/completions`
- 模型：`glm-4.7-flash`
- Secret 名称：`ZHIPU_API_KEY`

`openrouter/free` 会从当前可用的免费模型中自动选择。它不收费，但可用模型、速度与限流会变化；免费模型可能有各自的数据使用条款。

## 部署与更新

1. 运行 `npm.cmd test`（Windows）或 `npm test`，确认 Worker 契约测试通过。
2. 使用 `npx wrangler secret put OPENROUTER_API_KEY`，只在 Wrangler 的交互提示中粘贴 OpenRouter Key。
3. 使用 `npx wrangler secret put ZHIPU_API_KEY`，只在 Wrangler 的交互提示中粘贴智谱官方 Key。
4. 使用 `npx wrangler secret put QUOTA_SHARED_SECRET` 配置与阿里云函数相同的高强度随机密钥。
5. 运行 `npx wrangler deploy`。
6. 聊天地址为 `https://petpet-default-chat.gsheen-petpet.workers.dev/v1/chat`；内部额度地址为同域名下的 `/internal/quota/consume`。

> [!warning]
> 不要把真实 Key 写入 `wrangler.toml`、`.dev.vars.example`、Petpet 配置、Obsidian、截图或 Git。曾经暴露过的 Key 必须撤销。

## 固定契约

- 入口：仅接受 `POST /v1/chat` 和 `application/json`。
- 输入：UUID v4 请求 ID、UUID v4 安装 ID，加最多 12 条纯文字消息；系统提示每条最多 8000 字符，用户与助手消息每条最多 1600 字符，请求整体最多 32 KiB。为兼容旧桌面版，公开接口暂时接受缺少请求 ID 的请求并在服务端生成。
- 限额：安装 ID 与来源 IP 各 20 次/UTC 日；每天使用一个 SQLite Durable Object，
  在同一事务内检查并递增两个哈希计数键。请求 ID 绑定安装 ID，阿里云与 Cloudflare 出口 IP 不同时仍只扣一次。
- 输出：SSE 流，每次请求固定 `max_tokens=200`，并使用 OpenRouter 的 `reasoning.effort=none` 关闭推理，避免免费推理模型耗尽正文额度。
- 稳定错误：`invalid_default_chat_request`、`default_quota_exhausted`、`default_provider_unavailable`。

上游异常、免费模型临时不可用、Secret 未配置或 Durable Object 额度存储异常时，
Worker 只返回统一不可用错误，不向客户端泄露上游报文、身份信息或凭据。

## 随桌面版本发布

Worker 源码和测试随 Petpet 源码版本维护，但 `cloudflare-worker/.wrangler/` 本地缓存
不会进入 Git 或安装包。正式桌面版使用仓库根目录的一键发布命令；该命令不会
读取、复制或上传 Worker Secret：

```powershell
.\scripts\release.ps1 -Version 1.4.1
```
