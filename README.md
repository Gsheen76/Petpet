# 🐶 Pet陪它

一只住在桌面上的治愈系陪伴小狗。它会在桌面上走动、弹跳、撒娇、提醒你休息，也可以进入小屋布置家居；你可以通过默认免费文字聊天或自己的智谱 API 与它交流。

<p align="center">
  <img src="assets/runtime/pets/lunch_meat/desktop/poses/idle.png" width="280" alt="Pet陪它桌面小狗">
</p>

当前版本：`v1.5.2`

支持平台：Windows 10/11、macOS Intel、macOS Apple 芯片

## v1.5.2 更新亮点

- 桌面宠物使用新的 16 帧待机动画，并支持小恐龙、草莓小子两套专属待机动画。
- 商店将桌面装扮调整为完整套装；装备后，待机时直接替换为该套装的动画和预览图。
- 摸头、喂食、玩耍、挖宝和睡觉等交互动画统一缩放，使小狗主体大小与待机状态一致。
- 睡觉动画缩放为 `0.7`，三项基础属性的自然消耗速度降低为原来的 `0.5` 倍。
- 限制动画解码尺寸，常用交互动画预加载，其余动画按需加载，降低内存占用。
- 预热右键菜单和属性卡，减少首次打开菜单时的鼠标阻塞，并修复菜单预热期间的窗口生命周期竞态。
- 加强小狗意外隐藏后的显示恢复和置顶保持逻辑。
- 增加待机动画、套装预览、菜单预热、内存限制和窗口生命周期回归测试。

## v1.5.1 更新亮点

- 业务代码按 `app`、`chat`、`home`、`progression`、`minigames` 和 `ui` 进入 `petpet` 包。
- 根目录旧模块继续作为兼容入口，已有导入方式可以逐步迁移。
- 桌面宠物与家园宠物资源分离，运行资源与制作源图分别放入 `assets/runtime` 和 `assets/source`。
- Windows 与 macOS 打包配置只收集 `assets/runtime`，制作源图不会进入安装包。
- 修复重构后桌面宠物首次绘制引用缺失姿势名称映射导致的启动崩溃。
- 增加包内兼容层和桌面宠物首绘回归测试。

## 功能

- 透明置顶桌宠，可拖拽、甩飞并进行物理弹跳。
- 连续帧动画系统，覆盖待机、行走、进食、抚摸、玩耍、睡觉、挖宝和接球等动作。
- 默认状态下持续播放待机动画；只有发生拖拽、互动、睡觉等状态变化时才切换到对应动作。
- 扔球玩法：选择落点后小狗会移动并扑跃接球，接球后会定格并显示庆祝效果。
- 自动作息：精力低于 30% 时，小狗会走到屏幕角落睡觉；恢复后会自动醒来。
- 属性与养成：饱腹、心情、精力、等级、经验、好感度和陪伴天数。
- 右键状态卡与五个快捷入口：聊天、小屋、商店、互动、更多。
- 互动入口包含抚摸、喂食、玩耍和睡觉。
- 记录页面统计相识时长、实际运行时长、Pet币收支和互动次数。
- 成就页面提供阶段目标和 Pet币奖励，领取后会记录到本地存档。
- 小游戏中心提供金币雨和幸运爪爪，可重复游玩并按成绩获得 Pet币。
- 家园场景提供独立的小狗、背景和家具，可购买并自由摆放地毯、沙发、绿植和壁画。
- 商店提供套装、家居和强化三个栏目。
- 首次启动教程会引导完成基础操作，完成后可以为小狗命名。
- 说话气泡支持自动换行、排队显示和主动自言自语。
- 支持喝水、休息眼睛、起身活动等健康提醒。
- 支持抚摸、喂食、玩耍、睡觉和碰撞音效。
- Windows 系统托盘和 macOS 菜单栏入口均可显示、隐藏、设置或退出程序。
- 启动后可检查更新，也可以从托盘或右键菜单主动检查更新。

## 下载

