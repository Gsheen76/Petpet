# Petpet 阿里云大陆聊天入口

这是面向中国大陆玩家的主聊天入口。它直接调用低价的智谱 `glm-4.7-flashx`，以 SSE 原样返回模型输出。客户端在本机独立记录阿里云每日 20 次成功调用；阿里云函数不访问 Cloudflare 配额服务。

## 本地验证

```powershell
npm.cmd test
$env:PORT = "9000"
npm.cmd start
```

测试服务只需向 `http://127.0.0.1:9000/v1/chat` 发送 JSON。不要把真实密钥写入 `.env.example`、`s.yaml.example`、截图、日志或 Git。

## 函数计算 3.0 配置

- 地域：华东 1（杭州）`cn-hangzhou`
- 类型：Web 函数，自定义运行时
- 公共层：选择阿里云官方 `Nodejs20`（Custom.Debian10）运行时层
- 启动命令：`node src/server.js`
- 监听端口：`9000`
- 超时：`60` 秒
- 环境变量：`ZHIPU_API_KEY`、`ZHIPU_MODEL=glm-4.7-flashx`

公开请求最多包含 12 条消息和 32768 字节；系统消息最多 8000 字符，单条普通消息最多 1600 字符。模型输出上限保持 200 Tokens，并关闭思考模式以控制等待时间和成本。

日志只记录请求结果、耗时和数值型智谱业务错误码，不记录聊天正文、上游错误说明或 API Key。

`s.yaml.example` 只保留无密钥的结构示例。正式密钥请在阿里云控制台或部署环境变量中配置。
