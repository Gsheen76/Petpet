# 小屋睡眠参考图与气泡高度调整 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将小屋气泡总上移量调整为 `72px`，并生成同一只家园小狗的透明半蜷侧卧睡眠参考图和可复用提示词。

**Architecture:** `pet.py` 仅调整活动家园分支的纵向偏移，室外定位和气泡绘制不变；行为由现有真实几何测试保护。睡眠图使用三张现有家园小狗素材作为身份与视角参考，通过内置 image generation 生成纯色键控源图，再用 imagegen 去背脚本转换和验证为项目内透明 PNG。

**Tech Stack:** Python 3.12、PyQt5、unittest/pytest、Codex image generation、PNG alpha、imagegen chroma-key helper。

## Global Constraints

- 工作区固定为 `D:\Agent_project\Petpet\.worktrees\home-scene-system`，分支固定为 `codex/home-scene-system`。
- 不执行 `git reset`、`git checkout`，不覆盖或回退其他未提交改动。
- 不暂存、不提交、不推送、不发布。
- 生产代码修改前先运行新增测试并确认 RED。
- 手工文本编辑统一使用 `apply_patch`。
- 气泡在小屋中相对原始位置总计上移 `72px`；室外位置不变。
- 睡眠图只包含小狗，不包含地毯、场景、阴影、文字、`Zzz` 或水印。
- 项目与实施记录同步到 `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统`。

---

### Task 1: 小屋气泡总计上移 72px

**Files:**
- Modify: `tests/test_speech_bubble.py`
- Modify: `pet.py`

**Interfaces:**
- Consumes: `SpeechBubble._pet_uses_home_theme(pet) -> bool`。
- Produces: `_bubble_geometry(width, height)` 在小屋与室外同锚点下产生 `72px` 的 `top()` 差值。

- [x] **Step 1: 修改失败测试**

把 `test_home_bubble_moves_up_without_changing_its_size_or_x_position` 的最终断言改为：

```python
self.assertEqual(inside.top(), outside.top() - 72)
```

保留横向位置与尺寸相等的断言，确保修改不影响其他几何属性。

- [x] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_speech_bubble.py::SpeechBubbleTests::test_home_bubble_moves_up_without_changing_its_size_or_x_position -q`
Expected: FAIL，当前实际差值仍为 `24px`。

- [x] **Step 3: 写最小实现**

在 `SpeechBubble._bubble_geometry()` 的活动家园分支中把：

```python
y -= 24
```

改为：

```python
y -= 72
```

- [x] **Step 4: 运行 GREEN 与回归**

Run: `python -m pytest tests/test_speech_bubble.py tests/test_menu_ui.py -q`
Expected: PASS；室外纯几何用例和小屋主题用例均保持通过。

### Task 2: 生成透明睡眠参考图

**Files:**
- Reference: `assets/scenes/home/home-pet-idle-sit.png`
- Reference: `assets/scenes/home/home-pet-walk-down.png`
- Reference: `assets/scenes/home/home-pet-walk-back-right.png`
- Create: `assets/scenes/home/home-pet-sleep-reference.png`

**Interfaces:**
- Produces: 一张可由 `QImage` 加载、具有 alpha 通道、四角透明且身体完整的 PNG。
- Produces: 最终中英文生成提示词，记录到 Obsidian 实施笔记。

- [x] **Step 1: 调用内置图片生成**

使用三张参考图生成同一只小狗：半蜷侧卧、头枕并拢前爪、闭眼、脸朝右前方、后腿收拢、尾巴沿身体弯曲。背景严格为均匀纯 `#00ff00`，小狗本体不得出现键控绿。

- [x] **Step 2: 检查生成源图**

使用 `view_image` 检查角色身份、睡姿、全身边界、闭眼、无地毯/阴影/文字/水印。若仅姿势或身份有一项不合格，则只针对该问题迭代一次。

- [x] **Step 3: 转换透明 PNG**

把选中的键控源图复制到 worktree 临时路径，运行安装的：

```powershell
python C:\Users\sheen\.codex\skills\.system\imagegen\scripts\remove_chroma_key.py --input <source> --out assets\scenes\home\home-pet-sleep-reference.png --auto-key border --soft-matte --transparent-threshold 12 --opaque-threshold 220 --despill
```

若毛发出现绿边，再运行一次并增加 `--edge-contract 1`；不静默切换 CLI 模型。

- [x] **Step 4: 验证透明素材**

使用 `QImage` 检查：文件可加载、`hasAlphaChannel()` 为真、四角 alpha 为 `0`、主体区域存在非透明像素。再用 `view_image` 检查毛发边缘和身体完整性。

### Task 3: 同步记录与最终验证

**Files:**
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\小屋睡眠参考图与气泡高度调整实施计划.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\场景系统\小屋睡眠参考图与气泡高度调整设计.md`

- [x] **Step 1: 写入最终提示词与素材路径**

记录参考图职责、最终姿势提示词、键控背景禁止项、透明处理参数和项目内输出路径。

- [x] **Step 2: 运行 focused tests**

Run: `python -m pytest tests/test_speech_bubble.py tests/test_menu_ui.py tests/test_home_scene.py -q`

- [x] **Step 3: 运行完整验证**

Run: `python -m pytest -q`
Run: `python -m py_compile pet.py home_pet.py home_scene.py scene_system.py progression.py progression_ui.py`
Run: `git diff --check`

- [x] **Step 4: 重启源码供人工验收**

只重启命令行包含当前 worktree 绝对 `pet.py` 路径的进程，记录新 PID；不暂存、不提交。

结果：当前 worktree 源码已重启，`pythonw.exe` PID 为 `11236`。
