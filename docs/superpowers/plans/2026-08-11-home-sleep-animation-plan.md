# 小屋睡眠动画接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户提供的 8 帧睡眠帧表以 `3 FPS` 接入小屋 `sleeping` 状态，同时保持固定尺寸、正确基线、缺图回退和单一阴影。

**Architecture:** `home_scene.py` 继续统一负责家园宠物素材选择和渲染，新增睡眠帧表常量、固定源矩形、独立帧时钟与 sleeping render spec。正式睡眠素材有效时直接绘制其自带接触阴影；素材为空时沿用现有方块占位与程序阴影。状态机 `home_pet.py` 不修改。

**Tech Stack:** Python 3.12、PyQt5、QPixmap/QPainter、unittest/pytest、PNG alpha 帧表。

## Global Constraints

- 工作区固定为 `D:\Agent_project\Petpet\.worktrees\home-scene-system`，分支固定为 `codex/home-scene-system`。
- 不执行 `git reset`、`git checkout`，不覆盖或回退其他未提交改动。
- 不暂存、不提交、不推送、不发布。
- 修改生产代码前先运行新增测试并确认 RED。
- 手工文本编辑统一使用 `apply_patch`；二进制素材使用精确路径复制。
- 睡眠动画固定为 `3 FPS`，走路动画继续使用 `8 FPS`。
- 前 8 格有效，第 9 格不得参与播放。
- 项目规格、计划和最终结果同步到 `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统`。

---

### Task 1: 导入并验证睡眠帧表

**Files:**
- Source: `C:\Users\sheen\Downloads\job_e8a775fa6286425e9f59859b00a3b652-transparent.png`
- Create: `assets/scenes/home/home-pet-sleep.png`
- Modify: `tests/test_packaging_assets.py`

**Interfaces:**
- Produces: 可由 `QImage` 加载、尺寸为 `1920×1920`、具有 alpha 通道的 `home-pet-sleep.png`。

- [ ] **Step 1: 写素材契约失败测试**

在 `PackagingAssetTests` 中新增：

```python
def test_home_sleep_sheet_is_an_alpha_eight_frame_grid(self):
    path = Path(__file__).resolve().parents[1] / "assets" / "scenes" / "home" / "home-pet-sleep.png"
    self.assertTrue(path.is_file())
    image = QImage(str(path))
    self.assertFalse(image.isNull())
    self.assertEqual((image.width(), image.height()), (1920, 1920))
    self.assertTrue(image.hasAlphaChannel())
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/test_packaging_assets.py::PackagingAssetTests::test_home_sleep_sheet_is_an_alpha_eight_frame_grid -q`
Expected: FAIL，项目素材尚不存在。

- [ ] **Step 3: 精确复制二进制素材**

使用 `Copy-Item -LiteralPath` 从用户下载路径复制到 `assets/scenes/home/home-pet-sleep.png`，不覆盖 `home-pet-sleep-reference.png`。

- [ ] **Step 4: 运行 GREEN**

Run: `python -m pytest tests/test_packaging_assets.py -q`
Expected: PASS。

### Task 2: 3 FPS 帧时钟与固定裁剪

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `home_scene.py`

**Interfaces:**
- Produces: `HOME_PET_SLEEP_PATH`、`HOME_PET_SLEEP_FRAME_COUNT = 8`、`HOME_PET_SLEEP_FPS = 3.0`。
- Produces: `home_pet_sleep_source_rect(frame_index) -> QRect`。
- Produces: `HomeSceneWindow.home_pet_sleep_frame(now=None) -> int`。

- [ ] **Step 1: 写帧几何和速度失败测试**

新增断言：

```python
self.assertEqual(home_scene.home_pet_sleep_source_rect(0), QRect(24, 176, 592, 288))
self.assertEqual(home_scene.home_pet_sleep_source_rect(7), QRect(664, 1456, 592, 288))
self.assertEqual(home_scene.home_pet_sleep_source_rect(8), QRect(24, 176, 592, 288))
scene.home_pet.state = "sleeping"
self.assertEqual(scene.home_pet_sleep_frame(now=0.0), 0)
self.assertEqual(scene.home_pet_sleep_frame(now=1.0 / 3.0), 1)
self.assertEqual(scene.home_pet_sleep_frame(now=8.0 / 3.0), 0)
scene.home_pet.state = "idle"
self.assertEqual(scene.home_pet_sleep_frame(now=2.0), 0)
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/test_home_scene.py -k "sleep_source_rect or sleep_frame_uses_three_fps" -q`
Expected: FAIL，睡眠帧接口尚不存在。

