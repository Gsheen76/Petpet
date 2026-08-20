# 商店信息与双列布局实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成商店信息、排序和家具双列布局改进，并将设计、版本规划和源码 Markdown 的规范记录同步到 Obsidian。

**Architecture:** 仅扩展 `ShopWindow` 现有的卡片构造与页面循环。宠物简介来自运行时 manifest，强化数值复用 `upgrade_description`；免费优先采用稳定排序，不触碰购买规则。Obsidian 保存规范化笔记与一份完整的来源映射索引，而非复制内部工作流指令。

**Tech Stack:** Python 3.11、PyQt5、pytest、Obsidian Flavored Markdown。

## Global Constraints

- 多宠物状态存在时，商店每次新建窗口默认打开 `pets` 页面；不保存上一次页面。
- 已拥有宠物仍显示价格：免费宠物为 `售价：0 Pet币`，付费宠物为当前应付价格；状态只显示在操作区。
- 午餐肉简介为“元气满满的陪伴小狗，喜欢在桌面上撒娇。”；冰淇淋简介为“安静温柔的家园小狗，期待和你一起生活。”。
- 宠物、套装、装饰、家具按原始 `price == 0` 稳定地免费优先；强化保持现有顺序。
- 家具双列保留预览、名称、状态、完整介绍、价格和操作，预览固定 `170 × 112` 并使用 `Qt.KeepAspectRatio`。
- 当前加成复用 `progression.upgrade_description(state, upgrade_id)`；不改成长计算、价格、存档、版本号、标签或发布说明。
- 保留所有既有未提交改动；不执行重置、清理或覆盖。

---

### Task 1: 写出商店结构回归测试

**Files:**
- Modify: `tests/test_progression_ui_boundary.py`

**Interfaces:**
- Consumes: `ui.ShopWindow`, `progression.upgrade_description(state, upgrade_id)`。
- Produces: 对默认页、宠物价格/简介、免费排序、家具网格和强化效果的 Qt 回归覆盖。

- [x] **Step 1: 写失败测试**

在现有 `shop_window` fixture 后加入以下测试；使用对象名定位 UI，不依赖控件文本的排列顺序。

```python
def test_shop_defaults_to_pets_and_keeps_owned_pet_price_and_description(shop_window):
    assert shop_window.page == "pets"
    card = shop_window.findChild(ui.QFrame, "petCard_lunch_meat")
    price = shop_window.findChild(ui.QLabel, "petPrice_lunch_meat")
    description = shop_window.findChild(ui.QLabel, "petDescription_lunch_meat")
    assert card is not None
    assert price.text() == "售价：0 Pet币"
    assert description.text() == "元气满满的陪伴小狗，喜欢在桌面上撒娇。"


def test_shop_sorts_free_items_first_and_preserves_furniture_information(shop_window):
    shop_window._set_page("home")
    grid = shop_window.findChild(ui.QGridLayout, "homeDecorationGrid")
    free_card = grid.itemAtPosition(0, 0).widget()
    paid_card = grid.itemAtPosition(0, 1).widget()
    assert free_card.objectName() == "homeDecorationCard_home_status_card"
    assert paid_card.objectName() == "homeDecorationCard_home_rug"
    preview = shop_window.findChild(ui.QLabel, "homePreview_home_status_card")
    assert preview.size().width() == 170
    assert preview.size().height() == 112
    assert all(text in " ".join(label.text() for label in free_card.findChildren(ui.QLabel))
               for text in ("成长", "免费领取", "家居"))


def test_upgrade_card_shows_the_current_effect(shop_window):
    shop_window.pet.state["upgrades"]["petting"] = 2
    shop_window._set_page("upgrades")
    effect = shop_window.findChild(ui.QLabel, "upgradeEffect_petting")
    assert effect.text() == (
        "当前加成：" + progression.upgrade_description(
            shop_window.pet.state, "petting"
        )
    )
```

