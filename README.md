# 🐶 Pet陪它

一只住在桌面上的陪伴小狗，会走路、撒娇、陪你聊天、要吃的要贴贴。

<p align="center">
  <img src="banner.png" width="300" alt="Pet陪它">
</p>

## ✨ 功能

- **桌面悬浮** — 透明窗口常驻桌面，可拖拽到任意位置
- **物理弹跳** — 甩出去有惯性，撞墙撞地会弹
- **AI 对话** — 接入智谱 GLM-4-Flash，多轮记忆 + 情绪感知 + 主动搭话
- **状态养成** — 饱腹/心情/精力随时间变化，需要你照顾
- **等级系统** — 互动获得经验，维持高分被动涨经验，升级越来越慢
- **交互气泡** — 低属性时狗头上弹出可点击气泡，点完显示数值加成
- **温馨成长卡** — 右键显示等级、经验、陪伴天数与三项状态，搭配五个治愈系快捷按钮
- **自主行为** — 没人理时会自己溜达、发呆、偶尔找你
- **健康提醒** — 可设置喝水、休息眼睛和起身活动的提醒间隔
- **可选音效** — 抚摸、喂食、玩耍、睡觉和碰撞均有轻量音效，可随时关闭
- **眨眼动画** — 每 2-3 秒眨一次眼，走路时有上下波动
- **系统托盘** — 双击显示/隐藏，右键菜单
- **治愈系界面** — 聊天、状态、设置和托盘统一为奶油白与蜜桃色风格
- **可调设置** — 聊天窗口尺寸/字体、置顶、音效和健康提醒开关
- **离线运行** — 无需联网（AI 对话除外），数据本地持久化

## 🚀 使用

### Windows：直接运行 exe

1. 下载 `Petpet.exe` 和 `config.json`
2. 放在同一个文件夹
3. 双击 `Petpet.exe`

### macOS：运行 App

1. 下载并解压 macOS 发布包
2. 将 `Petpet.app` 拖入“应用程序”
3. 首次启动若被 Gatekeeper 拦截，请在“系统设置 → 隐私与安全性”中选择“仍要打开”
4. 点击菜单栏中的 Sheen 图标，可打开数据文件夹并编辑 `config.json`

macOS 的配置、记忆和状态保存在：

```text
~/Library/Application Support/Petpet
```

### 从源码运行

```bash
pip install PyQt5
python pet.py
```

## 💬 启用 AI 聊天

1. 去 https://open.bigmodel.cn 注册（免费）
2. 控制台 → API Keys → 创建 key
3. 编辑 `config.json`：
   ```json
   {"api_key": "你的key"}
   ```
4. 重启程序，双击小狗开始聊天

不填 key 也能用，小狗会用预设话术回复（不是真 AI）。

## 🎮 操作

| 操作 | 效果 |
|---|---|
| 左键单击 | 摸摸狗（心情+8） |
| 左键双击 | 打开聊天 |
| 左键拖动 | 移动 / 甩飞 |
| 右键短按 | 打开成长卡与五个快捷互动按钮 |
| 右键长按 | 打开状态页 |
| 托盘双击 | 显示/隐藏 |

## 📦 打包

### Windows

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name Petpet ^
  --icon icons/icon-256.png ^
  --add-data "poses;poses" ^
  --add-data "icons;icons" ^
  --add-data "buddy_ai.py;." ^
  pet.py
```

### macOS

必须在 macOS 上构建，PyInstaller 不支持从 Windows 交叉生成 `.app`：

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

输出文件为：

```text
dist/Petpet.app
```

GitHub 仓库中的 `.github/workflows/build-macos.yml` 也可以手动触发构建，会分别生成 Intel 与 Apple 芯片原生版本。

若要公开分发，还需要在 macOS 上使用 Apple Developer ID 进行代码签名和公证。

## 🔄 更新机制

程序启动后自动检查 GitHub Releases。Windows 版本支持下载替换重启；macOS
版本会打开对应的 `.dmg` 或 macOS `.zip` 下载地址，由用户完成替换。

## 🍎 macOS 兼容说明

- 支持透明置顶宠物窗口、拖拽与弹跳、聊天、状态养成、音效和菜单栏托盘
- 登录时启动使用 `~/Library/LaunchAgents/com.gsheen.petpet.plist`
- 可写数据统一放在 `~/Library/Application Support/Petpet`
- 应用以菜单栏工具运行，不在 Dock 中常驻显示
- 多屏幕坐标与不同 macOS 缩放比例仍建议在真机上继续测试

## 🩹 v1.1.1 修复内容

- 修复 Windows 编辑器或 PowerShell 保存的 `config.json` 带 UTF-8 BOM 时，API Key 无法读取的问题
- 配置读取现在同时兼容普通 UTF-8 和 UTF-8 BOM
- 已通过智谱 GLM 流式聊天实测

## 🌷 v1.1.0 更新内容

- 重做右键成长卡，扩大属性区域并保证等级、经验和状态文字完整显示
- 五个互动入口升级为带中文名称的大尺寸治愈系按钮
- 聊天窗、状态页、设置页和托盘菜单统一为温馨奶油色主题
- 自言自语气泡改为单行自适应宽度，并扩充日常、饥饿、心情和精力文案
- 新增喝水、休息眼睛、起身活动提醒
- 新增抚摸、喂食、玩耍、睡眠与碰撞音效及静音设置
- 优化互动需求气泡、经验显示、超高等级进度条和设置页稳定性

## 📁 结构

```
Petpet/
├── pet.py              主程序
├── buddy_ai.py         AI 引擎（人设/记忆/流式）
├── chat_poc.py         命令行聊天测试
├── config.json         API key 配置（需自填）
├── packaging/          Windows/macOS PyInstaller 配置
├── scripts/            macOS 构建脚本
├── requirements-macos.txt
├── banner.png          宣传图
├── poses/              7 张姿势 PNG
│   ├── idle.png  happy.png  sad.png
│   ├── eat.png   sleep.png  drag.png  close.png
│   └── sounds/          抚摸、喂食、睡眠、玩耍和碰撞音效
└── icons/              各尺寸图标
```

## 📜 许可

个人使用免费。poses/ 图片由 AI 生成，请勿商用。

## 🙏 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) — GUI 框架
- [智谱 GLM-4-Flash](https://open.bigmodel.cn) — 免费 AI 对话
