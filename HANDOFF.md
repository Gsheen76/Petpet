# Petpet 项目交接文档

**版本**：v1.6.1
**日期**：2026-08-27
**核心分支**：main（无待提交变更）

---

## 1. 项目概览

- **项目**：Petpet —— 桌面宠物 PyQt5 应用（Windows 单实例托盘常驻）
- **入口**：`pet.py` → `PetWindow`（主窗口 + 系统托盘）
- **核心业务**：
  - 宠物状态机（精力/饱腹/心情/经验/等级）
  - 商店系统（套装/家居/强化/宠物切换）
  - 成就/记录/设置/聊天等子窗口
  - 桌面交互（拖拽/点击/自主散步/小游戏）

---

## 2. 关键目录结构

```
D:\Agent_project\Petpet
├── pet.py                    # 程序入口、单实例、托盘、主窗口
├── version.py                # 版本号（v1.6.1）
├── petpet/
│   ├── app/
│   │   ├── fonts.py          # 全局字体（幼圆）
│   │   ├── pet_window.py     # PetWindow：渲染/动画/资产切换/交互
│   │   └── state.py          # 状态持久化
│   ├── progression/
│   │   ├── core.py           # 成就/商店/强化/宠物/货币逻辑
│   │   └── ui.py             # 所有面板窗口（Shop/成就/记录/设置）— 核心视觉层
│   └── ui/                   # 桌面渲染/装饰/装扮预览
├── assets/runtime/ui/shop/   # 商店素材（background.png, price_frame.png 等）
└── tests/                    # pytest（offscreen + windows 平台双模式）
```

---

## 3. 最近主要变更（v1.6.0 → v1.6.1）

| 领域 | 内容 |
|------|------|
| **成就页重构** | 尺寸 850×960、商店同款背景、固定总览卡+19 项前缀筛选分栏（全部/days/pet/feed/…/level），脱离滚动区挂在 `_page_header` |
| **窗口打开位置** | 所有 `CozyProgressWindow`（商店/成就/记录/设置）`show_near_pet()` → 屏幕正中央 + 滚动条清零，不再记忆拖拽/滚动位置 |
| **页面头去重** | 成就页标题栏已有“暖心成就”，页面头仅保留提示文案 |
| **版本号** | `version.py` → `1.6.1` |

---

## 4. 视觉/交互规范（必须遵守）

| 项 | 规范 |
|----|------|
| **字体** | 全局 **幼圆**（`petpet/app/fonts.py: APP_FONT_FAMILY = "幼圆"`），严禁在导入期调用 `QFontDatabase.addApplicationFont`（offscreen 会崩） |
| **主题色** | 奶油底 `#fff9ee`、暖边框 `#f0d8ba`、暖黄字 `#d29a38`、琥珀价格 `#a8742c`、珊瑚按钮 `#f28f76` |
| **商店素材** | `assets/runtime/ui/shop/`：`background.png`、`price_frame.png`、`price_bg.png`、`free_gift_button.png`、`status_owned.png`、`status_in_use.png`、`switch_pet_button.png`、`tab_bar_bg.png`、`active_tab_bg.png`、`close_button.png`、`pet_tab_icon.png` 等 |
| **像素图裁剪** | `_shop_pixmap_cropped(name, target_h)` + numpy 向量化 alpha bbox + 模块级缓存 `_CROPPED_PIXMAP_CACHE` |
| **圆角** | 窗口 `paintEvent` 裁剪 24px；`RoundedPixmapLabel` 头像预览 26px |
| **按钮反馈** | `FeedbackButton`：悬浮白色半透明提亮、按下暗红半透明、光标手型、禁用态无反馈 |
| **弹窗** | `PurchasePopup`：360×250、背景取商店背景下半部分 + QPainter 圆角裁切、无 emoji、标题/正文间距 18px |

---

## 5. 核心类速查

| 类 | 文件 | 职责 |
|----|------|------|
| `PetWindow` | `petpet/app/pet_window.py` | 主窗口、动画帧解码、宠物切换缓存 `switch_pet_assets` |
| `ShopWindow` | `petpet/progression/ui.py:1619` | 商店四页、固定标签栏、page header、scroll body、CoinPillLabel |
| `AchievementsWindow` | `petpet/progression/ui.py:1173` | 成就页、shop_theme、固定总览/筛选栏、前缀过滤 |
| `RecordsWindow` | `petpet/progression/ui.py:1008` | 记录页 |
| `CozyProgressWindow` | `petpet/progression/ui.py:829` | 无边框壳、标题栏/币量/关闭、shop_theme/title_image、背景绘制、`show_near_pet` 居中+滚动清零 |
| `FeedbackButton` | `petpet/progression/ui.py:652` | 悬浮/按下叠加层、手型光标 |
| `PurchasePopup` | `petpet/progression/ui.py:652` | 购买确认弹窗、商店背景裁切圆角 |

