# 冰淇淋睡眠体型一致性实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 调整冰淇淋桌面与家园睡眠显示比例，使主体可见高度与待机一致。

**Architecture:** 复用现有 manifest 比例和家园渲染比例常量，不新增渲染抽象。测试锁定资源配置和最终家园绘制矩形高度。

**Tech Stack:** Python、PyQt5、unittest、JSON、Pillow 资源检查。

## Global Constraints

- 只修改冰淇淋睡眠显示比例；不改窗口尺寸、帧率、裁剪区、锚点、阴影或其他宠物动画。
- 桌面目标比例为 `1.34`；家园目标比例为 `1.0`。
- 必须先观察回归测试失败，再修改生产配置。

### Task 1: 添加回归测试

**Files:**
- Modify: `tests/test_petting_animation.py`
- Modify: `tests/test_home_scene.py`

- [ ] 增加桌面冰淇淋 manifest 睡眠比例断言。
- [ ] 更新家园睡眠测试，断言睡眠矩形高度与待机矩形高度相等。
- [ ] 运行两组焦点测试，确认旧比例导致预期失败。

### Task 2: 调整最小配置

**Files:**
- Modify: `assets/runtime/pets/ice_cream/desktop/animations/manifest.json`
- Modify: `petpet/home/rendering.py`

- [ ] 将冰淇淋桌面睡眠 `scale` 改为 `1.34`。
- [ ] 将家园 `HOME_PET_SLEEP_VISUAL_SCALE` 改为 `1.0`。
- [ ] 运行焦点测试确认通过。

### Task 3: 全量验证与交付

**Files:**
- No additional source files.

- [ ] 运行全量 `python -m pytest -q`、`python -m py_compile` 和 `git diff --check`。
- [ ] 提交修改并重启主线源码小狗。
