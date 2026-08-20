# 家园固定脚印路线与对话气泡适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复会随小狗重排的脚印路线，缩小终点反馈，并为小屋提供更高、更协调的专属对话气泡。

**Architecture:** `home_scene.py` 在每次手动指令建立时保存世界坐标路线快照，渲染时依据小狗沿原路线的投影进度过滤已走过脚印。`pet.py` 的 `SpeechBubble` 复用现有家园活动接口，仅对小屋定位和绘制主题做条件分支，不改变室外行为。

**Tech Stack:** Python 3.12、PyQt5、unittest/pytest、QPainter、QPixmap。

## Global Constraints

- 工作区固定为 `D:\Agent_project\Petpet\.worktrees\home-scene-system`，分支固定为 `codex/home-scene-system`。
- 不执行 `git reset`、`git checkout`，不覆盖或回退其他未提交改动。
- 不暂存、不提交、不推送、不发布；任务结束只报告状态。
- 修改生产代码前必须先运行新增测试并确认 RED。
- 手工文本编辑统一使用 `apply_patch`。
- 项目规格、计划和最终结果同步到 `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统`。
- 启动源码时只运行当前 worktree 的 `pet.py`。

---

### Task 1: 固定世界坐标脚印路线

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `home_scene.py`

**Interfaces:**
- Produces: `HomeSceneWindow._manual_route`，包含 `start`、`end`、`footprints`。
- Produces: `HomeSceneWindow._set_manual_destination(target)`，原子设置目标、路线快照与淡出状态。
- Consumes: `route_footprints(start, end)` 的 `x`、`y`、`angle`、`mirrored`。

- [x] **Step 1: 写固定路线失败测试**

在 `tests/test_home_scene.py` 中把原“路线随剩余距离重新缩短”用例改为：先建立一次真实手动指令并记录所有脚印，再移动小狗；断言第二次反馈的脚印是第一次脚印的严格后缀，剩余元素的中心、角度和镜像与首次结果完全相同。

- [x] **Step 2: 写新指令替换快照失败测试**

先向右建立目标并保存 `_manual_route`，再向左建立新目标；断言快照的 `start`、`end` 和脚印序列全部属于第二条路线，旧终点不再出现在反馈中。

- [x] **Step 3: 运行 RED**

Run: `python -m pytest tests/test_home_scene.py -k "navigation_feedback_path or replaces_route" -q`
Expected: FAIL；当前实现会重采样路线且不存在固定快照。

- [x] **Step 4: 写最小实现**

在 `HomeSceneWindow` 中初始化 `_manual_route = None`；集中实现目标设置和清理。设置目标时调用一次 `route_footprints()` 并将返回值冻结为 tuple。反馈阶段用点积投影计算小狗进度，仅过滤投影进度已被小狗覆盖的脚印，不修改剩余脚印的数据。

- [x] **Step 5: 运行 GREEN 与回归**

Run: `python -m pytest tests/test_home_scene.py -k "navigation" -q`
Expected: PASS。

### Task 2: 缩小终点椭圆与箭头

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `home_scene.py`

**Interfaces:**
- `navigation_feedback(now)` 的 `target_rect` 基础高度约 `24px`。
- `arrow_rect` 继续与目标分离并保持素材比例。

- [x] **Step 1: 写几何失败测试**

在呼吸缩放相位可确定的时间点断言 `target_rect.height()` 约为 `24px`，且 `width / height` 仍接近素材的 `2.1:1`；断言箭头基础高度小于旧值 `31px`。

- [x] **Step 2: 运行 RED**

Run: `python -m pytest tests/test_home_scene.py -k "fixed_image_geometry" -q`
Expected: FAIL；当前椭圆基础高度为 `30px`。

- [x] **Step 3: 写最小实现并运行 GREEN**

将椭圆基础高度改为 `24.0`，箭头基础高度改为 `27.0`，按素材宽高比计算宽度并微调两者间距。

Run: `python -m pytest tests/test_home_scene.py -k "navigation" -q`
Expected: PASS。

### Task 3: 小屋专属对话气泡

**Files:**
- Modify: `tests/test_speech_bubble.py`
- Modify: `pet.py`

**Interfaces:**
- Produces: `SpeechBubble._uses_home_theme() -> bool`。
- `_bubble_geometry(width, height)` 在小屋状态额外上移 `24px`，之后进行屏幕裁剪。
- `paintEvent()` 根据主题选择室外或小屋调色板。

- [x] **Step 1: 写定位失败测试**

创建可切换活动家园接口、但保持相同锚点与屏幕矩形的真实 QWidget host；分别取得室外和小屋气泡几何，断言小屋 `top()` 比室外小 `24`，左右位置和尺寸不变。

- [x] **Step 2: 写主题渲染失败测试**

抓取室外与小屋气泡图像，在气泡主体中央比较颜色；断言小屋主题更接近奶油纸张与浅桃木色，并且与室外像素不同，同时两者 alpha 均非零。

- [x] **Step 3: 运行 RED**

Run: `python -m pytest tests/test_speech_bubble.py -q`
Expected: FAIL；当前没有小屋偏移或专属主题。

- [x] **Step 4: 写最小实现**

通过调用 host 的 `_active_home_interface()` 判断是否启用小屋主题；定位先应用 `-24px` 偏移再执行现有屏幕裁剪。绘制层只分支颜色、圆角与柔和阴影参数，保留完整清屏、文字换行、队列和尾巴逻辑。

- [x] **Step 5: 运行 GREEN 与回归**

Run: `python -m pytest tests/test_speech_bubble.py tests/test_menu_ui.py -q`
Expected: PASS。

### Task 4: 验证、记录和源码重启

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园固定脚印路线与对话气泡适配实施计划.md`

- [x] **Step 1: 运行 focused tests**

Run: `python -m pytest tests/test_home_pet.py tests/test_home_scene.py tests/test_speech_bubble.py tests/test_menu_ui.py -q`

- [x] **Step 2: 运行完整验证**

Run: `python -m pytest -q`
Run: `python -m py_compile pet.py home_pet.py home_scene.py scene_system.py progression.py progression_ui.py`
Run: `git diff --check`

- [x] **Step 3: 同步结果与检查状态**

把 RED/GREEN、focused 与全量测试数字、编译检查和人工验收项写入 Obsidian；运行 `git status --short` 和 `git diff --stat`，不暂存、不提交。

- [x] **Step 4: 重启准确源码**

只停止命令行包含当前 worktree 绝对 `pet.py` 路径的旧 Python 进程，再以该绝对路径启动源码，记录 PID 供用户验收。

结果：当前 worktree 源码已重启，`pythonw.exe` PID 为 `30216`。
