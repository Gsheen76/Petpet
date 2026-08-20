# 家场景装修界面优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with tests first.

**Goal:** 优化家场景装修态的视觉层级和交互入口，使面板不遮挡主体、装修时隐藏小狗、双击小狗打开家。

**Architecture:** 继续由 `home_scene.py` 管理家场景和装修态，由 `TrayApp` 的点击包装层管理单击/双击判定；不改变 progression 存档结构。选中框只调整绘制样式和固定几何常量。

**Tech Stack:** Python 3, PyQt5, pytest/unittest。

## Global Constraints

- 家场景保持 900 x 768、圆角和右下角定位。
- 装修时小狗隐藏，退出装修或家场景时恢复。
- 家具面板位于左侧，不覆盖整个画布底部。
- 家的按钮与选中框统一暖色主题；双击小狗打开家，单击仍抚摸。

---

### Task 1: 装修态小狗可见性与双击入口

**Files:**
- Modify: `home_scene.py`, `pet.py`
- Test: `tests/test_home_scene.py`, `tests/test_menu_ui.py`

- [ ] 写失败测试：进入装修隐藏小狗、退出恢复；双击调用 `open_home_scene` 而非 `chat`。
- [ ] 运行 focused tests 确认失败。
- [ ] 实现运行时可见性切换和双击入口替换。
- [ ] 运行 focused tests 确认通过。

### Task 2: 左侧家具面板

**Files:**
- Modify: `home_scene.py`
- Test: `tests/test_home_scene.py`

- [ ] 写失败测试：面板位于左侧、宽度受限、卡片不横跨画布、分类和操作命中仍有效。
- [ ] 运行 focused tests 确认失败。
- [ ] 将底部抽屉改为左侧窄面板和两列卡片，保留图片、分类、收纳/放置逻辑。
- [ ] 运行 focused tests 确认通过。

### Task 3: 家主题选中框

**Files:**
- Modify: `home_scene.py`
- Test: `tests/test_home_scene.py`

- [ ] 写失败测试：选中框使用主题色、圆角边界和圆形控制点，渲染仍完整。
- [ ] 运行 focused tests 确认失败。
- [ ] 调整选中框颜色、透明填充、边界和控制点绘制，不改手势几何。
- [ ] 运行 focused tests 确认通过。

### Task 4: 回归与记录

**Files:**
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/场景系统/家场景装修编辑器交互记录.md`

- [ ] 运行 focused tests 和完整 `pytest -q`。
- [ ] 更新 Obsidian 记录和计划状态。
- [ ] 重启源码实例供手工验收。
