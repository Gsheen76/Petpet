+# 暖色圆角设置与教程实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将设置和教程改为与聊天一致的暖色真实圆角界面，并用“健康提醒 / 性格偏好”两个三档滑块替代八项精细参数。

**Architecture:** 在 `pet.py` 中新增一个只接受 0/1/2 的三档控件与两组集中预设映射。设置窗口读取旧字段时选取距离最近的预设，保存时写回原字段；教程继续使用现有分页状态机，只更新视觉容器、字体和六页内容。

**Tech Stack:** Python 3、PyQt5、unittest/pytest、Obsidian Flavored Markdown。

## Global Constraints

- 不执行 git reset、git checkout，不覆盖或回退已有未提交改动。
- 修改前先写失败测试；修改后运行 focused tests 与 `pytest -q`。
- 顶层设置与教程窗口必须使用透明外壳和暖白实体圆角卡。
- 字体层级固定为标题 22px、分组标题 18px、正文/控件 17px、辅助说明 15px，并使用 DPI 无关像素字体。
- 健康提醒三档必须保留喝水、休息眼睛、起身活动三种提醒。
- 性格偏好必须同时控制说话、提醒与主动搭话频率。
- 保留旧底层字段并兼容旧存档；恢复默认后两个档位均为“适中”。
- 所有项目 Markdown 同步到 `D:\Github Desktop\My-Obsidian\项目\Petpet`。
- 不提交、不推送、不发布。

---

### Task 1: 三档预设与旧值匹配

**Files:**
- Modify: `pet.py`
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Produces: `SettingsWindow.HEALTH_PRESETS`、`SettingsWindow.PERSONALITY_PRESETS`。
- Produces: `SettingsWindow._nearest_preset_index(keys, presets) -> int`，返回 0、1 或 2。

- [ ] **Step 1: 写失败测试**

验证健康三档的分钟数、性格三档的闲置/间隔值、默认值匹配“适中”，以及任意旧字段值会映射到距离最近的档位。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest -q tests/test_settings_ui.py -k "preset or nearest"`
Expected: FAIL，因为预设和匹配函数尚不存在。

- [ ] **Step 3: 实现集中预设和距离匹配**

健康预设：

```python
HEALTH_PRESETS = (
    {"remind_drink_min": 120, "remind_rest_min": 180, "remind_stand_min": 90},
    {"remind_drink_min": 60, "remind_rest_min": 90, "remind_stand_min": 45},
    {"remind_drink_min": 40, "remind_rest_min": 60, "remind_stand_min": 30},
)
```

性格预设保持默认档与当前默认字段完全一致；文静使用 60 分钟/6 小时，活泼使用 15 分钟/1 小时，并设置单调递增的说话概率与搭话权重。

- [ ] **Step 4: 运行 Task 1 测试**

Run: `python -m pytest -q tests/test_settings_ui.py -k "preset or nearest"`
Expected: PASS。

### Task 2: 三档吸附滑块控件

**Files:**
- Modify: `pet.py`
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Produces: `ThreeLevelSlider(labels: tuple[str, str, str])`。
- Produces: `value() -> int`、`setValue(index: int)`，值域严格为 0..2。

- [ ] **Step 1: 写失败测试**

验证控件包含三个文字标签、值只会落在 0/1/2、键盘/鼠标改变后吸附到档位，并采用 `threeLevelSlider` 与 `threeLevelOption` 对象名。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest -q tests/test_settings_ui.py -k "three_level"`
Expected: FAIL，因为控件尚不存在。

- [ ] **Step 3: 实现最小控件**

使用水平 `QSlider`，范围 0..2、步长 1、刻度间隔 1；上层或下层放置三项等宽标签，点击标签也会选择相应档位。滑轨、滑块与当前档位使用暖粉圆角样式。

- [ ] **Step 4: 运行 Task 2 测试**

Run: `python -m pytest -q tests/test_settings_ui.py -k "three_level"`
Expected: PASS。

### Task 3: 设置页布局、保存与真实圆角

**Files:**
- Modify: `pet.py`
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: `ThreeLevelSlider`、两组预设、`_nearest_preset_index`。
- Produces: `inputs["health_level"]` 与 `inputs["personality_level"]`。

- [ ] **Step 1: 写失败测试**

验证旧八项精细字段不再各自生成控件；两个新控件存在且默认为 1；保存档位 0/2 会写回全部底层字段；重置回到 1；窗口具有 `WA_TranslucentBackground` 和实体 `settingsCard`；抓图四角 alpha 为 0；标题/正文/辅助字号分别为 22/17/15px。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest -q tests/test_settings_ui.py`
Expected: FAIL，显示旧 Stepper 布局及不透明顶层。

- [ ] **Step 3: 改为 A 方案纵向卡片**

创建 `QFrame#settingsCard` 承载全部内容，顶层透明；保留“界面体验”，新增“健康提醒”和“性格偏好”两张卡。移除面向玩家的八项 Stepper，只通过两个三档控件读写预设。

- [ ] **Step 4: 统一字体与控件尺寸**

使用 `independent_pixel_font` 显式设置字体，不在 QSS 中混用点字号；按钮、下拉和三档控件使用统一高度与暖色圆角。

- [ ] **Step 5: 运行设置 focused tests**

Run: `python -m pytest -q tests/test_settings_ui.py tests/test_menu_ui.py`
Expected: PASS。

### Task 4: 教程六页内容与圆角视觉

**Files:**
- Modify: `pet.py`
- Test: `tests/test_onboarding.py`
- Test: `tests/test_menu_ui.py`

**Interfaces:**
- Produces: `TutorialWindow.PAGES` 六页内容。
- Produces: 实体 `QFrame#tutorialCard` 与统一像素字体层级。

- [ ] **Step 1: 写失败测试**

验证教程正好六页；包含“小屋左键移动 / 右键互动 / 垫子睡觉”“免费与自定义聊天 / 图片”“健康提醒 / 性格偏好”；窗口四角透明；实体卡存在；标题、正文和按钮使用像素字体。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest -q tests/test_onboarding.py tests/test_menu_ui.py -k tutorial`
Expected: FAIL，因为仍是五页和旧顶层背景。

- [ ] **Step 3: 更新六页教程文案**

每页说明限制为两到三行，保持最后一页命名校验和完成回调不变。

- [ ] **Step 4: 改造教程实体卡与排版**

顶层设置透明背景；把品牌栏、图标区、标题正文、名字卡、进度和按钮放入 `tutorialCard`；使用 22/18/17/15px 字体体系和暖色圆角。

- [ ] **Step 5: 运行教程 focused tests**

Run: `python -m pytest -q tests/test_onboarding.py tests/test_menu_ui.py -k tutorial`
Expected: PASS。

### Task 5: 文档同步与完整验证

**Files:**
- Modify: `docs/superpowers/specs/2026-08-12-rounded-settings-and-tutorial-design.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\设置系统\暖色圆角设置与教程设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

- [ ] **Step 1: 更新实施结果**

记录最终档位映射、旧存档兼容方式、教程六页内容及实际测试数字。

- [ ] **Step 2: 运行所有 focused tests**

Run: `python -m pytest -q tests/test_settings_ui.py tests/test_onboarding.py tests/test_menu_ui.py`
Expected: PASS。

- [ ] **Step 3: 运行全量测试**

Run: `python -m pytest -q`
Expected: 全部 PASS。

- [ ] **Step 4: 进行静态检查**

Run: `git diff --check`
Expected: 无错误；仅允许已有行尾警告。

- [ ] **Step 5: 复核工作区**

Run: `git status --short`
Expected: 保留用户所有既有未提交改动；不提交、不推送。
