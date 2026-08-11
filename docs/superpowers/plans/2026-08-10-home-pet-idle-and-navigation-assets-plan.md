# 家园宠物待机与图片导航实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为家园小狗加入高质量正坐待机图、固定前景尺寸、走向地毯的手动睡眠，以及由高清图片素材组成的脚印路线和目的地反馈。

**Architecture:** `home_pet.py` 继续提供不依赖 Qt 的移动和睡眠状态机；`home_scene.py` 负责素材加载、固定脚底锚点、图片导航几何及渲染；`pet.py` 只在家园激活时把快捷菜单“睡觉”委托给家园场景。四张新增透明 PNG 全部放在现有 `assets/scenes/home`，打包规则已覆盖整个场景目录。

**Tech Stack:** Python 3.12、PyQt5、unittest/pytest、Codex 内置 image generation、PNG alpha 素材。

## Global Constraints

- 工作区固定为 `D:\Agent_project\Petpet\.worktrees\home-scene-system`，分支固定为 `codex/home-scene-system`。
- 不执行 `git reset`、`git checkout`，不覆盖或回退其他未提交改动。
- 不暂存、不提交、不推送、不发布；计划中的每个“检查点”代替提交步骤。
- 修改生产代码前先运行新增测试并确认 RED，再写最小实现。
- 手工文本编辑统一使用 `apply_patch`。
- 小狗在家园任何纵向位置都使用当前前景最大缩放 `1.08` 对应的固定大小。
- 待机仅使用单张静态正坐素材；本轮不制作待机动画或正式睡眠素材。
- 路线、终点和箭头的可见外观全部来自透明 PNG，代码只负责排列、旋转、缩放、透明度和动画。
- 项目规格、计划和最终实现记录必须同步到 `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统`。

---

## 文件结构

- Create: `assets/scenes/home/home-pet-idle-sit.png` — 正坐待机小狗。
- Create: `assets/scenes/home/home-nav-paw.png` — 单枚路线脚印。
- Create: `assets/scenes/home/home-nav-target.png` — 倾斜椭圆目的地。
- Create: `assets/scenes/home/home-nav-arrow.png` — 可爱向下箭头。
- Modify: `home_pet.py` — 手动睡眠行走状态和通用路线采样几何。
- Modify: `home_scene.py` — 素材加载、固定尺寸、待机渲染、家园睡眠入口和图片导航渲染。
- Modify: `pet.py` — 家园激活时委托 `toggle_sleep()`。
- Modify: `tests/test_packaging_assets.py` — 新素材存在、PNG 和 alpha 契约。
- Modify: `tests/test_home_pet.py` — 手动睡眠状态与脚印采样。
- Modify: `tests/test_home_scene.py` — 固定尺寸、待机素材、图片导航和场景睡眠生命周期。
- Modify: `tests/test_menu_ui.py` — 快捷菜单睡眠委托。
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园宠物待机与图片导航设计.md` — 最终结果和验证记录。

---

### Task 1: 建立并生成四张高清透明素材

**Files:**
- Create: `assets/scenes/home/home-pet-idle-sit.png`
- Create: `assets/scenes/home/home-nav-paw.png`
- Create: `assets/scenes/home/home-nav-target.png`
- Create: `assets/scenes/home/home-nav-arrow.png`
- Modify: `tests/test_packaging_assets.py`

**Interfaces:**
- Consumes: `assets/scenes/home/home-pet-walk-down.png`、`home-pet-walk-back-right.png` 和 `home-background.png` 作为角色与场景画风参考。
- Produces: 四个可由 `QPixmap(path)` 加载、带透明通道且透明四角的 PNG 文件。

- [x] **Step 1: 写素材契约失败测试**

在 `tests/test_packaging_assets.py` 增加：

```python
from PyQt5.QtGui import QImage

