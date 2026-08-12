# 🐶 Pet陪它

一只住在桌面上的治愈系陪伴小狗。它会走动、弹跳、撒娇、提醒你休息，也能通过默认免费文字服务或个人智谱 GLM Key 陪你聊天并记住近期对话。

<p align="center">
  <img src="assets/poses/idle.png" width="280" alt="Pet陪它桌面小狗">
</p>

当前版本：`v1.4.1`

支持平台：Windows 10/11、macOS Intel、macOS Apple 芯片

## 功能

- 透明置顶桌宠，可拖拽、甩飞和物理弹跳
- 可扩展连续帧动作系统，包含走路、进食、抚摸、睡眠和挖宝动画
- 互动扔球玩法：拉远视角后可选择落点，球与小狗同步运动，并用 24 帧正面扑跃动作在落点交会；接球后会定格 1 秒并显示庆祝效果
- 自动作息：精力低于 30% 时会走到最近的屏幕角落睡觉，自动睡眠恢复到 80% 以上后自行醒来；手动睡眠仍由玩家控制
- 饱腹、心情、精力、等级、经验、好感度与陪伴天数
- 右键状态卡与“聊天、小屋、商店、互动、更多”五入口快捷菜单；互动页集中提供抚摸、喂食、玩耍和睡觉
- 温馨记录：统计相识时长、实际运行时长、Pet币收支和各类互动次数
- 暖心成就：完成容易理解的阶段目标后手动领取 Pet币，每次升级都有等级奖励
- 小游戏中心：可选择“金币雨”或“幸运爪爪”反复游玩并按成绩赚取 Pet币
- Pet币商店：装扮支持分类、购买前试戴和待机位置微调，并可强化六类日常效果
- 家场景：固定在屏幕内的横向家居画板，小狗会在其中活动，背景视口随小狗移动
- 家居商店：可用 Pet币购买地毯、沙发、绿植和壁画，并在家中自由拖动摆放
- 首次启动治愈系新手教程，完成后可以为小狗命名
- 自动换行且完整排队显示的说话气泡与丰富的主动自言自语
- 默认免费文字聊天、个人 GLM 图文聊天、多轮记忆、已发布玩法知识库和离线预设回复
- 喝水、休息眼睛、起身活动等健康提醒
- 抚摸、喂食、玩耍、睡觉和碰撞音效
- Windows 系统托盘与 macOS 菜单栏入口
- 本地保存配置、记忆和养成状态
- 启动自动检查更新，也可从右键菜单或托盘主动检查并安装新版

## v1.4.1 更新亮点

- 聊天改为“免费聊天 / 自己配置”两种清晰模式；未配置个人 Key 时可直接使用默认免费文字服务
- 个人聊天保留 GLM-4.6V-Flash，并支持上传图片与小狗交流；API Key 只保存在玩家本机
- 新增随版本维护的玩法知识库，小狗可以在对话中介绍家园、家具、互动、养成和设置功能
- 聊天窗口统一为柔和暖色圆角风格，加入小狗与玩家头像、玩家头像上传及更精简的模式选项
- 设置与教程重新排版并默认居中打开，放大字体、统一卡片层级和控件尺寸
- 健康提醒改为“少 / 适中 / 多”三档；性格偏好合并为“文静 / 适中 / 活泼”三档
- 教程更新为六页精简引导，覆盖桌面互动、小屋、图片聊天、健康提醒与宠物命名
- 默认聊天代理加入安装级额度保护和清晰的失败提示；额度不可用时可切换为个人 GLM Key

## 下载和运行

### Windows

