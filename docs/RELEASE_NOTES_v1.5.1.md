# Pet陪它 v1.5.1

本次更新完成代码与资源结构重构收尾，并修复重构后桌面宠物首次绘制时的启动崩溃。

## 主要更新

- 业务实现按 `app`、`chat`、`home`、`progression`、`minigames` 和 `ui` 进入 `petpet` 包。
- 根目录旧模块继续保留为兼容入口，现有外部导入方式不需要立即调整。
- 桌面宠物与家园宠物资源独立管理。
- 运行资源与制作源图分离到 `assets/runtime` 和 `assets/source`。
- Windows 与 macOS 打包配置只收集运行资源，制作源图不会进入安装包。
- 修复桌面宠物首次绘制引用缺失姿势名称映射导致的 `NameError` 启动崩溃。
- 增加包内兼容层边界和桌面宠物首绘回归测试。

## 下载

- Windows 可执行文件：`Petpet.exe`
- Windows 便携包：`Petpet-v1.5.1-windows.zip`
- Apple 芯片 Mac：`Petpet-v1.5.1-macOS-arm64.zip`
- Intel Mac：`Petpet-v1.5.1-macOS-intel.zip`

macOS 应用当前尚未进行 Apple Developer ID 签名和公证。首次打开时可能需要在
“系统设置 → 隐私与安全性”中选择“仍要打开”。

## 升级与数据

升级不会重置宠物名字、属性、好感、等级、经验、Pet币、家具、装扮、设置、头像、
个人 API Key 或聊天记忆。Windows 用户数据保存在 `%LOCALAPPDATA%\Petpet`，macOS
用户数据保存在 `~/Library/Application Support/Petpet`。
