# 商店价格标签与强化数值优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**状态：** 已实现，待发布。

**Goal:** 用生成的图片资源统一商店价格，并落实确认的强化和睡眠数值。

**Architecture:** `core.py` 是全部强化公式的唯一来源；`pet_window.py` 只消费其返回值。`ui.py` 用一个价格标签工厂把动态文字叠加到透明 PNG 背景上。

**Tech Stack:** Python 3、PyQt5、pytest、PNG 运行时资源、Obsidian Markdown。

## Global Constraints

- 不新增依赖；价格文字不写死进图片。
- 四张透明、无文字、无数字 PNG 放入 `assets/runtime/ui/`。
- 宠物介绍单行；家具预览继续 `Qt.KeepAspectRatio`。
- 玩耍：精力 `max(0, 10 - 2 * level)`、饱腹 `max(0, 5 - level)`；睡眠饱腹 `max(0, 2 - 0.4 * level)`。
- 精力满值时睡眠不扣饱腹；不改购买规则、强化价格或存档字段。

---

### Task 1: 强化公式与睡眠结算

**Files:**
- Modify: `petpet/progression/core.py:852-1017`
- Modify: `petpet/app/pet_window.py:1919-1941`
- Modify: `tests/test_progression.py:394-465`
- Modify: `tests/test_pet_window_boundary.py`

**Interfaces:**
- Produces: `upgrade_effects()` 中的 `pet_mood`、`play_energy_cost`、`play_hunger_cost`、`sleep_energy_gain`、`sleep_hunger_cost`。
- Consumes: `PetWindow.on_decay()` 读取这些值，并在本次结算前精力小于 100 时才扣睡眠饱腹。

- [x] **Step 1: 写失败测试**

```python
def test_confirmed_upgrade_values_and_descriptions():
    state = fresh_state(upgrades={"petting": 0, "playing": 1, "sleeping": 2})
    effects = progression.upgrade_effects(state)
    assert effects["pet_mood"] == 10
    assert effects["play_energy_cost"] == 8
    assert effects["play_hunger_cost"] == 4
    assert effects["sleep_hunger_cost"] == pytest.approx(1.2)
    assert progression.upgrade_description(state, "petting") == "每次抚摸：心情+10点"

def test_sleeping_at_full_energy_does_not_consume_hunger(window):
    window.state.update({"sleeping": True, "energy": 100.0, "hunger": 50.0})
    window.on_decay()
    assert window.state["hunger"] == 50.0
```

- [x] **Step 2: 验证失败**

Run: `python -m pytest -q tests/test_progression.py tests/test_pet_window_boundary.py`

- [x] **Step 3: 最小实现**

```python
"pet_mood": 10 + 2 * pet_level,
"play_energy_cost": max(0, 10 - 2 * play_level),
"play_hunger_cost": max(0, 5 - play_level),
"sleep_energy_gain": 4.0,
"sleep_hunger_cost": max(0.0, 2.0 - 0.4 * sleep_level),
```

将文案改为 `心情+X点`、`精力-Y点`、`饱腹-Y点`；移除旧的睡眠倍率和精力额外增益。

- [x] **Step 4: 验证并提交**

Run: `python -m pytest -q tests/test_progression.py tests/test_pet_window_boundary.py`

```bash
git add petpet/progression/core.py petpet/app/pet_window.py tests/test_progression.py tests/test_pet_window_boundary.py
git commit -m "feat: rebalance care upgrades"
```

### Task 2: 价格标签图片资源与工厂

**Files:**
- Create: `assets/runtime/ui/shop-price-normal-v1.png`
- Create: `assets/runtime/ui/shop-price-sale-v1.png`
- Create: `assets/runtime/ui/shop-price-discount-v1.png`
- Create: `assets/runtime/ui/shop-price-gift-v1.png`
- Modify: `petpet/progression/ui.py:36-150, 1228-1243`
- Modify: `tests/test_progression_ui_boundary.py:148-180`

**Interfaces:**
- Produces: `_price_tag(text, role, object_name)` 和带“原价/现价/-Z%”的 `_price_labels()`。
- Consumes: `first_purchase_price()` 的 `original_price`、`price` 与 `discount`。

- [x] **Step 1: 写失败测试**

```python
def test_discount_prices_show_original_current_and_actual_percentage(shop_window):
    shop_window.refresh()
    assert shop_window.findChild(QLabel, "originalPrice_ice_cream").text() == "原价：1000 Pet币"
    assert shop_window.findChild(QLabel, "discountPrice_ice_cream").text() == "现价：760 Pet币"
    assert shop_window.findChild(QLabel, "discountBadge_ice_cream").text() == "-24%"
```