def test_home_pet_idle_and_navigation_assets_are_transparent_pngs(self):
    root = Path(__file__).resolve().parents[1]
    asset_dir = root / "assets" / "scenes" / "home"
    for name in (
        "home-pet-idle-sit.png",
        "home-nav-paw.png",
        "home-nav-target.png",
        "home-nav-arrow.png",
    ):
        path = asset_dir / name
        self.assertTrue(path.is_file(), name)
        image = QImage(str(path))
        self.assertFalse(image.isNull(), name)
        self.assertTrue(image.hasAlphaChannel(), name)
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0, name)
        self.assertGreater(image.width(), 128, name)
        self.assertGreater(image.height(), 128, name)
```

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_packaging_assets.py::PackagingAssetTests::test_home_pet_idle_and_navigation_assets_are_transparent_pngs -q`
Expected: FAIL，四张文件尚不存在。

- [x] **Step 3: 使用 image generation 逐张生成素材**

待机图使用两张现有行走图作为身份参考；三个 UI 素材使用家园背景作为调色参考。每个输出单独生成，不用一个大图切割。内置图像工具先生成纯色键控背景，随后用 imagegen skill 的 `remove_chroma_key.py` 去背；如果蓬松毛发边缘无法通过透明验证，停止并征求用户是否使用原生透明 CLI fallback。

待机图核心提示词：

```text
Use case: stylized-concept
Asset type: in-game home pet idle sprite
Primary request: the exact same cream-golden fluffy puppy from the references, sitting upright and still, front view turned slightly to the viewer's right
Style/medium: high-quality soft hand-painted children's storybook game art
Composition: full body, front paws naturally together, clear ground-contact baseline, centered with generous padding
Constraints: preserve face, eyes, ears, coat color and proportions; no floor, no shadow, no text, no watermark
Background: perfectly flat removable chroma key color
```

脚印、终点和箭头分别按设计规格生成；不得带文字、水印、棋盘格或环境背景。

- [x] **Step 4: 保存到项目并视觉检查**

将最终 alpha PNG 保存为四个约定路径。使用 `view_image` 检查身份一致性、完整边缘、无背景残留、无素材内投影；使用 QImage 或 Pillow 检查透明四角和非透明主体覆盖率。

- [x] **Step 5: 运行素材测试确认 GREEN**

Run: `python -m pytest tests/test_packaging_assets.py -q`
Expected: PASS。

- [x] **Step 6: 检查点**

运行 `git status --short assets/scenes/home tests/test_packaging_assets.py`，确认只新增四张目标素材和预期测试；不执行 git add/commit。

---

### Task 2: 扩展手动睡眠状态机与脚印采样

**Files:**
- Modify: `home_pet.py`
- Modify: `tests/test_home_pet.py`

**Interfaces:**
- Produces: `HomePetController.request_manual_sleep(target: Point, now: float) -> bool`。
- Produces: `HomePetController.advance(dt)` 在手动睡眠抵达时返回 `("arrived", "manual_sleep_started")`。
- Produces: `route_footprints(start: Point, end: Point, spacing: float = 42.0, lateral_offset: float = 6.0) -> tuple[dict[str, float | bool], ...]`，每项包含 `x`、`y`、`angle`、`mirrored`。

- [x] **Step 1: 写手动睡眠和脚印采样失败测试**

```python
def test_manual_sleep_walk_emits_distinct_arrival_event(self):
    pet = home_pet.HomePetController((500.0, 600.0), walk_speed=100.0)
    self.assertTrue(pet.request_manual_sleep((510.0, 600.0), now=10.0))
    self.assertEqual(pet.state, "manual_sleep_walk")
    self.assertEqual(
        pet.advance(1.0),
        ("arrived", "manual_sleep_started"),
    )
    self.assertEqual(pet.state, "sleeping")

def test_route_footprints_shorten_and_alternate(self):
    full = home_pet.route_footprints((100.0, 100.0), (400.0, 100.0))
    short = home_pet.route_footprints((250.0, 100.0), (400.0, 100.0))
    self.assertGreater(len(full), len(short))
    self.assertGreater(len(full), 2)
    self.assertNotEqual(full[0]["mirrored"], full[1]["mirrored"])
    self.assertAlmostEqual(full[0]["angle"], 0.0)
```

