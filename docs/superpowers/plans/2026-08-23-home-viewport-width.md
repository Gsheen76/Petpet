# 家园视口宽度缩减实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将家园可见画布宽度由 900 像素缩减为 600 像素。

**Architecture:** 只修改共享的 `HOME_VIEWPORT_SIZE`，让既有场景布局、相机、裁切和坐标转换自动使用新宽度；世界尺寸和素材比例保持不变。

**Tech Stack:** Python、PyQt5、pytest。

## Global Constraints

- 画布尺寸固定为 600×768。
- 家园世界保持 1800×768。
- 不缩放背景、家具、宠物和动画素材。

---

### Task 1：锁定新画布几何

**Files:**
- Modify: `tests/test_home_scene.py`
- Modify: `tests/test_scene_system.py`
- Modify: `petpet/home/geometry.py`

**Interfaces:**
- Consumes: `board_geometry(screen_rect: QRect) -> QRect`
- Produces: `HOME_VIEWPORT_SIZE = (600, 768)`

- [x] 将 1920×1080 屏幕的预期画布改为 `QRect(1320, 312, 600, 768)`，并确认旧实现测试失败。
- [x] 将 `HOME_VIEWPORT_SIZE` 从 `(900, 768)` 改为 `(600, 768)`。
- [x] 更新相机中心、最大平移范围和屏幕内定位的几何契约。

### Task 2：验证窄视口交互

**Files:**
- Modify: `tests/test_home_scene.py`

**Interfaces:**
- Consumes: `HomeSceneWindow.scene_canvas_rect() -> QRect`
- Produces: 窄视口下保持可用的按钮、家具和宠物目标坐标测试。

- [x] 将按钮测试改为相对画布左右边缘验证。
- [x] 将家具命中测试改为从画布左边缘换算坐标。
- [x] 验证装修侧栏仍独立于场景画布。
- [x] 运行家园专项测试：92 项通过。
- [x] 运行全量测试：656 项通过。
