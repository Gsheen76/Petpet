# 家园待机稳定与睡眠尺寸 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除午餐肉和冰淇淋家园待机的逐帧左右抖动，并把两只宠物的家园睡眠显示比例统一为 `0.50`。

**Architecture:** 在纯渲染层用 Qt 原生阈值 alpha mask 计算一组动画帧的稳定联合边界；家园窗口按宠物 ID 与动画名缓存该边界，所有共享动画帧复用同一源矩形。睡眠状态优先使用当前宠物注册的家园睡眠素材，并在既有脚底锚定矩形中应用固定 `0.50` 比例。

**Tech Stack:** Python 3.12、PyQt5 5.15、QImage/QBitmap/QRegion、unittest/pytest、Obsidian CLI 1.13.7

## Global Constraints

- 不修改任何 PNG 资源，不增加 Pillow、NumPy 或其他运行依赖。
- 不改变桌面动画、家园走路帧、世界坐标脚底锚点和走路接触阴影数据。
- 同一宠物、同一动画的所有帧必须使用同一个源矩形。
- Qt 阈值遮罩必须忽略 alpha 值为 1 的边缘残点。
- 两只宠物睡眠必须使用各自注册的家园睡眠素材，`visual_scale` 固定为 `0.50`。
- 宠物或资源切换必须清空家园动画源矩形缓存。
- 仅修改任务所需源码、测试、设计/计划及 Obsidian 记录；保留任务开始前的未跟踪 `.superpowers` 目录。

---

### Task 1: Qt 原生稳定联合边界

**Files:**
- Modify: `petpet/home/rendering.py:8-220`
- Modify: `tests/test_home_scene.py:1-65`

**Interfaces:**
- Consumes: `QPixmap.toImage() -> QImage`、`QImage.createAlphaMask(Qt.ThresholdDither) -> QImage`
- Produces: `home_pet_animation_source_rect(frames) -> QRect`

- [ ] **Step 1: 写入联合边界失败测试**

在 `tests/test_home_scene.py` 的静态边界测试后增加：

```python
def test_animation_source_rect_unites_threshold_alpha_bounds(self):
    first_image = QImage(100, 80, QImage.Format_ARGB32)
    first_image.fill(Qt.transparent)
    first_image.setPixelColor(0, 0, QColor(255, 255, 255, 1))
    painter = QPainter(first_image)
    painter.fillRect(QRect(20, 10, 30, 40), Qt.white)
    painter.end()

    second_image = QImage(100, 80, QImage.Format_ARGB32)
    second_image.fill(Qt.transparent)
    painter = QPainter(second_image)
    painter.fillRect(QRect(40, 20, 30, 40), Qt.white)
    painter.end()

    rect = home_scene.home_pet_animation_source_rect(
        [QPixmap.fromImage(first_image), QPixmap.fromImage(second_image)]
    )

    self.assertEqual(rect, QRect(20, 10, 50, 50))
    self.assertEqual(home_scene.home_pet_animation_source_rect([]), QRect())
```

同时在测试导入中加入 `QColor`。这个测试抓住的生产缺陷是：helper 尚不存在，且现有 `QPixmap.mask()` 会把 `(0, 0)` 的 alpha 1 残点纳入边界。

- [ ] **Step 2: 运行单测确认 RED**

Run:

```powershell
python -m pytest tests/test_home_scene.py::HomeSceneAssetTests::test_animation_source_rect_unites_threshold_alpha_bounds -q
```

Expected: FAIL，提示 `home_pet_animation_source_rect` 不存在。

- [ ] **Step 3: 实现最小联合边界 helper**

在 `petpet/home/rendering.py` 中为 QtGui 导入加入 `QBitmap`，并在 `home_pet_static_source_rect()` 后增加：

```python
def home_pet_animation_source_rect(frames) -> QRect:
    """Return one thresholded alpha crop shared by an animation sequence."""

    visible_union = QRect()
    fallback = QRect()
    for pixmap in frames or ():
        if pixmap is None or pixmap.isNull():
            continue
        if fallback.isEmpty():
            fallback = home_pet_static_source_rect(pixmap)
        alpha_mask = pixmap.toImage().createAlphaMask(Qt.ThresholdDither)
        visible = QRegion(QBitmap.fromImage(alpha_mask)).boundingRect()
        if visible.isEmpty():
            continue
        visible_union = (
            visible
            if visible_union.isEmpty()
            else visible_union.united(visible)
        )
    return visible_union if not visible_union.isEmpty() else fallback
```

- [ ] **Step 4: 运行 helper 测试确认 GREEN**

Run:

```powershell
python -m pytest tests/test_home_scene.py::HomeSceneAssetTests::test_animation_source_rect_unites_threshold_alpha_bounds -q
```