同时扩展现有打断和取消测试，要求 `manual_sleep_walk` 可被 `command_move()` 打断并由 `cancel_target()` 回到 `idle`。

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_home_pet.py -q`
Expected: FAIL，缺少 `request_manual_sleep`、`manual_sleep_walk` 和 `route_footprints`。

- [x] **Step 3: 实现最小状态机**

```python
def request_manual_sleep(self, target: Point, now: float) -> bool:
    if self.state != "idle":
        return False
    normalized = clamp_to_walkable(target)
    dx = normalized[0] - self.position[0]
    dy = normalized[1] - self.position[1]
    self.target = normalized
    self.direction = direction_for_delta(dx, dy, self.direction)
    self.state = "manual_sleep_walk"
    return True
```

把 `manual_sleep_walk` 加入 `advance()`、`command_move()` 中断集合和 `cancel_target()` 集合；抵达时设置 `sleeping` 并返回独立事件。实现纯数学 `route_footprints()`，第一枚脚印与起点保持半个间距，终点前保留空间给目的地素材。

- [x] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_home_pet.py -q`
Expected: PASS。

- [x] **Step 5: 检查点**

运行 `python -m py_compile home_pet.py` 和 `git diff --check -- home_pet.py tests/test_home_pet.py`；不提交。

---

### Task 3: 接入正坐待机素材和固定前景尺寸

**Files:**
- Modify: `home_scene.py`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: `HOME_PET_IDLE_PATH` 与 Task 1 的 `home-pet-idle-sit.png`。
- Produces: `HOME_PET_FIXED_DEPTH_SCALE = 1.08`。
- Produces: `HomeSceneWindow.home_pet_render_spec(now=None)`，在 `idle` 返回待机图，在行走状态返回对应动画帧，素材缺失时回退前向第 0 帧。
- Changes: `home_pet_draw_rect(visual_scale=1.0)` 的尺寸不再依赖世界 `y`。

- [x] **Step 1: 修改深度缩放测试为固定尺寸，并新增待机素材测试**

```python
def test_home_pet_draw_rect_keeps_foreground_size_at_every_depth(self):
    scene.home_pet.position = (900.0, 460.0)
    far_rect = scene.home_pet_draw_rect()
    scene.home_pet.position = (900.0, 730.0)
    near_rect = scene.home_pet_draw_rect()
    self.assertEqual(far_rect.size(), near_rect.size())
    self.assertAlmostEqual(far_rect.bottom(), 460.0)
    self.assertAlmostEqual(near_rect.bottom(), 730.0)

def test_idle_uses_dedicated_sitting_art_and_falls_back_to_walk_frame(self):
    scene.home_pet.state = "idle"
    spec = scene.home_pet_render_spec(now=0.0)
    self.assertEqual(spec.pixmap.cacheKey(), scene.home_pet_idle.cacheKey())
    scene.home_pet_idle = QPixmap()
    fallback = scene.home_pet_render_spec(now=0.0)
    self.assertEqual(fallback.frame_index, 0)
```

更新现有行走渲染测试，使 `manual_sleep_walk` 也播放动画。

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_home_scene.py -k "draw_rect or idle or render_spec" -q`
Expected: FAIL，尺寸仍随深度变化且待机素材接口不存在。

- [x] **Step 3: 加载素材并实现统一 render spec**

在路径常量区增加 `HOME_PET_IDLE_PATH`，构造函数加载 `self.home_pet_idle`。将尺寸公式改为：

```python
scale = HOME_PET_FIXED_DEPTH_SCALE
width = 512.0 * 0.23 * scale * visual_scale
height = 464.0 * 0.23 * scale * visual_scale
```

新增 `home_pet_render_spec()`，空闲时优先返回完整待机图；`manual_walk`、`manual_sleep_walk`、`auto_sleep_walk` 才计算动画帧。`_draw_home_pet()` 和命中矩形统一读取新 render spec。

- [x] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_home_scene.py -k "draw_rect or idle or render_spec or hit_rect or global_rect" -q`
Expected: PASS。