正式版本发布在 [GitHub Releases](https://github.com/Gsheen76/Petpet/releases)。当前 `v1.5.2` 的公开资产如下：

| 平台 | 文件 |
| --- | --- |
| Windows 直接运行 | `Petpet.exe` |
| Windows 便携包 | `Petpet-v1.5.2-windows.zip` |
| macOS Apple 芯片 | `Petpet-v1.5.2-macOS-arm64.zip` |
| macOS Intel | `Petpet-v1.5.2-macOS-intel.zip` |
| 校验和 | `Petpet-v1.5.2-SHA256SUMS.txt` |

Windows 下载 ZIP 后解压并运行 `Petpet.exe`。直接下载的 `Petpet.exe` 也可以独立运行，程序不会弹出命令行窗口。

macOS 请根据“ → 关于本机”显示的处理器选择 `arm64` 或 `intel` 包。安装包当前尚未进行 Apple Developer ID 签名和公证，首次打开可能需要在“系统设置 → 隐私与安全性”中选择“仍要打开”。如果系统明确提示“会损坏你的电脑”或“检测到恶意软件”，不要绕过提示，应重新下载并检查文件来源。

## 操作

| 操作 | 效果 |
| --- | --- |
| 左键单击 | 抚摸小狗，提升心情 |
| 左键双击 | 打开 AI 聊天 |
| 左键拖动 | 移动小狗；快速释放可以甩飞 |
| 睡觉时按住左键左右晃动 | 温柔地摇醒小狗 |
| 右键单击 | 打开成长卡和快捷菜单 |
| 右键 → 聊天 | 打开聊天窗口 |
| 右键 → 小屋 | 进入家园场景 |
| 右键 → 商店 | 打开套装、家居和强化商店 |
| 右键 → 互动 | 选择抚摸、喂食、玩耍或睡觉 |
| 右键 → 更多 | 打开记录、成就、小游戏、设置、隐藏、教程和退出 |
| 系统托盘或 macOS 菜单栏 | 显示、隐藏、设置、检查更新或退出 |

## 待机动画与套装

桌面待机动画是小狗的默认状态。小狗完成交互后会恢复待机；装备套装后，只替换待机状态的桌面动画，抚摸、喂食、玩耍、睡觉和挖宝仍使用对应的交互动画。

当前商店中的套装：

| 套装 | 价格 | 待机动画 |
| --- | ---: | --- |
| 小恐龙套装 | 680 Pet币 | `idle_dinosaur` |
| 草莓小子套装 | 760 Pet币 | `idle_strawberry` |

购买完整套装后会直接装备。未装备套装时使用默认小狗待机动画。套装在桌面上显示专属待机动画和拖拽预览图；家园宠物和家居资源仍由家园系统独立管理。

### 动画播放规则

- 默认待机为 16 帧循环，目标播放频率为 8 FPS。
- 小恐龙待机的逻辑播放序列为 `1..16, 7, 8, 9, 10, 11`，共 21 个逻辑帧；第 3、4、5 帧为 40 ms，其余帧为 160 ms。
- 草莓小子待机的逻辑播放序列为 `5..16, 8, 9, 10, 11, 12, 13`，共 18 个逻辑帧；第 6、7 帧为 60 ms，其余帧为 160 ms。
- 播放顺序和单帧时长由 `assets/runtime/pets/lunch_meat/desktop/animations/manifest.json` 配置，不在窗口绘制代码中硬编码。
- 桌面动画资源按宠物 ID 放在 `assets/runtime/pets/<pet_id>/desktop/animations/`；专属套装待机动画位于对应宠物动画目录的 `outfits/` 子目录。
- 生成动画时应保持透明背景、主体位置一致、画布留出防溢出像素，并让第一帧与循环结束帧自然衔接。

## 成长、Pet币与商店

### 属性和成长

小狗的基础属性是饱腹、心情和精力。属性会随时间自然变化，睡觉时会恢复精力；属性值和互动结果会保存到本地存档。好感度独立于等级成长，互动和小游戏可以增加好感，达到条件后提升好感等级。

等级通过经验提升。经验来源包括有效互动、陪伴和相关成长行为；成长卡会显示当前等级、好感、经验进度和每分钟经验。

### Pet币来源

Pet币可以通过以下方式获得：

- 完成并领取成就奖励。
- 完成金币雨或幸运爪爪小游戏并按成绩结算。
- 发现并领取桌面上的挖宝奖励。
- 升级获得等级奖励。

挖宝奖励需要等待冷却时间后才可能再次发现；奖励区间由游戏规则控制，领取后会写入 Pet币收支记录。

### 宠物

- 商店的“🐾 宠物”栏目提供午餐肉和冰淇淋。新存档默认拥有并使用午餐肉；旧存档的现有养成数据会迁移到午餐肉。
- 冰淇淋是可购买宠物，定价为原价 `1000 Pet币`、折扣 `0.76`、实际支付 `760 Pet币`。购买后会自动切换到冰淇淋，已拥有的宠物也可以在商店切换。
- 等级、经验、Pet币、家具、成就、强化和小游戏进度在宠物之间共享；饱腹、心情、精力、好感、昵称、桌面/家园位置和聊天记忆按宠物分别保存。
- 桌面和家园都会从 `assets/runtime/pets/manifest.json` 解析当前宠物，再分别读取该宠物自己的桌面或家园资源。某个动作缺少正式资源时，使用当前宠物自己的待机图回退，不借用另一只宠物的动作。
- 午餐肉的桌面待机动画和冰淇淋的现有预览/部分动作已经接入；其余正式宠物动画资源仍在补齐，待资源上传后替换回退图即可。

### 商店栏目

- **宠物**：购买或切换午餐肉、冰淇淋；宠物的角色身份与套装外观分开管理。
- **套装**：购买和装备完整桌面套装。当前包括小恐龙套装和草莓小子套装，装备后使用对应待机动画。
- **家居**：购买地毯、沙发、绿植和壁画，进入家园后拖动摆放。家居只改变视觉布置，不改变小狗的物理和属性。
- **强化**：强化温柔抚摸、营养餐、活力玩耍、香甜睡眠、成长加速和持久活力六类效果，每类最高 5 级。

购买、装备、强化、家具位置、宠物拥有状态和 Pet币余额都会保存到 `pet_state.json`。旧存档中的独立装饰数据仍会被兼容读取，但当前商店界面以宠物与完整套装为主要售卖单位。

## 家园

家园是固定在屏幕内的横向场景，小狗会在其中点击移动、四向行走、待机和自主活动。进入家园后可以通过家居商店购买家具，并在场景中拖动调整位置；背景视口会随小狗移动。

家园宠物资源与桌面宠物资源独立维护，并且都按宠物 ID 组织：

- 桌面宠物资源：`assets/runtime/pets/<pet_id>/desktop/`
- 家园宠物资源：`assets/runtime/pets/<pet_id>/home/`
- 家园背景：`assets/runtime/scenes/home/`
- 家居资源：`assets/runtime/furniture/home/`

## 小游戏

### 金币雨

在 20 秒内点击不断移动的金币。命中越多，本局奖励越高；完成后会结算 Pet币并记录小游戏局数。

### 幸运爪爪

观察金币放入哪只杯子，追踪杯子移动后选择位置。每局共 3 轮，按猜对轮数结算奖励。

### 挖宝

小狗在桌面活动期间可能发现宝藏气泡。点击后播放挖宝奖励动画并获得 Pet币；每次发现后有 20 分钟冷却，奖励由当前规则随机决定。

## AI 聊天

右键选择“聊天”或双击小狗即可打开聊天窗口。聊天模式由玩家在窗口底部明确选择，不会仅因为本机是否保存了 Key 就自动切换。

### 默认免费文字聊天

- 默认模式名称为“免费聊天 · OpenRouter Free”，默认模型标识为 `petpet-free`。
- 首次发送前会说明消息将交给 OpenRouter 的免费模型处理，确认后才会发送。
- 默认线路优先使用中国大陆可直连的阿里云函数，失败时使用 Cloudflare Worker 备用线路。
- 每个安装 ID 和来源 IP 每个 UTC 日最多各 20 次请求；单次回复最多 200 个输出 token。
- 默认线路只支持文字，不支持上传图片；额度耗尽或服务不可用时会显示明确的系统提示。

### 个人 GLM-4.6V-Flash

需要图片聊天时，选择“自己配置 API”，填写自己的智谱 Key，并选择 `GLM-4.6V-Flash`。此模式支持文字和单张 PNG、JPG/JPEG 或 WEBP 图片，单张图片最大 10 MiB。

1. 在[智谱开放平台](https://open.bigmodel.cn)创建 API Key。
2. 打开聊天窗口底部的聊天模式按钮，选择“自己配置 API”。
3. 选择 `GLM-4.6V-Flash`，填入 Key 并保存；下一条消息立即生效，无需重启。

也可以使用环境变量临时提供 Key：

```text
ZHIPU_API_KEY=你的智谱 API Key
```

环境变量优先级高于程序中保存的 Key。不要把真实 Key 写入 Git、示例配置或项目笔记。

两种模式都会在本地保存近期对话和用户画像。上传图片只会随当前消息发送给配置的智谱 API，Petpet 不会把原图 Base64 写入聊天记忆；本机仅保留聊天缩略图以便回看。

项目方默认聊天代理的部署说明见 [cloudflare-worker/README.md](cloudflare-worker/README.md)。

## 数据与隐私

Petpet 的配置、记忆和养成状态保存在用户数据目录，不进入仓库，也不会随安装包在不同电脑之间自动同步。

| 运行方式 | 数据目录 |
| --- | --- |
| Windows 源码版或打包版 | `%LOCALAPPDATA%\\Petpet` |
| macOS 源码版或打包版 | `~/Library/Application Support/Petpet` |

主要文件如下：

| 文件 | 用途 |
| --- | --- |
| `config.json` | API Key、聊天模式、免费聊天同意状态、安装 ID 和代理地址 |
| `memory.json` | AI 对话历史和用户画像 |
| `pet_state.json` | 名字、等级、属性、好感、位置、记录、成就、Pet币、套装和强化 |
| `pet_settings.json` | 界面、音效和提醒设置 |

不配置个人 Key，或不接受默认聊天说明，不会影响桌面宠物、家园、养成和其他离线功能。

## 从源码运行

建议使用 Python 3.11。源码运行需要先安装运行依赖；Windows 和 macOS 使用相同的 Python 入口 `pet.py`。

### Windows PowerShell

```powershell
Set-Location 'D:\Agent_project\Petpet'
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements\runtime.txt
python pet.py
```

也可以在已经激活虚拟环境的情况下使用无控制台解释器启动：

```powershell
Start-Process -FilePath (Get-Command pythonw.exe).Source `
    -ArgumentList 'pet.py' `
    -WorkingDirectory (Get-Location) `
    -WindowStyle Hidden
```

如果使用 `Start-Process` 提示找不到 `.venv\Scripts\pythonw.exe`，说明当前项目没有该虚拟环境，先按上面的步骤创建并激活 `.venv`，或把 `-FilePath` 改为系统中实际存在的 `pythonw.exe` 路径。

### macOS Terminal

```bash
cd /path/to/Petpet
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/runtime.txt
python pet.py
```

首次运行会创建用户数据目录。旧版本放在项目根目录的配置、记忆和状态文件会按兼容逻辑迁移到用户数据目录。

## 构建

构建产物输出到 `dist/`，中间文件输出到 `build/`；这两个目录默认不会进入 Git。打包只包含 `assets/runtime`，不会包含 `assets/source` 制作源图。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出：

```text
dist/Petpet.exe
```

### macOS

PyInstaller 不能在 Windows 上交叉生成 macOS `.app`，必须在 macOS 或 GitHub macOS Runner 上构建：

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

输出：

```text
dist/Petpet.app
```

`.github/workflows/build-macos.yml` 支持手动触发 Apple 芯片和 Intel 构建。公开分发前仍需配置 Apple Developer ID 签名和公证。

### 一键发布

发布前应先更新 `version.py`、`docs/RELEASE_NOTES_v<版本>.md` 和 README，并提交全部改动。在干净工作树中运行：

```powershell
.\scripts\release.ps1 -Version 1.5.2
```

脚本会依次检查版本和工作树、运行全量测试、编译检查、构建并冒烟验证 Windows 版本、生成 Windows 便携包和 SHA256 校验文件，然后同步 `main`、创建或继续草稿 Release，并触发 macOS 双架构工作流。

公开 Release 必须包含以下四项非空正式资产；校验和文件也会一并上传：

- `Petpet.exe`
- `Petpet-v1.5.2-windows.zip`
- `Petpet-v1.5.2-macOS-arm64.zip`
- `Petpet-v1.5.2-macOS-intel.zip`

中途失败时 Release 会保持草稿。修复问题后可以重复运行同一版本命令；脚本不会强推、覆盖已存在的标签或删除 worktree。已公开且完整的 Release 会先验证远端资产，避免重复修改。

## 项目结构

```text
Petpet/
├── pet.py                         源码、开发运行和打包启动入口
├── version.py                     唯一版本号来源
├── petpet/
│   ├── app/                       路径、存档、设置与桌面宠物控制器
│   ├── chat/                      聊天配置、传输、记忆、知识和提示词
│   ├── home/                      家园宠物、几何、渲染和窗口控制器
│   ├── progression/               成长规则、记录、成就、商店和强化
│   ├── minigames/                 金币雨、幸运爪爪和小游戏入口
│   └── ui/                        聊天、设置、教程、气泡和公共控件
├── app_paths.py 等                根目录旧模块兼容转发层
├── updater.py                     跨平台检查、下载和应用更新
├── config.json.example             安全配置模板
├── assets/
│   ├── runtime/                   唯一进入安装包的运行资源
│   │   ├── pets/<pet_id>/desktop/  当前宠物的桌面姿势、动画和套装
│   │   ├── pets/<pet_id>/home/     当前宠物的家园姿势和动画
│   │   ├── furniture/home/         家园家具
│   │   ├── scenes/home/            家园背景和反馈资源
│   │   ├── decorations/            兼容装饰资源
│   │   ├── icons/                  程序和界面图标
│   │   ├── sounds/                 互动和碰撞音效
│   │   ├── props/                  互动道具
│   │   └── knowledge/              随版本打包的玩法知识库
│   └── source/                    不进入安装包的参考图和制作源图
│       ├── references/            AI 参考图
│       └── spritesheets/           精灵表、切帧说明和制作素材
├── docs/
│   ├── RELEASE_NOTES_v*.md        各版本发布说明
│   └── superpowers/                实施方案和工程记录
├── packaging/                     Windows/macOS PyInstaller 配置
├── requirements/                  运行和构建依赖
├── scripts/                       构建、发布和资源处理脚本
├── tests/                         业务边界、GUI、资源和发布回归测试
└── tools/                         图标、音效、精灵表和聊天验证工具
```

动画素材的画布尺寸、命名、提示词、切帧方式和透明边界要求见 [assets/source/spritesheets/README.md](assets/source/spritesheets/README.md)。制作源图可以保存在 `assets/source`，但不要把它们加入打包配置。

## 常见问题

### AI 聊天没有反应

- 检查聊天窗口底部选择的是“免费聊天”还是“自己配置 API”。
- 自配模式显示“未配置”时，重新选择“自己配置 API”并填写智谱 Key。
- 使用 `ZHIPU_API_KEY` 时，确认它存在于启动 Petpet 的进程环境中。
- 检查网络是否能访问当前聊天线路或智谱开放平台。
- 免费线路达到额度或暂时不可用时，等待额度恢复或切换个人 API 模式。
- 完全退出托盘或菜单栏中的 Petpet 后再重新启动。

### 小狗不见了或没有保持置顶

点击 Windows 系统托盘或 macOS 菜单栏中的 Petpet 图标，选择显示或唤醒。v1.5.2 已增加意外隐藏后的恢复和置顶保持逻辑；若仍无法显示，先检查是否被移到屏幕边缘，再重新启动程序。

### 右键菜单第一次打开有延迟

程序启动后会预热属性卡和右键菜单，第一次启动仍可能受系统负载影响。若出现窗口卡住或程序退出，重新启动后再尝试，并保留终端输出或崩溃信息用于排查。

### Windows 源码启动找不到 pythonw.exe

先确认当前目录是项目根目录，并按“从源码运行”创建 `.venv`。`pythonw.exe` 位于虚拟环境的 `Scripts` 目录；也可以直接用 `python pet.py` 启动以查看错误输出。

### macOS 下载后无法打开

- 确认下载了与芯片匹配的 `arm64` 或 `intel` 包。
- 确认使用 Release 页面中构建产物内层的 `Petpet-v*-macOS-*.zip`。
- 对“无法验证开发者”使用“隐私与安全性 → 仍要打开”。
- 对“会损坏你的电脑”不要强行绕过，应重新下载并反馈完整提示。

### 不同 Windows 电脑上的显示大小不同

Windows 版使用 Per-Monitor V2 DPI 感知。小狗、窗口、按钮和布局使用稳定尺寸，文字会独立适配系统缩放以保持清晰。

## 更新机制

- 默认在启动约 5 秒后检查 GitHub Releases，可在“设置 → 启动时自动检查更新”中关闭。
- 也可以从托盘或右键菜单主动检查更新。
- Windows 打包版会根据 Release 资产下载 `.exe` 或 Windows ZIP，校验完成后在原安装目录替换程序并重启。
- 更新过程使用系统临时目录保存下载文件，不会覆盖 `%LOCALAPPDATA%\\Petpet` 中的名字、等级、记忆和设置。
- 源码运行模式检测到新版时会打开 GitHub Release 页面，不会覆盖项目文件。
- GitHub API 被限流时会尝试使用公开 Release 页面。

## 许可与素材

当前仓库未附带开源许可证。个人学习和个人使用可以继续使用；小狗姿势图和部分装饰图由 AI 生成，请勿直接用于商业用途。

## 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)：桌面 GUI 框架
- [智谱开放平台](https://open.bigmodel.cn)：个人 AI 对话服务
- [PyInstaller](https://pyinstaller.org)：Windows 与 macOS 应用打包