Expected: `1 passed`。

- [ ] **Step 5: 提交纯渲染边界**

```powershell
git add petpet/home/rendering.py tests/test_home_scene.py
git commit -m "fix: stabilize home animation alpha bounds"
```

### Task 2: 家园共享动画缓存与睡眠比例

**Files:**
- Modify: `petpet/home/rendering.py:31-45`
- Modify: `petpet/home/window.py:45-260,880-960`
- Modify: `tests/test_home_scene.py:130-285`

**Interfaces:**
- Consumes: `home_pet_animation_source_rect(frames) -> QRect`、`PetWindow.animation_frames: dict[str, list[QPixmap]]`
- Produces: `HomeSceneWindow._shared_animation_source_rect(shared: dict) -> QRect`、`HOME_PET_SLEEP_VISUAL_SCALE = 0.50`

- [ ] **Step 1: 写入共享待机稳定性失败测试**

构造两张主体横向位置不同的动画帧，让 `shared_animation_frame()` 先后返回不同帧，但 `animation_frames["idle"]` 暴露完整序列：

```python
def test_shared_idle_frames_keep_one_cached_render_rect(self):
    frames = []
    for body in (QRect(20, 10, 40, 80), QRect(30, 10, 40, 80)):
        pixmap = QPixmap(100, 100)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(body, Qt.white)
        painter.end()
        frames.append(pixmap)

    current = {"index": 0}
    state = progression.ensure_progression({"active_pet_id": "ice_cream"})
    pet = SimpleNamespace(
        state=state,
        width=lambda: 190,
        height=lambda: 220,
        current_screen_rect=lambda: QRect(0, 0, 1920, 1080),
        animation_frames={"idle": frames},
        shared_animation_frame=lambda: {
            "name": "idle",
            "pixmap": frames[current["index"]],
            "frame_index": current["index"],
            "spec": {},
        },
    )
    scene = home_scene.HomeSceneWindow(pet, Mock())
    self.addCleanup(scene.close)
    scene.home_pet.state = "idle"

    first_spec = scene.home_pet_render_spec(now=0.0)
    first_rect = scene.home_pet_render_rect(first_spec)
    current["index"] = 1
    second_spec = scene.home_pet_render_spec(now=0.1)
    second_rect = scene.home_pet_render_rect(second_spec)

    self.assertEqual(first_spec.source_rect, QRect(20, 10, 50, 80))
    self.assertEqual(second_spec.source_rect, first_spec.source_rect)
    self.assertEqual(second_rect, first_rect)
```

当前代码会分别返回 `QRect(20, 10, 40, 80)` 与 `QRect(30, 10, 40, 80)`，测试必须按预期失败。

- [ ] **Step 2: 写入睡眠优先级和尺寸失败测试**

扩展现有 `test_sleeping_uses_the_sleep_sheet_and_falls_back_when_it_is_missing`，让 fake pet 同时提供一个非空 `shared_animation_frame()`，并断言家园睡眠素材仍胜出；把比例断言更新为 `0.50`，再验证目标尺寸：

```python
self.assertEqual(spec.visual_scale, 0.50)
rect = scene.home_pet_render_rect(spec)
self.assertAlmostEqual(rect.width(), 118.46, places=2)
self.assertAlmostEqual(rect.height(), 57.63, places=2)
```

当前共享帧分支会提前返回 fake 桌面帧，且原专用睡眠分支仍为 `0.62`，测试必须按行为差异失败。

- [ ] **Step 3: 运行家园焦点测试确认 RED**

Run:

```powershell
python -m pytest tests/test_home_scene.py -q
```

Expected: 新增的待机稳定测试和更新后的睡眠测试失败；其他既有测试保持通过。

- [ ] **Step 4: 增加缓存和稳定源矩形选择**

在 `HomeSceneWindow.__init__()` 初始化：

```python
self._home_pet_animation_source_rects = {}
```

在 `refresh_pet_assets()` 开头清空该字典。增加：

```python
def _shared_animation_source_rect(self, shared):
    name = str(shared.get("name", "idle"))
    key = (self.current_pet_id, name)
    cached = self._home_pet_animation_source_rects.get(key)
    if cached is not None:
        return cached
    frames = getattr(self.pet, "animation_frames", {}).get(name, ())
    source_rect = home_pet_animation_source_rect(frames)
    if source_rect.isEmpty():
        source_rect = home_pet_static_source_rect(shared["pixmap"])
    self._home_pet_animation_source_rects[key] = QRect(source_rect)
    return source_rect
```

把共享动画 `HomePetWalkRenderSpec` 的 `source_rect` 改为调用该方法。不要改变 `world_x/world_y`、contact 数据或 `home_pet_draw_rect()`。