- [x] **Step 5: 检查点**

Run: `python -m py_compile home_scene.py`
Run: `git diff --check -- home_scene.py tests/test_home_scene.py`

---

### Task 4: 让快捷菜单睡觉委托给家园场景

**Files:**
- Modify: `pet.py`
- Modify: `home_scene.py`
- Modify: `tests/test_menu_ui.py`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Produces: `HomeSceneWindow.toggle_home_sleep(now=None) -> bool`。
- Consumes: `HomePetController.request_manual_sleep()` 和 `home_sleep_target()`。
- Changes: `PetWindow.toggle_sleep()` 在 `_active_home_interface()` 返回活动家园时调用 `home.toggle_home_sleep()` 并立即返回。

- [x] **Step 1: 写菜单委托和场景睡眠失败测试**

```python
def test_toggle_sleep_delegates_to_active_home(self):
    home = SimpleNamespace(toggle_home_sleep=Mock(return_value=True))
    harness = SimpleNamespace(_active_home_interface=lambda: home)
    pet.PetWindow.toggle_sleep(harness)
    home.toggle_home_sleep.assert_called_once_with()

def test_home_manual_sleep_walks_to_rug_before_setting_shared_sleep(self):
    scene.home_pet.position = (600.0, 600.0)
    target = scene.home_sleep_target()
    self.assertTrue(scene.toggle_home_sleep(now=10.0))
    self.assertEqual(scene.home_pet.state, "manual_sleep_walk")
    self.assertEqual(scene.home_pet.target, target)
    self.assertFalse(scene.state["sleeping"])
    self.assertEqual(scene._manual_destination, target)
```

再加到达测试：`manual_sleep_started` 后设置 `sleeping=True`、`sleep_mode="manual"`、调用 `progression.record_sleep(..., "manual")`；精力恢复不自动唤醒。增加已睡眠再次调用后原地醒来的测试。

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_menu_ui.py tests/test_home_scene.py -k "toggle_sleep or manual_sleep" -q`
Expected: FAIL，尚无委托入口和手动睡眠场景方法。

- [x] **Step 3: 实现场景入口和事件同步**

`toggle_home_sleep()`：装修或不可见时返回 `False`；已睡眠则原地唤醒、清理共享状态并保存；醒着且空闲时调用 `request_manual_sleep(home_sleep_target(), now)`，把目标写入 `_manual_destination` 并保持共享 `sleeping=False`。

在 `_advance_home_pet()` 中分别处理：

```python
if "manual_sleep_started" in events:
    self.state["sleeping"] = True
    self.state["sleep_mode"] = "manual"
    progression.record_sleep(self.state, "manual")
elif "sleep_started" in events:
    self.state["sleeping"] = True
    self.state["sleep_mode"] = "auto"
```

`PetWindow.toggle_sleep()` 只在活动家园存在时委托；屋外路径保持原逻辑。

- [x] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_menu_ui.py tests/test_home_scene.py -k "toggle_sleep or manual_sleep or auto_sleep" -q`
Expected: PASS。

- [x] **Step 5: 检查点**

运行 `python -m py_compile pet.py home_scene.py` 和相关 `git diff --check`；不提交。

---

### Task 5: 用图片素材渲染脚印路线、椭圆终点和箭头

**Files:**
- Modify: `home_scene.py`
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: `route_footprints()` 和 Task 1 三张导航 PNG。
- Extends: `navigation_feedback(now=None)` 返回 `footprints`、`target_rect`、`arrow_rect`、`arrow_offset`、`opacity`。
- Produces: `_draw_navigation_pixmap(painter, pixmap, rect, rotation=0.0, mirrored=False, opacity=1.0)`，只做图片变换与绘制。

- [x] **Step 1: 写图片导航几何和绘制失败测试**

