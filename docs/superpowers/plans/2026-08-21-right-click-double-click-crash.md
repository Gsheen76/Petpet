# 右键快速双击闪退修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除菜单关闭状态下快速双击小狗右键导致的 Qt 原生闪退，同时保持现有菜单速度、外观和关闭规则。

**Architecture:** 在 `BubbleMenu` 的应用级事件过滤器中把所属小狗的右键识别为菜单请求而不是菜单外关闭；在 `PetWindow.open_bubble_menu()` 中复用仍可见且未关闭的菜单实例。测试分别锁定事件过滤边界与菜单幂等复用，再用真实 Qt 子进程和完整测试套件验证生命周期稳定性。

**Tech Stack:** Python 3.12、PyQt5 5.15、unittest/pytest、Windows Event Loop、Obsidian Flavored Markdown

## Global Constraints

- 不改变菜单外观、按钮布局、预热机制或现有页面切换行为。
- 小狗本体右键不得安排当前菜单关闭；其他真正的菜单外点击仍需关闭。
- 可见且未进入 `_closing` 的菜单必须复用，不得关闭重建。
- 不引入新依赖，不修改用户未跟踪的 `.superpowers` 内容。
- 完成后同步 Obsidian、提交并重启 `D:\Agent_project\Petpet\pet.py`。

---

### Task 1: 锁定快速右键菜单生命周期

**Files:**
- Modify: `tests/test_menu_ui.py`
- Modify: `petpet/ui/desktop.py`
- Modify: `petpet/app/pet_window.py`

**Interfaces:**
- Consumes: `BubbleMenu.eventFilter(watched, event) -> bool`、`PetWindow.open_bubble_menu() -> BubbleMenu | None`
- Produces: 小狗右键不触发 `_close()` 的事件边界；可见活动菜单的幂等复用行为

- [ ] **Step 1: 写入事件过滤器失败测试**

在 `tests/test_menu_ui.py` 增加真实 `BubbleMenu.eventFilter` 边界测试。测试对象包含 `_closing=False`、`_prewarming=False`、可见菜单几何和所属 `pet`；右键事件的 `watched` 正是所属 `pet`。用 `QTimer.singleShot` spy 断言没有安排 `_close()`：

```python
def test_right_clicking_owner_pet_does_not_schedule_menu_close(self):
    owner = object()
    menu = SimpleNamespace(
        pet=owner,
        _closing=False,
        _prewarming=False,
        isVisible=lambda: True,
        frameGeometry=lambda: QRect(20, 20, 100, 80),
        stat_bubble=None,
        _close=Mock(),
    )
    event = SimpleNamespace(
        type=lambda: QEvent.MouseButtonPress,
        button=lambda: Qt.RightButton,
        globalPos=lambda: QPoint(300, 300),
    )

    with patch.object(QTimer, "singleShot") as single_shot:
        BubbleMenu.eventFilter(menu, owner, event)

    single_shot.assert_not_called()
    menu._close.assert_not_called()
```

- [ ] **Step 2: 写入可见菜单复用失败测试**

构造一个可见、未关闭的旧菜单，直接调用真实 `PetWindow.open_bubble_menu()`，断言旧菜单不关闭、新工厂不调用，并且执行跟随与置顶：

```python
def test_open_bubble_menu_reuses_visible_active_menu(self):
    old = SimpleNamespace(
        _closing=False,
        isVisible=lambda: True,
        follow_pet=Mock(),
        raise_=Mock(),
        activateWindow=Mock(),
        _close=Mock(),
    )
    factory = Mock()
    harness = SimpleNamespace(
        _bubble_menu=old,
        _last_bubble_menu_t=0.0,
        _create_bubble_menu=factory,
    )

    result = PetWindow.open_bubble_menu(harness)

    self.assertIs(result, old)
    old.follow_pet.assert_called_once_with()
    old.raise_.assert_called_once_with()
    old.activateWindow.assert_called_once_with()
    old._close.assert_not_called()
    factory.assert_not_called()
```

