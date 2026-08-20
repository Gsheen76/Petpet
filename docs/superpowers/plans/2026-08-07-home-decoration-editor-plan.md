# 家场景装修编辑器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with tests first.

**Goal:** 将家场景改造成底部家具抽屉与 PPT 式家具选中编辑器，并恢复非装修状态下的小狗跟随视野。

**Architecture:** 复用现有家居存档结构；在 `scene_system.py` 增加可测试的控制框与手柄几何，在 `home_scene.py` 实现底部抽屉、缩放/旋转手势和装修模式状态机。位置与变换继续通过 `progression.py` 规范化保存。

**Tech Stack:** Python 3, PyQt5, pytest/unittest。

## Global Constraints

- 家场景保持 900 x 768，世界保持 1800 x 768，固定在屏幕右下角。
- 所有新可见标签使用中文：装修、退出、全部、地毯、沙发、绿植、墙饰、放置、收纳。
- 左右视野移动仅在装修模式生效；非装修模式视野跟随小狗。
- 缩放限制 0.5..1.5，旋转规范为 -180..180，家具位置遵守世界边界。
- 采用 TDD：每个行为先添加失败测试，确认失败后再写最小实现。

---

### Task 1: 编辑几何纯逻辑

**Files:**
- Modify: `scene_system.py`
- Test: `tests/test_scene_system.py`

**Interfaces:**
- Produce `home_decoration_bounds(position, size, transform, camera_x) -> QRectF`。
- Produce `home_decoration_handles(bounds) -> dict[str, QRectF]`，键为 `nw`, `ne`, `sw`, `se`, `rotate`。
- Produce `scale_from_handle(center, pointer, handle, base_size, rotation, current_scale) -> float`。
- Produce `rotation_from_pointer(center, pointer) -> float`。

- [x] 写测试：旋转后控制框包含对象、四角/旋转手柄位置稳定、拖角按比例返回 scale、旋转角度可规范化。
- [x] 运行 `pytest tests/test_scene_system.py -q`，确认新增测试失败。
- [x] 实现最小几何函数并复用现有 clamp/normalize helpers。
- [x] 重新运行 focused tests，确认通过。

### Task 2: 装修状态与镜头行为

**Files:**
- Modify: `home_scene.py`
- Test: `tests/test_home_scene.py`

- [x] 写测试：非装修隐藏/禁用左右按钮；装修显示并可平移；退出装修清除 manual camera 并回到 dog-follow。
- [x] 运行 focused Qt 测试确认失败。
- [x] 调整 `_sync_scene`, `show_scene`, `toggle_decoration_mode`, `handle_scene_click` 和绘制条件。
- [x] 运行 focused tests 确认通过。

### Task 3: 底部家具抽屉

**Files:**
- Modify: `home_scene.py`
- Test: `tests/test_home_scene.py`

- [x] 写测试：装修时面板位于底部、分类栏可切换、每项显示缩略图和中文名称、收纳/放置动作可用。
- [x] 运行 focused Qt 测试确认失败。
- [x] 将现有左上角列表面板替换为底部抽屉布局，保留已拥有与已收纳过滤逻辑。
- [x] 运行 focused tests 确认通过。

### Task 4: PPT 式直接编辑

**Files:**
- Modify: `home_scene.py`
- Test: `tests/test_home_scene.py`

- [x] 写测试：点击家具选中；拖主体移动；拖四角缩放；拖顶部手柄旋转；退出后所有手势无效；点击空白清除选择。
- [x] 运行 focused Qt 测试确认失败。
- [x] 增加鼠标手势状态机，绘制强化选中框、四边/四角缩放手柄和旋转手柄，调用 Task 1 几何 API 后持久化。
- [x] 运行 focused tests 确认通过。

### Task 5: 回归、记录与运行

**Files:**
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/场景系统/家场景系统开发记录.md`
- Test: all existing tests

- [x] 运行 `pytest tests/test_scene_system.py tests/test_home_scene.py tests/test_progression.py -q`。
- [x] 运行完整 `pytest -q`。
- [x] 更新 Obsidian 记录，写明新交互和测试结果。
- [x] 重启隔离工作区源码实例，检查窗口显示和装修交互。
