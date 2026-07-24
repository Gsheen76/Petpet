# 🐶 Pet陪它

一只住在桌面上的治愈系陪伴小狗。它会走动、弹跳、撒娇、提醒你休息，也能通过智谱 GLM 陪你聊天并记住近期对话。

<p align="center">
  <img src="assets/poses/idle.png" width="280" alt="Pet陪它桌面小狗">
</p>

当前版本：`v1.2.0`

支持平台：Windows 10/11、macOS Intel、macOS Apple 芯片

## 功能

- 透明置顶桌宠，可拖拽、甩飞和物理弹跳
- 可扩展连续帧动作系统，走路、进食、玩耍等行为自动触发动画
- 饱腹、心情、精力、等级、经验与陪伴天数
- 右键成长卡和五个治愈系快捷互动
- 单行自适应说话气泡与丰富的主动自言自语
- 智谱 GLM 流式聊天、多轮记忆和离线预设回复
- 喝水、休息眼睛、起身活动等健康提醒
- 抚摸、喂食、玩耍、睡觉和碰撞音效
- Windows 系统托盘与 macOS 菜单栏入口
- 本地保存配置、记忆和养成状态
- 启动自动检查更新，也可从右键菜单或托盘主动检查并安装新版

## v1.2.0 更新亮点

- 新增动作动画引擎，首批加入更自然的走路与进食逐帧动画
- 全面整理“温馨设置”，开关改为滑动样式，数值调节更清晰，聊天窗口提供五档尺寸
- 修复设置修改、保存和恢复默认时部分选项未即时生效的问题
- 新增应用内检查更新与 Windows 自动替换重启流程
- 完成 macOS Intel / Apple 芯片双架构构建、数据目录和菜单栏基础适配
- 重新整理资源、构建、测试和工具目录，减少发布包中的开发素材

## 下载和运行

### Windows

