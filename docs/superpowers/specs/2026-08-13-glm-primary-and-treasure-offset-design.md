# GLM 优先与宝箱位置调整设计

## 目标

- 免费聊天先请求智谱官方 `glm-4.7-flash`。
- GLM 请求失败、响应体缺失，或 5 秒内没有产生有效 `delta.content` 时，切换到 OpenRouter `openrouter/free`。
- OpenRouter 是最后一级兜底，不再循环切换。
- 桌面宝箱气泡在当前位置基础上上移 20px。

## 数据流

Worker 只扣除一次每日额度。额度通过后，先以关闭思考的参数请求 GLM；首个有效正文在 5 秒内出现时继续转发同一条流。GLM 不可用或首字超时则取消其响应流，再请求 OpenRouter。两个提供商均不可用时返回现有 `default_provider_unavailable`。

宝箱仍由 `InteractiveBubble._place_above_pet()` 居中定位，纵坐标由贴近小狗头顶约 2px 改为间隔约 22px，其他气泡不变。

## 验证

- Worker 契约测试覆盖 GLM 正常响应、GLM HTTP 失败、GLM 首字超时及双提供商失败。
- 桌面测试断言宝箱相对小狗头顶上移 20px。
- 运行 focused tests、Worker 全量测试、Python 全量测试和线上无隐私测速。
