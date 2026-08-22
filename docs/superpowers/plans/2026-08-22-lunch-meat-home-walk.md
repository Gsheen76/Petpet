# 午餐肉家园移动动画实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让午餐肉在家园内复用已有桌面八帧行走动画。

**Architecture:** 家园窗口在无专属行走资源时缓存桌面 walk 帧；渲染阶段依照家园帧索引选择该帧，并通过已有 alpha 裁剪和镜像绘制流程输出，不新增图片文件。

**Tech Stack:** Python、PyQt5、unittest。

## Global Constraints

- 仅为缺少专属家园 walk 资源的宠物启用桌面帧回退。
- 冰淇淋的原生家园 walk 资源优先级不变。
- 缺少有效桌面帧时保持静态待机回退。

### Task 1: 回归测试

**Files:**
- Modify: `tests/test_home_window_boundary.py`

- [ ] 让测试夹具提供两帧桌面 walk QPixmap。
- [ ] 断言午餐肉家园移动选中 `desktop_animation`、按 `now` 推进帧并在左向镜像。
- [ ] 运行目标测试，确认当前代码仍静态回退导致失败。

### Task 2: 家园桌面帧回退

**Files:**
- Modify: `petpet/home/window.py`

- [ ] 在 `refresh_pet_assets()` 无家园 walk 时安全读取 `pet.animation_frames["walk"]`。
- [ ] 在 `home_pet_walk_render_spec()` 为该帧序列生成 `HomePetWalkRenderSpec`。
- [ ] 使用整个序列的 alpha 并集作为稳定 source rect，左向镜像。
- [ ] 运行目标测试确认通过。

### Task 3: 全量验证与交付

**Files:**
- No additional source files.

- [ ] 运行家园焦点测试、全量 `python -m pytest -q`、`python -m py_compile` 和 `git diff --check`。
- [ ] 提交修改、同步 Obsidian 记录并重启源码小狗。