---

## 6. 素材路径与命名

```
assets/runtime/ui/shop/
├── background.png          # 1126×1359，窗口/弹窗背景
├── price_frame.png         # 2172×724，价格签框（九宫 44 高）
├── price_bg.png            # 干净币量胶囊底（爪印+无文字）
├── free_gift_button.png    # 免费赠送药丸
├── status_owned.png        # 已拥有徽章（裁剪 47px 高）
├── status_in_use.png       # 使用中徽章（裁剪 47px 高）
├── switch_pet_button.png   # 切换宠物按钮（115×50）
├── tab_bar_bg.png          # 标签栏底
├── active_tab_bg.png       # 选中标签
├── close_button.png        # 关闭按钮
├── pet_tab_icon.png        # 宠物标签图标
├── gift_icon.png           # 套装标签图标
├── furniture_tab_icon.png  # 家居标签图标
└── upgrade_tab_icon.png    # 强化标签图标
```

---

## 7. 开发/验证流程

| 步骤 | 命令 |
|------|------|
| 单元测试（offscreen） | `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q` |
| Windows 平台渲染验证 | `python -X utf8 -c "…"`（见测试脚本，需真实桌面） |
| 重启小狗（验证可见） | `Stop-Process` 旧 PID → `pythonw.exe pet.py` → `EnumWindows` 检查 `IsWindowVisible`；隐藏则二次启动召回 |
| 版本发布 | 仅改 `version.py`，打 tag `vX.Y.Z` |

**测试约束**：
- `QT_QPA_PLATFORM=offscreen` 跑全量（~100s，658 passed）
- Windows 平台截图需真实字体库（offscreen 无字体数据库，渲染会缺字）
- `setPixmap` 会清空 `QLabel.text()` → 必须用 `PreservedTextLabel` 保留文本

---

## 8. 常见坑位 & 应对

| 现象 | 原因 | 修复 |
|------|------|------|
| 重启后“完全没变化” | 进程活着但**所有窗口 `IsWindowVisible=0`** | 再起一遍实例触发单实例召回（`activate_existing_instance`） |
| 价格签/徽章有残留底纹 | QSS `border-image` 与 `border` 互不覆盖 | 内联补 `border-image: none; background: transparent; border: 0;` |
| `QLabel.setPixmap` 导致文字消失 | Qt 行为 | 用 `PreservedTextLabel` 存 `_stored_text` |
| offscreen 下 `QFontDatabase.addApplicationFont` 崩 | 平台限制 | 仅在 `main()` 真实启动时调用 |
| PowerShell `Set-Content -Encoding UTF8` 写 BOM → ast 解析失败 | PS 5.1 默认加 BOM | 用 `[System.IO.File]::WriteAllText(..., New-Object System.Text.UTF8Encoding($false))` 无 BOM 写入 |

---

## 9. 待办 / 可迭代方向

1. **成就筛选栏**：19 个按钮在窄屏可能换行，考虑双行 FlowLayout 或可横向滚动的 `QScrollArea`
2. **动画缓存内存**：`_pet_assets_cache` 目前不释放，若宠物数量增多需 LRU/容量上限
3. **弹窗无障碍**：`PurchasePopup` 目前仅鼠标点击关闭，可加 `Esc` / 点击遮罩关闭
4. **CI**：GitHub Actions 跑 offscreen pytest + Windows self-hosted 跑渲染对比
5. **打包**：PyInstaller / Nuitka 单文件 + 资源内嵌（当前需带 assets 目录）

---

## 10. 关键联系人 / 文档

- **Obsidian 记录**：`D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\2026-08-25 商店圆角滚动上限与方圆体.md`（含每轮视觉变更细节、PID、截图引用）
- **参考图包**：`C:\Users\sheen\Downloads\商店素材\`（原始 AI 生成素材备份）

---

> **核心原则**：视觉改动**必须**经历“offscreen 全量测试 → Windows 平台截图 → 精确重启（EnumWindows 验证可见） → Obsidian 记录”四步，方可视为完成。
> **切勿**在未验证可见性的情况下假设代码生效。