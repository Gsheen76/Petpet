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
- **自主行为** — 没人理时会自己溜达、发呆、偶尔找你
- **眨眼动画** — 每 2-3 秒眨一次眼，走路时有上下波动
- **系统托盘** — 双击显示/隐藏，右键菜单
- **可调设置** — 聊天窗口尺寸/字体、置顶开关
- **离线运行** — 无需联网（AI 对话除外），数据本地持久化

## 🚀 使用

### 方式一：直接运行 exe（推荐）

1. 下载 `SheenPet.exe` 和 `config.json`
2. 放在同一个文件夹
3. 双击 `SheenPet.exe`

### 方式二：从源码运行

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
| 右键短按 | 弹出菜单 |
| 右键长按 | 打开状态页 |
| 托盘双击 | 显示/隐藏 |

## 📦 打包

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name SheenPet ^
  --icon icons/icon-256.png ^
  --add-data "poses;poses" ^
  --add-data "icons;icons" ^
  --add-data "buddy_ai.py;." ^
  pet.py
```

## 🔄 更新机制

程序启动后自动检查 GitHub Releases，有新版弹窗提示，一键下载替换重启。

## 📁 结构

```
Petpet/
├── pet.py              主程序
├── buddy_ai.py         AI 引擎（人设/记忆/流式）
├── chat_poc.py         命令行聊天测试
├── config.json         API key 配置（需自填）
├── banner.png          宣传图
├── poses/              7 张姿势 PNG
│   ├── idle.png  happy.png  sad.png
│   ├── eat.png   sleep.png  drag.png  close.png
└── icons/              各尺寸图标
```

## 📜 许可

个人使用免费。poses/ 图片由 AI 生成，请勿商用。

## 🙏 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) — GUI 框架
- [智谱 GLM-4-Flash](https://open.bigmodel.cn) — 免费 AI 对话