- [ ] **Step 5: 让家园睡眠优先并应用 0.50**

在 `petpet/home/rendering.py` 增加：

```python
HOME_PET_SLEEP_VISUAL_SCALE = 0.50
```

把 `home_pet_render_spec()` 的睡眠分支移动到共享动画分支之前，并把 spritesheet 的 `visual_scale` 改为：

```python
visual_scale=(
    HOME_PET_SLEEP_VISUAL_SCALE
    if self._home_pet_sleep_is_sheet
    else 1.0
)
```

保持睡眠素材缺失时返回 `None`，保持 `_draw_home_pet()` 对 authored sleep 不画额外阴影。

- [ ] **Step 6: 运行家园焦点测试确认 GREEN**

Run:

```powershell
python -m pytest tests/test_home_scene.py tests/test_pet_window_boundary.py -q
```

Expected: 全部通过，无 Qt warning 或异常。

- [ ] **Step 7: 提交家园集成**

```powershell
git add petpet/home/rendering.py petpet/home/window.py tests/test_home_scene.py
git commit -m "fix: steady home idle and resize sleep"
```

### Task 3: 两只宠物验证、Obsidian 与重启

**Files:**
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\2026-08-21 家园待机稳定与睡眠尺寸修复.md`
- Verify: `assets/runtime/pets/lunch_meat/desktop/animations/idle/*.png`
- Verify: `assets/runtime/pets/ice_cream/desktop/animations/idle/*.png`

**Interfaces:**
- Consumes: Task 1/2 的稳定联合边界、缓存和 `HOME_PET_SLEEP_VISUAL_SCALE`
- Produces: 两只宠物的真实资源验收证据、Obsidian 可追溯记录与运行中的源码进程

- [ ] **Step 1: 运行两只宠物真实资源诊断**

使用真实 `PetWindow` 和 `HomeSceneWindow`，分别选择 `lunch_meat` 与 `ice_cream`，遍历全部已加载待机帧。对每只宠物收集 `source_rect` 与 `home_pet_render_rect()`，断言：

```python
assert len(set(source_rect_tuples)) == 1
assert len(set(render_rect_tuples)) == 1
```

同时打印每只宠物统一源矩形、运行时帧尺寸、最终待机宽高和睡眠宽高。直接分析 640px 原始资源时，午餐肉阈值联合边界约为 `(111, 77, 342, 514)`，冰淇淋约为 `(83, 88, 408, 458)`；`PetWindow` 加载后的 384px 帧应得到等比例边界。睡眠约为 `118.46×57.63px`。

- [ ] **Step 2: 运行完整验证**

Run:

```powershell
python -m pytest -q
python -m py_compile pet.py petpet\home\rendering.py petpet\home\window.py
git diff --check
```

Expected: pytest 0 failures，编译与 diff 检查退出码均为 0。

- [ ] **Step 3: 写入开发记录并使用 Obsidian CLI 验证**

使用 `apply_patch` 创建带 frontmatter、wikilink、`[!bug]` 与 `[!success]` callout 的开发记录，随后通过 `D:\Program Files\Obsidian\Obsidian.com` 连接 `My-Obsidian` vault 验证。记录包含：

- 两只宠物原始抖动量；
- alpha 1 残点与逐帧裁剪根因；
- Qt 阈值联合边界和缓存策略；
- 睡眠 `0.50` 与最终宽高；
- RED/GREEN、真实资源和全量测试结果；
- 设计、计划和实现提交号；
- 人工验收清单。

随后运行：

```powershell
& 'D:\Program Files\Obsidian\Obsidian.com' vault='My-Obsidian' read path='项目/Petpet/开发记录/2026-08-21 家园待机稳定与睡眠尺寸修复.md'
& 'D:\Program Files\Obsidian\Obsidian.com' vault='My-Obsidian' outline path='项目/Petpet/开发记录/2026-08-21 家园待机稳定与睡眠尺寸修复.md' format=tree
& 'D:\Program Files\Obsidian\Obsidian.com' vault='My-Obsidian' links path='项目/Petpet/开发记录/2026-08-21 家园待机稳定与睡眠尺寸修复.md'
```

- [ ] **Step 4: 核对 Obsidian 自动备份**

检查 vault Git 状态和最新提交。如果 Obsidian 自动备份已经提交并推送该文件，记录自动提交号；否则只暂存并提交本次新笔记，不带入无关修改。

- [ ] **Step 5: 重启源码小狗**

只终止命令行精确包含 `D:\Agent_project\Petpet\pet.py` 的 `python/pythonw` 进程，以隐藏窗口重新启动同一路径。等待约 1.5 秒，确认新 `pythonw.exe` PID 仍存在。