1. 前往 [GitHub Releases](https://github.com/Gsheen76/Petpet/releases)。
2. 下载最新的 Windows ZIP 或 `Petpet.exe`。
3. 解压后双击 `Petpet.exe`，程序不会弹出命令行窗口。
4. 托盘区出现 Petpet 图标后，即可显示、隐藏、设置或退出桌宠。

`Petpet.exe` 与用户数据彼此独立；移动或替换程序不会影响保存在
`%LOCALAPPDATA%\Petpet` 中的配置、记忆和养成状态。

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
| 睡觉时按住左键左右晃动 | 温柔地摇醒小狗 |
| 点击右键 | 打开成长卡与聊天、喂食、玩耍、睡觉、更多五个快捷气泡 |
| 右键 → 更多 → 记录 | 查看陪伴时长、Pet币收支和累计互动数据 |
| 右键 → 更多 → 成就 | 查看进度并领取 Pet币；有奖励时会显示红点 |
| 右键 → 商店 | 打开装扮、强化和家居商店 |
| 右键 → 互动 | 切换到抚摸、喂食、玩耍和睡觉四个互动按钮 |
| 右键 → 小屋 | 打开或聚焦固定的家场景画板 |
| 小屋中左键地面 | 显示脚印路径并让小狗走向指定目的地 |
| 家场景右上角“退出” | 退出家场景并恢复普通桌面活动 |
| 托盘或菜单栏双击 | 显示或隐藏小狗 |

首次启动会依次介绍常用操作，并在最后一步保存小狗名字。以后可以从
“右键 → 更多 → 教程”重新查看教程或修改名字。

## 记录、成就与 Pet币

新系统直接保存在原有 `pet_state.json` 中，旧存档首次加载时会自动补齐，
不会重置名字、等级、经验、属性或陪伴天数。

- 记录页包含相识时长、桌面实际陪伴时长、历史 Pet币收入与消费，以及
  抚摸、喂食、玩耍、睡眠、接球、聊天、摇醒、好感、启动和升级等数据。
- 每次抚摸、喂食、玩耍、发送聊天消息、手动睡觉、接球或摇醒都可增加好感。
  除聊天外，每类互动都有独立的好感冷却；冷却期间动作、动画与属性效果
  正常生效，只是不重复增加好感。聊天每发送一条有效消息都会增加好感。
- 当前好感冷却为：抚摸 20 秒、喂食 5 分钟、玩耍与接球各 3 分钟、
  摇醒 2 分钟、手动睡觉 10 分钟、随机休息气泡 5 分钟。
- 好感升级后会提高每分钟经验；饱腹、心情和精力不再影响经验速度。
  右键成长卡会完整显示好感等级、当前进度、下一级需求与实时 EXP/min。
- 成就按陪伴天数、互动次数、接球、聊天和等级分阶段解锁。达到要求后
  会在“更多”和“成就”气泡显示红点，需要玩家进入成就页领取奖励。
- 每升一级都会生成对应的等级成就。旧存档已有的等级也可以补领。
- 商店顶部拆分为“装饰”和“强化”两个独立栏目。强化共 5 级，
  价格逐级增加；满级玩耍不再消耗精力和饱腹，满级睡眠不再消耗饱腹。
- 抚摸和喂食强化只提高对应属性，不额外提高经验；“成长加速”会在
  好感决定的每秒经验基础上提供倍率。随机需求气泡触发的互动不会
  直接获得经验，但完成互动仍会增加好感。
- 装饰栏目已支持领取、购买、装备和卸下，并提供免费的“暖心红项圈”。
  每件装饰都作为独立透明贴图叠加在待机姿势上，玩家可以拖动位置，
  并微调大小和角度；走路、睡眠、进食、抚摸和接球等动作不显示装饰。
- 商店的“家居”栏目与穿戴装饰分开保存。购买后的地毯、沙发、绿植和壁画
  可在家场景内拖拽位置；它们只有视觉效果，不影响小狗物理、动画和属性。
- 当前 Pet币主要来自成就。后续还会加入小游戏奖励和小狗随机挖到
  Pet币的事件，现有收支记录与余额可直接复用。

## 启用 AI 聊天

右键小狗打开快捷菜单，选择“聊天”即可发送文字；双击小狗会进入小屋。选择免费聊天时，Petpet 使用项目方部署的限时免费文字服务：

- 首次发送前会明确说明消息将交给 OpenRouter 的免费模型处理，且免费模型可能有各自的数据使用条款；只有确认后才会发送。
- 默认模型为 OpenRouter 的 `openrouter/free` 免费路由；每个安装 ID 和来源 IP 每个 UTC 日最多各 20 次请求，每次回复最多 200 个输出 token。200 是单次回复上限，不是每日总 token 额度。
- 免费模型、额度或可用性可能调整；额度耗尽或服务不可用时，聊天窗口会显示系统提示，不会伪装成小狗的回答。
- 默认免费服务仅支持文字，不支持上传图片。

聊天窗口底部只有一个聊天模式按钮，可直接选择“免费聊天”或“自己配置 API”。模式由玩家明确选择，不再根据是否保存 Key 自动切换。切回免费聊天时，已经保存的个人 Key 会继续留在本机，但不会被使用。

如果需要使用图片，可以选择“自己配置 API”并配置智谱 Key：

1. 在[智谱开放平台](https://open.bigmodel.cn)创建 API Key。
2. 点击聊天框底部的聊天模式按钮，选择“自己配置 API”。
3. 在弹窗中选择 `GLM-4.6V-Flash` 并填入 Key；保存后下一条消息立即生效，不需要重启。此模式支持文字和单张 PNG、JPG/JPEG 或 WEBP 图片（最大 10 MiB）。

因此两种模式的边界是：**默认免费文字聊天**无需玩家 Key，只处理文字；
**个人 GLM-4.6V-Flash**使用玩家自己的智谱 Key，并支持文字和图片。

图片会随本次消息发送给所配置的智谱 API。Petpet 不会复制原图，也不会把图片 Base64 写进聊天记忆；为便于回看，本机仅保留一张聊天缩略图。移除尚未发送的图片会清除其临时缩略图。旧配置首次读取时会按是否存在个人 Key迁移聊天模式，此后完全遵循玩家的显式选择。

项目维护者的默认聊天代理部署步骤见 [cloudflare-worker/README.md](cloudflare-worker/README.md)。仓库、安装包、示例配置和项目笔记都不得包含供应商真实密钥；代理必须通过 Cloudflare Worker Secret 注入一枚重新生成的 Key。

小狗会用自然的对话内容回复，不显示自动狗狗图标或括号动作说明。你也可以直接询问当前版本的玩法，例如小屋、家具装修、互动、成长、商店、小游戏或图片聊天。相关资料随应用版本本地打包，不需要联网读取项目笔记；每次新增或调整玩家可见功能时，会同步更新 `assets/knowledge/game_knowledge.json` 及其版本号。

配置文件位置：

| 运行方式 | 数据目录 |
|---|---|
| Windows 打包版 | `%LOCALAPPDATA%\Petpet` |
| macOS 打包版 | `~/Library/Application Support/Petpet` |
| Windows 源码/发布版 | `%LOCALAPPDATA%\Petpet` |
| macOS 源码/发布版 | `~/Library/Application Support/Petpet` |

通常不需要手动操作配置文件。也可以通过环境变量 `ZHIPU_API_KEY`
临时提供 Key；环境变量的优先级高于程序内保存的 Key。请勿把真实
API Key 提交到 Git，`data/` 和 `config.json` 已默认忽略。

不配置 Key 也不接受默认聊天说明时，其他养成和界面功能仍可正常使用。

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

### 一键发布

维护者准备好版本号与 `docs/RELEASE_NOTES_v<版本>.md`、提交全部改动后，可在
干净工作树中运行：

```powershell
.\scripts\release.ps1 -Version 1.4.1
```

脚本会重新运行测试、构建并冒烟验证 Windows、生成校验和、安全同步 `main`、
建立草稿 Release，并触发 macOS 双架构工作流。只有以下四项正式资产均存在且
非空时才会公开版本：

- `Petpet.exe`
- `Petpet-v1.4.1-windows.zip`
- `Petpet-v1.4.1-macOS-arm64.zip`
- `Petpet-v1.4.1-macOS-intel.zip`

中途失败时 Release 保持草稿；修复问题后可重复运行同一命令继续。脚本不会
强推、覆盖标签或删除 worktree。完整约束见
[`v1.4.1 一键发布设计`](docs/superpowers/specs/2026-08-13-v1.4.1-one-click-release-design.md)。

## 数据与隐私

Petpet 只在本地保存以下文件：

| 文件 | 用途 |
|---|---|
| `config.json` | API Key、聊天模式、默认聊天同意状态、安装 ID 和公开代理地址 |
| `memory.json` | AI 对话历史和用户画像 |
| `pet_state.json` | 名字、等级、属性、好感、位置、记录、成就、Pet币、装扮和强化数据 |
| `pet_settings.json` | 界面、音效和提醒设置 |

默认文字聊天会经项目方 Cloudflare Worker 转发到限时免费模型；个人 Key 模式会直接请求智谱 API。其他养成和界面功能可离线运行。

## 项目结构

```text
Petpet/
├── pet.py                       桌宠主程序
├── version.py                   唯一版本号来源
├── buddy_ai.py                  AI 对话、记忆与离线回复
├── game_knowledge.py            本地版本化的玩家玩法知识库
├── home_pet.py                  小屋宠物状态、2.5D 移动与睡眠目标
├── home_scene.py                家场景、家具装修、导航反馈与宠物渲染
├── scene_system.py              场景坐标、视口与家具几何
├── progression.py               记录、成就、Pet币经济与强化结算
├── progression_ui.py            记录、成就和商店的治愈系界面
├── decoration_renderer.py       待机装饰贴图定位、裁切与分层绘制
├── app_paths.py                 跨平台资源和数据目录
├── updater.py                   跨平台检查、下载和应用更新
├── config.json.example          安全配置模板
├── assets/
│   ├── poses/                   七种小狗静态姿势
│   ├── icons/                   应用图标
│   ├── sounds/                  五种互动音效
│   ├── props/                   接球等玩法使用的运行时道具
│   ├── decorations/             商店预览及待机装饰透明贴图
│   ├── scenes/home/             家背景、家具、小屋宠物与导航反馈素材
│   └── animations/              动作清单、制作规范和连续帧
├── data/                        本地配置、记忆和状态（不进入 Git）
├── docs/
│   ├── TODO.md                  路线图和待办事项
│   ├── RELEASE_NOTES_v1.2.0.md  v1.2.0 发布说明
│   ├── RELEASE_NOTES_v1.2.1.md  v1.2.1 发布说明
│   ├── RELEASE_NOTES_v1.2.2.md  v1.2.2 发布说明
│   ├── RELEASE_NOTES_v1.2.3.md  v1.2.3 发布说明
│   ├── RELEASE_NOTES_v1.2.4.md  v1.2.4 发布说明
│   ├── RELEASE_NOTES_v1.3.0.md  v1.3.0 发布说明
│   ├── RELEASE_NOTES_v1.3.1.md  v1.3.1 发布说明
│   ├── RELEASE_NOTES_v1.3.2.md  v1.3.2 发布说明
│   └── RELEASE_NOTES_v1.4.0.md  v1.4.0 发布说明
├── packaging/
│   ├── Petpet-windows.spec      Windows PyInstaller 配置
│   └── Petpet-mac.spec          macOS PyInstaller 配置
├── requirements/
│   ├── runtime.txt              运行依赖
│   └── build.txt                打包和资源生成依赖
├── scripts/
│   ├── build_windows.ps1        Windows 构建入口
│   └── build_macos.sh           macOS 构建入口
├── tests/                       互动、养成、界面与更新逻辑自动化测试
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

- 打开聊天窗口，检查底部聊天模式是否为“免费聊天”或“自己配置 API”。
- 自配模式显示“未配置”时，点击模式按钮重新选择“自己配置 API”，填写 Key 并保存。
- 如果通过 `ZHIPU_API_KEY` 提供 Key，程序会在自配模式下优先使用环境变量。
- 检查网络是否能访问智谱开放平台。
- UTF-8 和带 BOM 的 UTF-8 配置均受支持。
- 完全退出托盘或菜单栏中的 Petpet 后再重新启动。

### Mac 下载后只能移到废纸篓

- 确认下载了与芯片匹配的 `arm64` 或 `intel` 包。
- 确认使用的是构建产物内层的 `Petpet-v*-macOS-*.zip`。
- 对“无法验证开发者”使用“隐私与安全性 → 仍要打开”。
- 对“会损坏你的电脑”不要强行绕过，应重新下载并反馈完整提示。

### 小狗不见了

点击系统托盘或 macOS 菜单栏中的 Petpet 图标，选择“回到屏幕中央”或“显示/隐藏”。

### 不同 Windows 电脑上的显示大小

Windows 版使用 Per-Monitor V2 DPI 感知，固定小狗、窗口、按钮和布局的尺寸，不再随系统缩放整体变大；文字会独立放大以保持清晰易读。

## 更新与路线图

- 默认在启动 5 秒后检查 GitHub Releases；可在“设置 → 启动时自动检查更新”中关闭。
- 也可以从托盘或右键菜单主动选择“检查更新”，程序会明确提示最新版、网络错误或可用更新。
- Windows 打包版会自动选择 `.exe` 或 Windows ZIP。更新包只在系统临时目录停留，校验完成后会在原安装目录原子替换 `Petpet.exe`、自动重启并删除下载缓存、待更新文件、临时备份和旧的 `update/updates/updata` 目录。
- 原安装目录最终只保留一个最新的 `Petpet.exe`；名字、等级、记忆和设置稳定保存在 `%LOCALAPPDATA%\Petpet`，替换程序时不会覆盖用户数据。
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