- [ ] **Step 3: 写最小帧实现**

在 `home_scene.py` 增加固定帧尺寸、数量、速度和内容矩形。`home_pet_sleep_source_rect()` 使用索引对 `8` 取模并按 3 列平移；`home_pet_sleep_frame()` 只在 `sleeping` 状态返回 `int(now * 3.0) % 8`。

- [ ] **Step 4: 运行 GREEN**

Run: `python -m pytest tests/test_home_scene.py -k "sleep_source_rect or sleep_frame_uses_three_fps" -q`
Expected: PASS。

### Task 3: sleeping render spec、固定尺寸和阴影回退

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `home_scene.py`

**Interfaces:**
- `HomeSceneWindow.home_pet_sleep: QPixmap`
- `home_pet_render_spec(now)` 在 sleeping 且素材有效时返回睡眠 pixmap、固定源矩形、`visual_scale=0.62`、不镜像。
- `_draw_home_pet()` 在正式睡眠 spec 存在时跳过程序阴影；spec 不存在时保留方块、`Z Z` 和程序阴影。

- [ ] **Step 1: 写 render spec 失败测试**

设置 `state="sleeping"`，断言 `home_pet_render_spec(now=1/3)` 使用 `scene.home_pet_sleep`、第 1 帧源矩形、`visual_scale=0.62`、`mirrored=False`。把 `home_pet_sleep` 设为空 `QPixmap()` 后断言返回 `None`。

- [ ] **Step 2: 写阴影行为失败测试**

把有效睡眠 pixmap 替换为同尺寸透明 `QPixmap`，在透明 `QImage` 上调用 `_draw_home_pet()`，断言正式 sleep spec 不产生程序阴影像素。再把睡眠 pixmap 设为空并重画，断言占位方块或程序阴影产生非透明像素。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/test_home_scene.py -k "sleep_render_spec or sleep_asset_skips_program_shadow" -q`
Expected: FAIL，sleeping 当前返回 `None` 并始终绘制程序阴影与占位。

- [ ] **Step 4: 写最小渲染实现**

构造器加载 `self.home_pet_sleep = QPixmap(HOME_PET_SLEEP_PATH)`。`home_pet_render_spec()` 优先处理 sleeping；素材为空返回 `None`，否则构造 sleep render spec。`_draw_home_pet()` 仅在 `render_spec is None` 或状态不是 sleeping 时绘制程序阴影。

- [ ] **Step 5: 运行 GREEN 与场景回归**

Run: `python -m pytest tests/test_home_scene.py -q`
Expected: PASS。

### Task 4: 验证、同步记录和源码重启

**Files:**
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\小屋睡眠动画接入实施计划.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\小屋睡眠动画接入设计.md`

- [ ] **Step 1: 运行 focused tests**

Run: `python -m pytest tests/test_packaging_assets.py tests/test_home_scene.py tests/test_home_pet.py tests/test_menu_ui.py -q`

- [ ] **Step 2: 运行完整验证**

Run: `python -m pytest -q`
Run: `python -m py_compile pet.py home_pet.py home_scene.py scene_system.py progression.py progression_ui.py`
Run: `git diff --check`

- [ ] **Step 3: 同步实施结果**

把素材路径、3 FPS、固定裁剪、RED/GREEN、focused 与完整测试数字写入 Obsidian；运行 `git status --short`，不暂存、不提交。

- [ ] **Step 4: 重启当前 worktree 源码**

只停止命令行包含 `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py` 的旧进程，再启动同一绝对路径并记录 PID。

## 实施结果（2026-08-11）

- 已将用户提供的 `1920×1920` 透明精灵表原样导入为 `assets/scenes/home/home-pet-sleep.png`，仅前 8 格参与播放。
- 已接入 `QRect(24, 176, 592, 288)` 统一裁剪、`3 FPS` 独立睡眠时钟、`visual_scale=0.62` 固定显示比例。
- 正式睡眠素材使用自带接触阴影，不再叠加程序椭圆；素材无效时保留方块、`Z Z` 与程序阴影回退。
- TDD RED：素材缺失测试 1 项按预期失败；帧接口测试 2 项按预期失败；render spec/阴影测试 2 项按预期失败。
- GREEN：`tests/test_packaging_assets.py` 为 `3 passed`，`tests/test_home_scene.py` 为 `65 passed`。
- 最终 focused：`136 passed in 21.50s`；全量：`304 passed in 38.72s`。
- `py_compile` 与 `git diff --check` 均以退出码 0 完成；未暂存、未提交、未推送、未发布。
- 已启动当前 worktree 的 `pet.py`，源码进程 PID 为 `29872`。
