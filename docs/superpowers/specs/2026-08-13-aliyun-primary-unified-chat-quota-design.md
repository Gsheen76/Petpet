# 阿里云优先与统一免费聊天额度设计

## 目标

- 中国大陆玩家的免费聊天优先直连阿里云函数计算，不依赖本机代理。
- 阿里云连接阶段失败时，才使用现有 Cloudflare Worker 兜底。
- 阿里云与 Cloudflare 共用同一份每日额度：安装 ID 与来源 IP 各自每日最多 20 次。
- 同一句消息发生线路切换时只扣一次，不重复调用已经接收请求的上游。
- 智谱与 OpenRouter 密钥始终只存在于云端。

## 总体架构

```text
Petpet 桌面端
  │ request_id + install_id + messages
  ├─ 1. 阿里云函数（中国大陆主入口）
  │      ├─ 调 Cloudflare 内部额度接口
  │      └─ 调智谱 glm-4.7-flash 并转发 SSE
  │
  └─ 2. 仅连接阶段失败时：Cloudflare Worker
         ├─ 用同一 request_id 检查统一额度
         ├─ 调智谱 glm-4.7-flash
         └─ 智谱失败/首字超时后调 openrouter/free

Cloudflare Durable Object
  └─ 唯一原子额度账本与 request_id 幂等记录
```

## 客户端路由

发布配置新增两个 HTTPS 地址：

- `default_chat_primary_url`：阿里云函数公网 URL。
- `default_chat_fallback_url`：现有 Cloudflare `/v1/chat`。

每次玩家发送消息时生成 UUID v4 `request_id`，在一次逻辑请求的全部线路尝试中保持不变。

1. 客户端先直连阿里云，不读取或使用系统代理。
2. 只有阿里云发生 DNS、TCP、TLS 或 `ConnectTimeout`，且尚未收到 HTTP 响应时，才尝试 Cloudflare。
3. Cloudflare 兜底继续使用系统代理；若无代理，可进行一次正常系统网络请求，但不重复循环。
4. 阿里云返回任何 HTTP 响应、开始 SSE、发生 `ReadTimeout` 或已出现正文后，均不切换线路，避免重复回答与重复模型调用。
5. 日志仅记录线路、阶段、状态、模型和耗时，不记录消息正文、回复、IP、额度密钥或模型密钥。

## 统一额度与幂等

### 请求字段

两个公开入口都接受：

```json
{
  "request_id": "UUID v4",
  "install_id": "UUID v4",
  "messages": []
}
```

### Durable Object 数据

每日 Durable Object 保存：

- `install:<sha256>`：安装 ID 计数。
- `ip:<sha256>`：来源 IP 计数。
- `request:<sha256>`：已成功扣额的 `request_id`，值包含对应安装哈希。

扣额事务规则：

1. `request_id` 已存在且绑定相同安装：返回“已扣额”，不增加计数；允许阿里云与 Cloudflare 看到不同出口 IP。
2. `request_id` 已存在但安装身份不匹配：拒绝请求。
3. 任一计数达到 20：返回额度耗尽。
4. 否则同时增加安装与 IP 计数，并写入请求幂等记录。
5. 次日 alarm 沿用现有 `deleteAll()` 清理。

这保证阿里云尝试已经扣额、随后客户端因连接结果不明确进入 Cloudflare时，不会再次扣额。模型调用是否重复则由客户端“仅连接前失败才切换”的规则限制。

## 阿里云函数

采用阿里云函数计算 3.0 Web 函数，因为 Web 函数支持带 `Transfer-Encoding: chunked` 的 SSE 流式响应。默认公网函数 URL 可先用于测试；后续若绑定中国大陆自定义域名，需要完成 ICP 备案。

环境变量：

- `ZHIPU_API_KEY`：智谱官方 Key。
- `QUOTA_ENDPOINT`：Cloudflare 内部额度接口 URL。
- `QUOTA_SHARED_SECRET`：阿里云到 Cloudflare 的服务器间鉴权密钥。
- `ZHIPU_MODEL=glm-4.7-flash`。

阿里云函数校验与 Cloudflare 相同的消息数量、角色、字符数与正文大小。它从函数计算可信请求上下文读取玩家来源 IP，将 `install_id`、`request_id` 与来源 IP 通过 HTTPS 发送到内部额度接口；额度通过后才请求智谱。函数对客户端保持现有 SSE 格式和稳定错误码。

## Cloudflare 内部额度接口

新增 `POST /internal/quota/consume`，只接受：

- `Authorization: Bearer <QUOTA_SHARED_SECRET>`。
- 阿里云传来的合法 `request_id`、`install_id` 与来源 IP。

该接口只返回额度结果，不接收聊天内容，不调用模型。Secret 使用 Wrangler Secret 保存。公开 `/v1/chat` 也改用同一幂等扣额函数。

## 安全与隐私

- 桌面端不包含智谱 Key、OpenRouter Key或内部额度 Secret。
- 阿里云 HTTP 入口可匿名访问，但必须在应用层执行请求大小、字段和速率限制；不能把服务器间 Secret 放进桌面请求头。
- 阿里云会将来源 IP 发送到 Cloudflare 额度服务用于统一 IP 限额；隐私说明需要明确这一处理。如果后续要求 IP 不离开中国大陆，必须把唯一额度账本迁至阿里云存储，而不是双写。
- Cloudflare 内部额度接口失败时，阿里云采取失败关闭，不允许绕过额度。

## 错误语义

- `400 invalid_default_chat_request`
- `401 invalid_quota_authorization`（仅内部接口）
- `409 request_identity_mismatch`
- `429 default_quota_exhausted`
- `503 default_provider_unavailable`

玩家界面继续使用精简提示，不展示内部线路或异常名；诊断日志可以区分 `aliyun` 与 `cloudflare`。

## 测试与上线

1. Worker 单元测试：原子合计额度、幂等 request ID、身份冲突、内部鉴权、次日清理。
2. 阿里云函数测试：请求校验、额度服务异常、智谱 SSE 转发、稳定错误码。
3. 客户端测试：阿里云优先、仅连接前失败切 Cloudflare、ReadTimeout 不切换、同一 request ID。
4. 在无代理环境验证阿里云首字与完整响应。
5. 在阻断阿里云连接的测试环境验证 Cloudflare 兜底和只扣一次。
6. 先小范围启用阿里云 URL，再更新发布配置。

## 所需云资源

- 阿里云函数计算 3.0 Web 函数 1 个，建议地域：华东 1（杭州）或离主要玩家更近的大陆地域。
- 公网函数 URL 1 个，允许 POST；初期无需自定义域名。
- 阿里云环境变量/密钥配置 4 项。
- Cloudflare 新增 `QUOTA_SHARED_SECRET` 1 项，不新增数据库或 Durable Object。