- [x] **Step 2: 验证失败**

Run: `python -m pytest -q tests/test_progression_ui_boundary.py`

- [x] **Step 3: 生成并保存四张资源**

用内置图片工具为普通售价、现价、折扣、免费赠送分别生成透明 PNG：暖珊瑚、奶油纸张、缝线、爪印、高光与蝴蝶结；中心留白、无文字、无数字、无水印。把已选文件复制到本任务列出的四个运行时路径。

- [x] **Step 4: 实现图片标签工厂**

```python
def _price_tag(text, role, object_name):
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setProperty("priceTagRole", role)
    label.setAlignment(Qt.AlignCenter)
    return label
```

在 `PANEL_STYLE` 按 `priceTagRole` 绑定图片与文字颜色；原价保留删除线，折扣使用 `round((1 - price / original_price) * 100)`。

- [x] **Step 5: 验证并提交**

Run: `python -m pytest -q tests/test_progression_ui_boundary.py`

```bash
git add assets/runtime/ui petpet/progression/ui.py tests/test_progression_ui_boundary.py
git commit -m "feat: add illustrated shop price tags"
```

### Task 3: 卡片布局与强化文本

**Files:**
- Modify: `petpet/progression/core.py:970-1010`
- Modify: `petpet/progression/ui.py:1110-1216, 1644-1750, 1798-1845`
- Modify: `tests/test_progression.py:394-465`
- Modify: `tests/test_progression_ui.py:82-180`
- Modify: `tests/test_progression_ui_boundary.py:53-180`

- [x] **Step 1: 写失败测试**

```python
def test_pet_description_is_single_line_and_upgrade_effect_has_no_prefix(shop_window):
    shop_window.refresh()
    assert shop_window.findChild(QLabel, "petDescription_lunch_meat").wordWrap() is False
    shop_window._set_page("upgrades")
    effect = shop_window.findChild(QLabel, "upgradeEffect_petting")
    assert effect.text() == "每次抚摸：心情+10点"
    assert "当前加成" not in effect.text()
```

- [x] **Step 2: 验证失败**

Run: `python -m pytest -q tests/test_progression_ui.py tests/test_progression_ui_boundary.py`

- [x] **Step 3: 最小实现**

```python
description.setWordWrap(False)
card.setFixedHeight(290)
effect = QLabel(progression.upgrade_description(state, upgrade_id))
card.setFixedHeight(220)
```

让 `upgrade_description()` 统一输出已确认的 `心情+X点`、`精力-Y点` 和 `饱腹-Y点` 文案，UI 不得复制公式。宠物、套装、家具都调用价格标签工厂；免费商品使用 gift 标签。家具继续等比缩放，固定高度必须容纳现有标题、简介、价格与按钮，不省略信息。

- [x] **Step 4: 验证并提交**

Run: `python -m pytest -q tests/test_progression_ui.py tests/test_progression_ui_boundary.py`

```bash
git add petpet/progression/ui.py tests/test_progression_ui.py tests/test_progression_ui_boundary.py
git commit -m "feat: unify shop card presentation"
```

### Task 4: 文档、Obsidian 与最终验证

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-shop-price-assets-and-upgrade-balance-design.md`
- Modify: `docs/superpowers/plans/2026-08-20-shop-price-assets-and-upgrade-balance.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/开发记录/商店信息与双列布局设计.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/开发记录/商店信息与双列布局实施计划.md`

- [x] **Step 1: 将设计和计划更新为“已实现，待发布”**

记录四张资源路径、强化公式、满精力睡眠规则及实际测试计数；不修改版本号。

- [x] **Step 2: 同步 Obsidian**

在既有商店设计和计划笔记追加“价格标签与强化平衡”章节，包含资源路径、价格规则、玩耍/睡眠公式与验证结果。

- [x] **Step 3: 运行最终验证**：`python -m pytest -q` 为 `609 passed in 56.21s`；`python -m compileall -q petpet pet.py tests` 无输出且退出码 0；`git diff --check` 退出码 0（仅 LF/CRLF 转换警告）。

Run: `python -m pytest -q`
Expected: 全部测试通过。

Run: `python -m compileall -q petpet pet.py tests`
Expected: 无输出、退出码 0。

Run: `git diff --check`
Expected: 无输出、退出码 0。

- [x] **Step 4: 提交文档**

```bash
git add docs/superpowers
git commit -m "docs: record shop price polish"
```
