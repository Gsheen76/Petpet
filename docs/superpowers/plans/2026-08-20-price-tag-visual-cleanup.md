# 商店价格标签视觉修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用不会裁切或遮挡文字的统一原生价格标签，替换商店中失真的插画底图。

**Architecture:** 保持 `ShopWindow._price_tag()` 作为全部价格展示的唯一入口。仅把 `PANEL_STYLE` 的四种 `priceTagRole` 从位图 `border-image` 改为共享的奶油金边样式；动态文本、折扣计算与删除线逻辑维持现状。

**Tech Stack:** Python 3、PySide6、Qt Style Sheets、pytest。

## Global Constraints

- 不再使用 `shop-price-*-v1.png` 作为文字标签底图。
- 保持免费、常规、折扣三种价格语义、已有折扣算法和原价删除线。
- 不改变购买逻辑、家具卡片尺寸或展示图的等比缩放。

---

### Task 1: 用可读的原生标签替换位图样式

**Files:**
- Modify: `tests/test_progression_ui_boundary.py:159-181`
- Modify: `petpet/progression/ui.py:298-325`
- Delete: `assets/runtime/ui/shop-price-normal-v1.png`
- Delete: `assets/runtime/ui/shop-price-sale-v1.png`
- Delete: `assets/runtime/ui/shop-price-discount-v1.png`
- Delete: `assets/runtime/ui/shop-price-gift-v1.png`

**Interfaces:**
- Consumes: `ShopWindow._price_tag(text, role, object_name) -> QLabel` 和 `priceTagRole` 动态属性。
- Produces: `normal`、`sale`、`discount`、`gift` 四种不含 `border-image` 的价格标签样式。

- [ ] **Step 1: 写入失败的 UI 边界测试**

```python
def test_price_tags_reserve_a_text_safe_height(shop_window):
    for role in ("normal", "sale", "discount", "gift"):
        label = shop_window._price_tag("售价：760 Pet币", role, role)
        assert label.minimumHeight() >= 34
        assert label.sizeHint().height() >= label.fontMetrics().height() + 10
```

- [ ] **Step 2: 运行测试并确认它因旧位图样式失败**

Run: `python -m pytest tests/test_progression_ui_boundary.py::test_shop_price_tags_use_native_text_safe_style -q`

Expected: FAIL，当前 `_price_tag()` 没有为动态文字预留安全高度。

- [ ] **Step 3: 最小化实现原生标签样式并移除旧资源**

```python
QLabel[priceTagRole="normal"] {
    background: #fff8e8;
    border: 1px solid #e8bd72;
    border-radius: 11px;
    color: #7a5040;
    padding: 5px 12px;
}
```

为 `sale`、`discount`、`gift` 分别保留同一安全边距与圆角，仅用背景色、描边和字体权重区分层级；`_price_tag()` 设定 34px 最小高度；删除四张旧标签 PNG。不得修改 `_price_tag()` 的文本、角色或折扣计算。

- [ ] **Step 4: 运行焦点测试并确认通过**

Run: `python -m pytest tests/test_progression_ui_boundary.py -q`

Expected: PASS，且既有折扣文本/删除线、免费商品与卡片布局断言仍通过。

- [ ] **Step 5: 运行完整验证**

Run: `python -m pytest -q; python -m compileall -q petpet pet.py tests; git diff --check`

Expected: pytest 全绿；编译和空白检查均退出码 0。

- [ ] **Step 6: 提交实现**

```bash
git add petpet/progression/ui.py tests/test_progression_ui_boundary.py assets/runtime/ui
git commit -m "fix: render shop price tags without clipped artwork"
```
