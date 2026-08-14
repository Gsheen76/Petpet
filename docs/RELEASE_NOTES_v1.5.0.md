# Pet陪它 v1.5.0

本次更新集中完善家园宠物、好感成长和默认免费聊天。家园中的小狗拥有更完整的
移动、待机与睡眠行为；默认聊天优先走中国大陆可直连的阿里云函数，并保留备用线路。

## 主要更新

- 家园宠物支持点击移动、四向行走、待机、地毯睡眠和自主活动。
- 家园新增紧凑的商店与互动入口，家具商店使用双列布局。
- 状态卡成为可免费领取、摆放和改名的墙面家具。
- 新增好感成长与零属性红点提醒，等级和经验继续记录玩家整体成长。
- 优化属性卡、路径脚印、目的地标记、宝藏气泡和跟随宠物的对话框指针。
- 宝藏与小游戏的 Pet币基础奖励提高。
- 免费聊天优先使用阿里云函数，Cloudflare Worker 作为备用线路，两边额度独立。
- 默认模型更新为 GLM-4.7-FlashX，并扩充按需注入的游戏知识库与聊天上下文。

## 下载

- Windows 可执行文件：`Petpet.exe`
- Windows 便携包：`Petpet-v1.5.0-windows.zip`
- Apple 芯片 Mac：`Petpet-v1.5.0-macOS-arm64.zip`
- Intel Mac：`Petpet-v1.5.0-macOS-intel.zip`

macOS 应用当前尚未进行 Apple Developer ID 签名和公证。首次打开时可能需要在
“系统设置 → 隐私与安全性”中选择“仍要打开”。

## 升级与数据

升级不会重置宠物名字、属性、好感、等级、经验、Pet币、家具、装扮、设置、头像、
个人 API Key 或聊天记忆。Windows 用户数据保存在 `%LOCALAPPDATA%\Petpet`，macOS
用户数据保存在 `~/Library/Application Support/Petpet`。
