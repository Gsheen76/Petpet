# 默认免费聊天代理设计

## 目标

让没有个人 API Key 的玩家可以体验文字聊天，同时不把项目方的模型密钥打包进 Petpet。默认文字聊天使用 OpenCode Zen 的 `deepseek-v4-flash-free`；图片聊天仅使用玩家自己的 GLM-4.6V-Flash Key。

## 请求路由

```text
玩家发送聊天
├─ 已保存个人智谱 Key：Petpet 直连 GLM-4.6V-Flash（文字或图片）
└─ 未保存 Key：检查默认聊天同意状态
   ├─ 未同意：显示数据说明，等待确认
   └─ 已同意：Petpet -> Cloudflare Worker -> OpenCode Zen DeepSeek V4 Flash Free
```

旧的 GLM-4.7-Flash 选择会迁移为默认免费文字聊天；已有个人智谱 Key 的玩家会迁移到 GLM-4.6V-Flash，避免丢失其图片聊天能力。

## Cloudflare Worker

- Worker 从 Secret `OPENCODE_API_KEY` 读取项目方新生成的 OpenCode Zen Key；密钥不进入仓库、桌面程序、日志或 Obsidian。
- 上游为 OpenAI 兼容接口 `https://opencode.ai/zen/v1/chat/completions`，模型 ID 为 `deepseek-v4-flash-free`。
- 仅接收文本、最近六轮聊天和预先生成的随机安装 ID；拒绝图片、超大请求体、超长上下文及客户端传入的模型/Token 参数。
- Worker 固定 `max_tokens=200`，只返回经映射的 SSE 文本流。
- 使用 KV 以日期为窗口同时记录安装 ID 与来源 IP 的调用计数；任一计数到每日 20 条即返回稳定错误码 `default_quota_exhausted`。KV 项目在次日过期。
- 上游限流、不可用或免费模型结束时，不向客户端泄露上游报文、状态细节或密钥，只返回 `default_provider_unavailable`。
- `deepseek-v4-flash-free` 是 OpenCode 标注的限时免费模型，且其免费期内容可能用于模型改进；模型 ID 必须通过 Worker 环境变量可替换。[OpenCode Zen 文档](https://dev.opencode.ai/docs/zen)

安装 ID 用于轻量限额而非用户身份验证；它可被重置或伪造，所以 IP 限额、请求尺寸限制和服务端硬性模型参数仍是必要保护。

## Petpet 客户端

- 新增内部模型状态 `petpet-free`，界面显示“免费聊天 · DeepSeek V4 Flash”。它不是用户可填写的 Key，也不会显示 OpenCode 的具体密钥。
- 首次免费聊天前显示一次可持久化的确认框：消息会发送至 OpenCode 的限时免费模型，免费期内容可能用于模型改进；玩家可取消并配置个人 Key。
- 无个人 Key 时只显示默认免费文字聊天，不显示上传图片。
- 有个人 Key 时提供 GLM-4.6V-Flash；它可处理文字与图片，保留现有图片缩略图和本地记忆隐私策略。
- 默认额度耗尽时，在聊天内显示“今日免费聊天额度已用完。配置自己的 API Key 后可继续聊天。”并打开/聚焦 Key 配置入口；不把这类错误伪装成小狗的普通回复。
- 免费服务不可用时显示可理解的临时不可用状态，并提供稍后重试与配置个人 Key 两条路径。

## 部署与运维

- 仓库新增独立 `cloudflare-worker/`，包含 Worker 源码、`wrangler` 配置、KV 绑定、`.dev.vars.example`、部署与 Secret 设置说明、Worker 测试。
- 项目方在 Cloudflare 后台创建 KV 命名空间，设置新的 `OPENCODE_API_KEY` Secret，部署 Worker，并把公开 Worker URL 写入发布构建配置。
- 不在本次工作中替项目方登录 Cloudflare、部署 Worker 或填写任何真实密钥。
- 需要定期检查 OpenCode 模型列表；若限时免费模型取消，则仅替换 Worker Secret/模型环境变量与玩家文案，不暴露新的供应商细节给客户端。

## 验收

- 发布包和仓库均不包含项目方模型 Key。
- 无 Key 玩家需要先同意数据说明，之后可获得最多 20 条/日的默认文字聊天。
- 有 Key 玩家可使用 GLM-4.6V-Flash 图文聊天；无 Key 时图片上传不可用。
- 超额、上游不可用、取消同意、旧配置迁移和个人 Key 优先级均有自动化测试。
- Worker 与客户端的 focused tests、完整 `pytest -q`、编译检查和 `git diff --check` 通过。