- [ ] **Step 3: 运行焦点测试确认 RED**

Run:

```powershell
python -m pytest tests/test_menu_ui.py -q
```

Expected: 两个新增测试失败；第一个观察到 `QTimer.singleShot(0, menu._close)`，第二个观察到旧菜单被关闭或函数未返回旧菜单。

- [ ] **Step 4: 实现最小事件过滤边界**

在 `BubbleMenu.eventFilter()` 的现有外部点击逻辑之前加入：

```python
if (
    event.type() == QEvent.MouseButtonPress
    and watched is self.pet
    and hasattr(event, "button")
    and event.button() == Qt.RightButton
):
    return False
```

不要改变左键小狗、属性卡、其他窗口或菜单自身的既有判断。

- [ ] **Step 5: 实现最小可见菜单复用**

在 `PetWindow.open_bubble_menu()` 读取 `old` 后，优先检查对象可见且未 `_closing`。满足时重新定位并置顶，然后返回：

```python
if old is not None and not getattr(old, "_closing", False):
    try:
        if old.isVisible():
            old.follow_pet()
            old.raise_()
            old.activateWindow()
            return old
    except RuntimeError:
        pass
```

创建新菜单后返回 `self._bubble_menu`，使接口和复用分支一致。保留失效对象的现有清理路径。

- [ ] **Step 6: 运行焦点测试确认 GREEN**

Run:

```powershell
python -m pytest tests/test_menu_ui.py tests/test_pet_window_boundary.py -q
```

Expected: 全部通过且无 Qt 警告。

- [ ] **Step 7: 提交生命周期修复**

```powershell
git add tests/test_menu_ui.py petpet/ui/desktop.py petpet/app/pet_window.py
git commit -m "fix: stabilize rapid right-click menu"
```

### Task 2: 压力验证、Obsidian 同步与重启

**Files:**
- Create: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\右键快速双击闪退修复.md`
- Verify: `pet.py`

**Interfaces:**
- Consumes: Task 1 的稳定右键菜单生命周期
- Produces: 可追溯的故障记录、完整回归证据与运行中的验证进程

- [ ] **Step 1: 运行真实 Qt 连续右键压力测试**

启动隔离 Python 子进程，创建真实 `PetWindow`，连续派发至少 100 轮右键按下、释放和 `QContextMenuEvent`，每轮处理 Qt 事件。子进程必须以退出码 0 结束；若退出码为 Windows 原生崩溃码，则保留证据并继续定位，不得宣称完成。

- [ ] **Step 2: 运行完整验证**

Run:

```powershell
python -m pytest -q
python -m py_compile pet.py petpet/app/pet_window.py petpet/ui/desktop.py
git diff --check
```

Expected: pytest 0 failures，编译和 diff 检查退出码均为 0。

- [ ] **Step 3: 写入 Obsidian 开发记录**

创建带 frontmatter 的 Obsidian 笔记，包含：用户复现方式、Windows `Qt5Core_conda.dll / 0xc0000005` 证据、根因、方案 A、RED/GREEN 测试、完整测试数量、提交号和人工验证步骤。使用 `[[Petpet]]` 或现有项目笔记 wikilink，并用 `> [!bug]` 与 `> [!success]` 突出故障和修复。

- [ ] **Step 4: 提交 Obsidian 记录**

在 Obsidian 仓库仅暂存新建开发记录，不带入已有无关修改，提交信息：

```powershell
git commit -m "docs: record Petpet right-click crash fix"
```

- [ ] **Step 5: 最终提交检查并重启小狗**

确认 Petpet 仓库仅剩任务开始前已存在的未跟踪目录。终止命令行精确包含 `D:\Agent_project\Petpet\pet.py` 的旧 `python/pythonw` 进程，再以隐藏窗口启动同一路径，等待约 1.2 秒并确认新 PID 仍存在。
