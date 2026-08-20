# 阿里云本地额度与 Cloudflare 独立额度设计

## 目标

- 阿里云聊天线路不再访问 Cloudflare 或依赖跨境额度服务。
- 阿里云线路由桌面客户端按北京时间每天记录 20 次免费额度。
- Cloudflare Worker 继续使用 Durable Object 独立记录每天 20 次额度。
- 阿里云本地额度耗尽后，客户端可以继续尝试 Cloudflare，因此单个玩家每天最多约有 40 次免费聊天机会。

## 客户端路由

1. 客户端读取独立的本地额度状态文件。
2. 当北京时间日期变化时，将阿里云计数重置为 0。
3. 阿里云计数小于 20 时，优先直连阿里云函数。
4. 阿里云返回有效 HTTP 200 响应后，本地计数增加 1。同一个 `request_id` 只计一次。
5. DNS、TCP、TLS 或连接超时等“尚未收到 HTTP 响应”的失败不扣本地次数，并按照现有连接阶段规则切换 Cloudflare。阿里云一旦返回任何 HTTP 响应，便不再切换线路，避免重复回答。
6. 阿里云本地次数达到 20 时，不再请求阿里云，直接尝试 Cloudflare。
7. Cloudflare 继续按自己的服务端额度规则返回成功或 `429 default_quota_exhausted`。

## 本地状态

状态保存在 `DATA_DIR` 下独立的 `chat_quota_state.json`，不混入用户设置：

```json
{
  "aliyun": {
    "date": "2026-08-14",
    "count": 3,
    "request_ids": ["UUID v4"]
  }
}
```

- 日期使用 `Asia/Shanghai` 的自然日。
- 文件通过临时文件、刷新落盘和 `os.replace` 原子替换保存。
- 文件缺失、损坏或字段非法时按当天 0 次恢复，不能阻止聊天窗口启动。
- `request_ids` 只保留当天已成功计数的请求 ID，防止同一次逻辑请求重复扣除。
- 本地计数是体验限制，不作为安全或计费边界；重装或手工修改文件可以重置额度，这是已接受的取舍。

## 阿里云函数

- 删除调用 `QUOTA_ENDPOINT` 的逻辑。
- 不再要求 `QUOTA_ENDPOINT` 与 `QUOTA_SHARED_SECRET` 环境变量。
- 保留请求格式、正文大小、消息数量和角色校验。
- 校验通过后直接调用 `glm-4.7-flash` 并转发 SSE。
- 保留不含消息正文、IP 与密钥的上游状态和耗时诊断日志。

部署完成后可以从阿里云函数删除 `QUOTA_ENDPOINT` 和 `QUOTA_SHARED_SECRET`。Cloudflare 中旧的内部额度接口可暂时保留以兼容已部署版本，但桌面客户端和新版阿里云函数均不再调用它。

## Cloudflare Worker

- 公共 `/v1/chat` 保持现有 Durable Object 每日 20 次限制。
- Cloudflare 额度与阿里云本地额度完全独立。
- 不改变 GLM 优先、OpenRouter 兜底及现有错误码。

## 错误与界面语义

- 阿里云连接失败：按现有规则尝试 Cloudflare，不扣阿里云本地次数。
- 阿里云返回服务错误：不扣本地次数；若已收到 HTTP 响应则不进行可能导致重复回答的线路切换。
- 阿里云本地额度耗尽：直接尝试 Cloudflare，不显示额外中间错误。
- 两条线路都不可用或 Cloudflare 额度也耗尽：继续显示现有精简提示。

## 测试

- 本地额度文件缺失、损坏、跨日重置与原子保存。
- 只有阿里云 HTTP 200 才计数，失败不计数。
- 同一 `request_id` 重试不重复计数。
- 第 20 次允许阿里云，第 21 次跳过阿里云并进入 Cloudflare。
- 阿里云函数不再读取或调用 Cloudflare 额度配置。
- 阿里云函数仍校验请求并正确转发 GLM SSE。
- Cloudflare 原有独立 20 次额度测试保持通过。