1. 前往 [GitHub Releases](https://github.com/Gsheen76/Petpet/releases)。
2. 下载最新的 Windows ZIP 或 `Petpet.exe`。
3. 解压后双击 `Petpet.exe`，程序不会弹出命令行窗口。
4. 托盘区出现 Petpet 图标后，即可显示、隐藏、设置或退出桌宠。

不要把 `Petpet.exe` 单独放入受系统保护且不可写的目录，否则配置和状态可能无法保存。

### macOS

macOS 构建分为两种，请按“ → 关于本机”显示的芯片选择：

| Mac 类型 | 下载文件 |
|---|---|
| Apple M1、M2、M3、M4 或更新芯片 | `Petpet-macOS-arm64` |
| Intel 处理器 | `Petpet-macOS-intel` |

macOS 包由 [GitHub Actions](https://github.com/Gsheen76/Petpet/actions/workflows/build-macos.yml) 生成。若 Release 页面已经提供对应芯片的 ZIP，可直接下载；否则：

1. 打开一次成功的 `Build macOS app` 任务。
2. 在任务 `Summary` 页面底部找到 `Artifacts`。
3. 下载对应芯片的构建产物并解压外层 ZIP。
4. 打开其中的 `Petpet-v*-macOS-*.zip`。
5. 再次解压，将 `Petpet.app` 拖入“应用程序”。

当前安装包尚未经过 Apple Developer ID 签名和公证。首次打开若提示“无法验证开发者”：

1. 尝试打开一次 Petpet，然后关闭警告。
2. 打开“系统设置 → 隐私与安全性”。
3. 在“安全性”区域点击“仍要打开”，输入登录密码确认。

如果系统明确提示“会损坏你的电脑”或“检测到恶意软件”，不要绕过提示，应重新下载安装包并联系开发者检查。

## 操作

| 操作 | 效果 |
|---|---|
| 左键单击 | 抚摸小狗，提升心情 |
| 左键双击 | 打开 AI 聊天 |
| 左键拖动 | 移动或甩飞小狗 |
| 右键短按 | 打开成长卡和五个快捷互动 |
| 右键长按 | 打开完整状态页 |
| 托盘或菜单栏双击 | 显示或隐藏小狗 |

## 启用 AI 聊天

1. 在[智谱开放平台](https://open.bigmodel.cn)创建 API Key。
2. 找到对应平台的 `config.json`。
3. 填入：

```json
{
  "api_key": "你的智谱 API Key"
}
```

4. 保存并完全退出 Petpet，再重新打开。

配置文件位置：

| 运行方式 | 数据目录 |
|---|---|
| Windows 打包版 | `Petpet.exe` 所在目录 |
| macOS 打包版 | `~/Library/Application Support/Petpet` |
| 从源码运行 | 项目中的 `data/` |

也可以通过环境变量 `ZHIPU_API_KEY` 临时提供 Key。请勿把真实 API Key 提交到 Git，`data/` 和 `config.json` 已默认忽略。

不配置 Key 仍可使用除在线 AI 之外的全部功能，小狗会使用本地预设话术回复。

## 从源码运行

建议使用 Python 3.11。

### Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\runtime.txt
python pet.py
```

### macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/runtime.txt
python pet.py
```

首次运行会自动创建 `data/config.json`。旧版放在项目根目录的配置、记忆和状态文件会自动迁移到 `data/`。

## 构建

构建产物统一输出到 `dist/`，中间文件输出到 `build/`；两个目录都不会进入 Git。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出：

```text
dist/Petpet.exe
```

### macOS

PyInstaller 不支持在 Windows 上交叉生成 `.app`，必须在 macOS 或 GitHub 的 macOS Runner 上构建：

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

输出：

```text
dist/Petpet.app
```

`.github/workflows/build-macos.yml` 可手动触发 Intel 与 Apple 芯片双架构构建。正式公开分发还需要 Apple Developer ID 签名和公证。

## 数据与隐私

Petpet 只在本地保存以下文件：

| 文件 | 用途 |
|---|---|
| `config.json` | API Key |
| `memory.json` | AI 对话历史和用户画像 |
| `pet_state.json` | 等级、属性、位置和陪伴数据 |
| `pet_settings.json` | 界面、音效和提醒设置 |

在线聊天时，消息会发送到所配置的智谱 API；其他养成和界面功能可离线运行。

## 项目结构

```text
Petpet/
├── pet.py                       桌宠主程序
├── buddy_ai.py                  AI 对话、记忆与离线回复
├── app_paths.py                 跨平台资源和数据目录
├── updater.py                   跨平台检查、下载和应用更新
├── config.json.example          安全配置模板
├── assets/
│   ├── poses/                   七种小狗姿势
│   ├── icons/                   应用图标
│   ├── sounds/                  五种互动音效
│   └── animations/              动作清单、制作规范和连续帧
├── data/                        本地配置、记忆和状态（不进入 Git）
├── docs/
│   ├── TODO.md                  路线图和待办事项
│   └── RELEASE_NOTES_v1.2.0.md  v1.2.0 发布说明
├── packaging/
│   ├── Petpet-windows.spec      Windows PyInstaller 配置
│   └── Petpet-mac.spec          macOS PyInstaller 配置
├── requirements/
│   ├── runtime.txt              运行依赖
│   └── build.txt                打包和资源生成依赖
├── scripts/
│   ├── build_windows.ps1        Windows 构建入口
│   └── build_macos.sh           macOS 构建入口
├── tests/                       设置与更新逻辑自动化测试
└── tools/
    ├── chat_poc.py              命令行 AI 对话验证
    ├── make_icons.py            图标生成工具
    ├── make_sounds.py           音效生成工具
    ├── slice_sprite_sheet.py    AI 精灵表切帧工具
    └── repack_sprite_components.py  精灵表分割与重新排版工具
```

动画素材的画布、命名、AI 提示词和切帧方法见
[assets/animations/README.md](assets/animations/README.md)。

## 常见问题

### AI 聊天没有反应

- 检查 `config.json` 是否位于上表对应的数据目录。
- 确认字段名为 `api_key`，并检查网络是否能访问智谱开放平台。
- UTF-8 和带 BOM 的 UTF-8 配置均受支持。
- 完全退出托盘或菜单栏中的 Petpet 后再重新启动。

### Mac 下载后只能移到废纸篓

- 确认下载了与芯片匹配的 `arm64` 或 `intel` 包。
- 确认使用的是构建产物内层的 `Petpet-v*-macOS-*.zip`。
- 对“无法验证开发者”使用“隐私与安全性 → 仍要打开”。
- 对“会损坏你的电脑”不要强行绕过，应重新下载并反馈完整提示。

### 小狗不见了

点击系统托盘或 macOS 菜单栏中的 Petpet 图标，选择“回到屏幕中央”或“显示/隐藏”。

## 更新与路线图

- 默认在启动 5 秒后检查 GitHub Releases；可在“设置 → 启动时自动检查更新”中关闭。
- 也可以从托盘或右键菜单主动选择“检查更新”，程序会明确提示最新版、网络错误或可用更新。
- Windows 打包版会自动选择 `.exe` 或 Windows ZIP，下载并校验完成后隐藏替换旧程序、自动重启。
- macOS 版会根据 Apple 芯片或 Intel 芯片选择对应的 `.dmg`/ZIP，下载后打开更新包；根据系统提示将 Petpet 拖入“应用程序”并替换旧版本。
- 源码运行模式不会覆盖项目文件，检测到新版时会打开 GitHub Release 页面。
- GitHub API 被限流时会自动改用公开 Release 页面，不需要登录 GitHub。
- 后续计划见 [docs/TODO.md](docs/TODO.md)。

## 许可与素材

当前仓库未附带开源许可证。个人学习和个人使用可以继续使用；小狗姿势图由 AI 生成，请勿直接用于商业用途。

## 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)：桌面 GUI 框架
- [智谱开放平台](https://open.bigmodel.cn)：在线 AI 对话服务
- [PyInstaller](https://pyinstaller.org)：Windows 与 macOS 应用打包