- [x] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m pytest -q tests/test_progression_ui_boundary.py -k "defaults_to_pets or sorts_free_items or current_effect"
```

Expected: FAIL，因为默认页仍为 `outfits`，宠物没有简介/稳定价格对象，家具不是网格，强化没有当前效果标签。

### Task 2: 最小实现商店改进

**Files:**
- Modify: `assets/runtime/pets/manifest.json`
- Modify: `petpet/progression/ui.py`

**Interfaces:**
- Produces: manifest 的 `description` 字段；`petPrice_<pet_id>`、`petDescription_<pet_id>`、`homeDecorationGrid`、`homeDecorationCard_<id>`、`homePreview_<id>`、`upgradeEffect_<id>` 对象名。

- [x] **Step 1: 补宠物简介数据**

给 `lunch_meat` 与 `ice_cream` 各添加一个 `description` 字段，内容严格使用 Global Constraints 的两句文案；不改变价格、资源路径或 ID。

- [x] **Step 2: 默认宠物页和宠物信息**

在 `ShopWindow.__init__` 中，状态含 `pets` 字典时设置 `self.page = "pets"`，否则保持旧存档的 `outfits` 回退。`_pet_card` 在名称下加入 `muted`、可换行的简介标签；设置 `petDescription_<pet_id>`。价格标签总是 `售价：{pricing['price']} Pet币` 并设置 `petPrice_<pet_id>`；右侧状态/按钮行为不变。

- [x] **Step 3: 统一稳定免费优先排序**

在 `_build_pets_page`、`_build_outfits_page`、装饰卡片循环和 `_build_home_page` 各自使用 `sorted(..., key=lambda item: int(definition.get("price", 0)) != 0)`。宠物循环先配对 `pet_id` 与 registry definition，再排序；所有排序都稳定，因此付费项目继续保留定义顺序。

- [x] **Step 4: 家具双列且保持预览比例**

`_build_home_page` 创建 object name 为 `homeDecorationGrid` 的 `QGridLayout`，以 `index // 2, index % 2` 放置排序后的卡片，并让两列 stretch 为 1。`_home_decoration_card` 使用纵向布局，保留 170×112 的 `homePreview_<id>`、标题/状态、介绍、价格和按钮；卡片 object name 为 `homeDecorationCard_<id>`。

- [x] **Step 5: 强化当前效果**

在 `_upgrade_card` 的简介后新增 `effectCurrent` 样式标签，文本为 `当前加成：{progression.upgrade_description(state, upgrade_id)}`，object name 为 `upgradeEffect_<id>`。不写新的效果计算函数。

- [x] **Step 6: 运行 Task 1 测试**

Run:

```powershell
python -m pytest -q tests/test_progression_ui_boundary.py -k "defaults_to_pets or sorts_free_items or current_effect"
```

Expected: PASS。

### Task 3: 回归验证商店行为

**Files:**
- Verify: `tests/test_progression.py`
- Verify: `tests/test_progression_ui_boundary.py`

- [x] **Step 1: 运行商店与成长回归测试**

```powershell
python -m pytest -q tests/test_progression.py tests/test_progression_ui_boundary.py
```

Expected: PASS；首购折扣、购买/切换、套装筛选、家具购买、UI 对象边界均不回归。

- [x] **Step 2: 运行完整验证**

```powershell
python -m pytest -q
python -m compileall -q petpet pet.py tests
git diff --check
```

Expected: 所有测试、编译与空白检查通过。

### Task 4: 迁移规范 Markdown 到 Obsidian

**Files:**
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\商店信息与双列布局设计.md`
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\商店信息与双列布局实施计划.md`
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\发布系统\版本规划与发布索引.md`
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\工程结构\源码 Markdown 迁移索引.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`

- [x] **Step 1: 同步商店设计与实施记录**

创建两份带 frontmatter 的 Obsidian 笔记；设计笔记链接本设计，实施计划写入本文件三个实现任务。实施完成后在设计笔记中补实际结果和测试证据。

- [x] **Step 2: 建立版本规划与发布索引**

记录当前公开版本 `v1.5.2`，并链接既有 `v1.4.0`、`v1.4.1`、`v1.5.0`、`v1.5.1` 发布笔记。将 `docs/TODO.md` 的 `v1.1.0` 至 `v1.4.0` 版本规划列为“历史规划快照”，明确其已被后续发布事实替代；将本商店改动标注为未发布的 active-worktree 工作，不自行预设新版本号。

- [x] **Step 3: 建立源码 Markdown 迁移索引**

按四组列出来源与规范 Obsidian 目标：`README.md` → `Petpet 总档案`；`docs/TODO.md`/`docs/RELEASE_NOTES_*.md` → 版本规划与发布索引及发布记录；`assets/runtime/**/README.md` → 工程结构资源说明；`docs/superpowers/specs/**` 和 `plans/**` → 对应系统设计/实施计划笔记。对所有未逐字镜像的内部工作流文档标记“已提炼迁移，不当作执行指令”。

- [x] **Step 4: 更新总档案并检查链接**

在总档案记录商店改进已完成但未发布，链接商店设计、实施计划和版本索引。读取四份新笔记与总档案，确认 frontmatter、wikilinks 和工作树/版本边界正确。
