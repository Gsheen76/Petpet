# 午餐肉家园移动动画实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让午餐肉在家园内播放已清理的四向 16 帧行走动画。

**Architecture:** 导入脚本将四张用户提供的 4×4 精灵图清理为透明家园资源；manifest 声明网格规格，家园窗口按当前移动主轴加载并渲染对应方向的 16 帧序列。

**Tech Stack:** Python、PyQt5、unittest。

## Global Constraints

- 仅为声明四向网格资源的宠物启用四向播放。
- 冰淇淋的原生家园 walk 资源优先级不变。
- 缺少有效四向帧时保持既有原生资源与桌面帧回退。

### Task 1: 四向资源与回归测试

**Files:**
- Modify: `tests/test_home_pet.py`
- Modify: `tests/test_home_scene.py`
- Modify: `tests/test_home_window_boundary.py`

- [x] 断言位移主轴选择上、下、左、右四个朝向。
- [x] 断言午餐肉四张网格均拆为 16 帧，并按方向优先渲染。
- [x] 断言帧索引可推进到第 9–16 帧。

### Task 2: 四向网格导入与家园渲染

**Files:**
- Create: `tools/import_lunch_meat_home_walk.py`
- Create: `assets/runtime/pets/lunch_meat/home/animations/walk_*.png`
- Modify: `assets/runtime/pets/manifest.json`
- Modify: `petpet/home/pet.py`
- Modify: `petpet/home/rendering.py`
- Modify: `petpet/home/window.py`

- [x] 清理每格的半透明生成杂边，保留最大犬体区域。
- [x] 在 manifest 登记四张 4×4 家园网格。
- [x] 在 `refresh_pet_assets()` 拆分网格，在 `home_pet_walk_render_spec()` 按方向输出对应帧。
- [x] 保留原生两向和桌面帧回退，以兼容冰淇淋与未补图宠物。

### Task 3: 全量验证与交付

**Files:**
- No additional source files.

- [x] 运行家园焦点测试、全量 `python -m pytest -q`、`python -m py_compile` 和 `git diff --check`。
- [x] 提交修改、同步 Obsidian 记录并重启源码小狗。