```python
def test_navigation_feedback_uses_fixed_image_geometry_and_footprints(self):
    scene.home_pet.position = (600.0, 600.0)
    scene._manual_destination = (900.0, 600.0)
    feedback = scene.navigation_feedback(now=10.0)
    self.assertGreater(len(feedback["footprints"]), 1)
    self.assertAlmostEqual(
        feedback["target_rect"].width() / feedback["target_rect"].height(),
        2.1,
        places=1,
    )
    self.assertNotEqual(feedback["arrow_rect"], feedback["target_rect"])
    self.assertNotIn("depth_scale", feedback)
```

更新像素测试：路线中点附近有脚印像素，终点矩形和箭头矩形各自有 alpha；将三张导航 pixmap 置空后移动逻辑仍能前进且不抛异常。

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_home_scene.py -k "navigation" -q`
Expected: FAIL，反馈仍返回虚线路径和圆形程序绘制标记。

- [x] **Step 3: 加载导航素材并返回固定几何**

构造函数加载 `self.home_nav_paw`、`self.home_nav_target`、`self.home_nav_arrow`。在 `navigation_feedback()` 中调用 `route_footprints()`，把世界坐标转换成画布坐标；使用固定目标宽高（例如 `58x28`）和固定脚印显示尺寸（例如 `18x22`），箭头浮动为 `2.5 * sin(...)`，呼吸缩放保持约 `±4%`。

- [x] **Step 4: 替换程序绘制外观**

删除虚线、`drawEllipse()` 和 `QPainterPath` 箭头外观。`_draw_navigation_feedback()` 只循环绘制脚印图片，再绘制 target 和 arrow 图片。统一乘以到达淡出 `opacity`，使用 `Qt.SmoothTransformation` 或 painter smooth pixmap transform。

- [x] **Step 5: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_home_scene.py -k "navigation" -q`
Expected: PASS。

- [x] **Step 6: 检查点**

Run: `python -m py_compile home_scene.py home_pet.py`
Run: `git diff --check -- home_scene.py home_pet.py tests/test_home_scene.py tests/test_home_pet.py`

---

### Task 6: 完整回归、源码验收和 Obsidian 同步

**Files:**
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\家园宠物待机与图片导航设计.md`

**Interfaces:**
- Consumes: Tasks 1–5 的最终代码、素材和测试结果。
- Produces: 可复核的验证数字、手工验收清单和 Obsidian 实现记录。

- [x] **Step 1: 运行 focused tests**

Run:

```powershell
python -m pytest tests/test_packaging_assets.py tests/test_home_pet.py tests/test_home_scene.py tests/test_menu_ui.py tests/test_scene_system.py -q
```

Expected: 全部 PASS，零失败。

- [x] **Step 2: 运行完整测试**

Run: `python -m pytest -q`
Expected: 全部 PASS，零失败。

- [x] **Step 3: 静态检查**

Run: `python -m py_compile pet.py home_pet.py home_scene.py scene_system.py progression.py progression_ui.py`
Run: `git diff --check`
Expected: exit code 0；允许已有 LF/CRLF 提示，但不允许 whitespace error。

- [x] **Step 4: 启动精确 worktree 源码**

仅停止命令行包含精确路径 `D:\Agent_project\Petpet\.worktrees\home-scene-system\pet.py` 的旧 Python 进程，再从该 worktree 隐藏启动 `pythonw pet.py`。不得启动其他目录源码。

- [ ] **Step 5: 手工验收**

检查：静态正坐待机、上下位置固定大小、脚印路线、椭圆终点、箭头动画、快捷菜单走向地毯睡眠、无地毯回退、自动睡眠无路线、装修和退出清理。

- [x] **Step 6: 同步 Obsidian**

用 `apply_patch` 在 Obsidian 设计笔记追加：四张素材路径与最终提示词、代码接口、RED/GREEN 过程、focused/full 测试数字、静态检查结果和未完成的手工验收项。

- [x] **Step 7: 最终状态审计**

Run: `git status --short` 和 `git diff --stat`。报告本轮文件，不暂存、不提交、不推送。
