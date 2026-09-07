# Petpet 项目交接文档

**版本**：v1.6.3
**日期**：2026-09-01
**核心分支**：main（有未推送提交：宠物详情面板 4 连击 3ac4ab1..85b4368，等用户确认后推送）

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
├── version.py                # 版本号（v1.6.3）
├── petpet/
│   ├── app/
│   │   ├── fonts.py          # 全局字体（幼圆）
│   │   ├── pets.py           # 宠物注册表（缓存化）
│   │   ├── pet_window.py     # PetWindow：渲染/动画/资产切换/交互
│   │   └── state.py          # 状态持久化
│   ├── home/
│   │   ├── window.py         # HomeSceneWindow：家园场景/交互按钮/影子/装饰面板
│   │   ├── pet.py            # HomePetController：2.5D 移动/走路/睡觉状态机
│   │   ├── rendering.py      # 状态卡渲染、精灵表裁剪
│   │   └── geometry.py       # 视口/世界/地垫墙饰边界钳制
│   ├── progression/
│   │   ├── core.py           # 成就/商店/强化/宠物/货币逻辑
│   │   └── ui.py             # 所有面板窗口（Shop/成就/记录/设置）— 核心视觉层
│   └── ui/                   # 桌面渲染/装饰/装扮预览/聊天/设置
├── assets/runtime/ui/shop/   # 商店素材（background.png, price_frame.png 等）
└── tests/                    # pytest（offscreen + windows 平台双模式）
```

---

## 3. 最近主要变更（v1.6.1 → v1.6.3）

### v1.6.3 后（未发布，未推送）

| 领域 | 内容 |
|------|------|
| **素材库治理** | **全量审计 + 清理 + 守卫（2026-09-04）**：删零引用死素材（打包体积约 -12MB）：旧 `ui/pet_profile/` 31 张整目录、商店 3 孤儿（currency_bg/paw_print_icon/pet_shop_header）、`pet_profile_new` 死文件 4 张（background/base_UI/description_bg/progress_bar）、icon-48、本地 assets/icons 两张 + gitignore 对应两行、空目录 assets/rig2d；参考稿归档 `assets/source/references/`（jieshao/taozhuang 背景、ref 布局稿×2、outfits walk-reference×2）——runtime 不再混开发稿。命名统一 snake_case（同步改引用）：`outfit_diansour→outfit_dinosaur`（修拼写）、`宠物头像列表→pet_avatar_rail`（修中文文件名）、ice_cream 姿势 `home-pet-*→home_pet_*`×4、`wall-art→wall_art`、`scenes/home` 的 `home-background/home-nav-*→snake`×4（**守卫测试抓出的审计漏项**）；牵动 pets/manifest.json、ice_cream 动画 manifest 相对路径、rendering.py、core.py、5 个测试文件、3 个 tools。**修真 bug**：settings.py QSS 关闭按钮 border-image 硬编码盘符绝对路径（打包版按钮隐形）→ `CLOSE_BUTTON_ICON_PATH` 模块常量。**bounce.wav 接线**：落地弹跳（abs(vy)>60）播放——此前加载进内存却从未播放。**新增守卫测试 `tests/test_asset_inventory.py`（4 条规则）**：runtime 无孤儿 / 命名 ASCII snake_case（帧 NNN.png、图标 icon-N.png 例外）/ 动画帧目录必须被 manifest 声明 / 主代码禁盘符绝对路径。断链工具（build_fetch/build_petting/generate_home_assets/import_home_furniture）加 legacy 标注；`slice_sprite_sheet.py` help 更新；`assets/source/spritesheets/README.md` 重写为 per-pet 现行结构（v2）；make_icons 去 48。规范入 AGENTS.md「资源管理规范」章节。坑位：**manifest 的 fallback=静态姿势名（非动画键），自引用 happy→happy 是正确写法不是死循环**。验证：pytest 712 通过 + Windows 平台截图（设置页/详情面板）+ 重启可见（PID 7012）。审计结论修正记录：初版误判「商店无孤儿」（实有 3 个）与「manifest 幽灵声明是死循环隐患」（实为合法语义） |
| **宠物详情面板** | **换新素材从零重建中（用户指示逐轮搭建）**：新素材在 `assets/runtime/ui/pet_profile_new/`（background 1201×1304 + base_UI 右侧骨架 + 装备按钮/宠物图标）。第十四轮分层新背景（`0465bcd`）：背景换 `new_background.png`（1085×1663，横幅/虚线圆/粉垫烘焙）+ 独立 rail `宠物头像列表.png`（无烘焙卡槽，卡槽程序布局）——ART 1085×1450（第十五轮原比例版，垫 y430-570，`ce504e2`）；第二十一轮交互与进度条（`7118f8b`）：双卡右移还原、rail+卡左移 10 显示px（rail x51 卡 x76）、午餐肉卡 y272；**改名键/关闭键统一 `_ArtButton` 交互**（悬浮素材放大+白洗、点击缩小→回弹触发，弃 QSS 背景块——反馈区比素材大的教训）、牌上名字 `_ArtTitle` 艺术字（34 号）；**进度条恢复**（_MiniBar 渐变版：等级经验/好感/三属性 + 数值联动，上轮误删）；改名组件右移 20 显示px；简介节间距 24；第四十一轮对位（`d19c626`）：region_background 顶部裁 56px（565→499）、分栏按钮叠在背景内顶部（不再浮在上方）、内容边距对齐装饰内框（侧带薄~2px+呼吸 22）；第四十轮剥层（`c01a4d2`）：套装卡 QSS（渐变底+虚线框）删除——内容直接写在区域背景上，两层结构（背景+内容+顶部按键）；第七十二轮左下角商店提示+按键（`504ca12`）：`_ShopPillButton` 胶囊键（标准反馈，回弹后触发）+ 两行 tips「宠物和套装可前往商店购买」，点击走 `PetWindow.open_shop`；第七十一轮改名条上移+两键紧连+简介均布（`92eba6e`）：改名组件 -15 art（上移 10 显示px）；套装键 x=前键右缘-6（素材间距 10→4px）；简介四模块 `addSpacing(8)+addStretch(1)` 均布铺满内容区；第六十六轮下移+白框+透明度回退（`9f15fb6`）：整块 +8 art（下移 5 显示px）、边框纯白 #ffffff、未选中键弃压暗叠层恢复透明度法 0.45→0.65；第六十五轮吸附+换色+变暗（`3c16a9d`）：两键素材底缘=卡顶缘（y=473，弃半嵌骑边）、边框换 #d6a880（原 #c9955e 太扎眼）、未选中键弃 0.45 透明度改暖色压暗叠层（110,68,40,α55）；第六十四轮好感改名+背景卡真边框（`9f77de1`）：简介节「好感度」→「好感」；region_bg 3px #c9955e 外框（**真 bug：`setClipPath(空 QPainterPath)`=裁掉一切，51/52 轮的画笔描边从未渲染，历史所见是素材烘焙框且左右被 ByExpanding 裁 32px——解除裁剪必须 `setClipping(False)`**）；第六十三轮悬浮横向截断（`02bc179`）：悬浮矩形外扩后 KeepAspectRatio 从高度受限翻转为宽度受限，素材横向 +11px 超出 3px 余量被裁——`side_margin` 3→5 + 素材基准矩形横向内缩（**坑位：悬浮放大限制维度会翻转，余量按最坏轴预留**；曾误诊源图截断做镜像加宽已撤销）；第六十二轮两键放大20%（`e477185`）：`tab_scale=1.2` 素材高 32→38（简介 140×38/套装 139×38），左缘对齐内容区 229、紧贴 6px、中线不变；第六十一轮紧靠（`9f57f46`）：60 轮方向理解反了——用户要的是**靠在一起**：widget 按素材实宽收窄（±3px 悬浮余量，124/123×40）、两键相接素材间距 6px（简介 art x=229 不动，套装 353），顺带修掉旧 154 宽 widget 重叠抢点击的隐患；第六十轮键距拉开（`40c9403`）：键距 216→247 art（+24 显示px，素材间距 14→38，套装 x 343→362）；第五十九轮简介新素材+文件名归位（`d13ad05`）：46 轮的映射对调实为**素材文件内容互换**——套装图迁回 `tab_outfit.png`、用户新简介图（1672×455）进 `tab_intro.png`、`TAB_SLOTS` 恢复自然映射、两键同尺寸 154×40（撤 ±10%）；第五十八轮两键±10%+顶裁修复（`7c0daf9`）：简介键长 -10%（素材 117×32→106×29）、套装 +10%（134×32→146×35），中线保持 y=466；**悬浮顶裁 BUG：自绘控件 QPainter 只能在 widget 内作画，悬浮外扩 2px 触顶被裁——`_TabButton` 加 headroom=4（widget 上下余量、素材原位）；关键认知：素材高度受限（比例 3.66/4.18<键 4.81），改宽不变、等比改高才生效**；第五十七轮上移10px（`15861a6`）：`TAB_BAR_AT`/`CONTENT_AT` y 各减 15 art（整块-10 显示px）；**分栏键实测 154×32 显示px（名义 art 250×72 被双重缩放——先乘 _SX/_SY 再过 _R，历史轮记的尺寸是名义值非屏上实尺寸）**；第五十六轮套装卡加宽（`8e50f38`）：`_outfit_layout` 左右边距 8/14→2/4（卡宽 +16 显示px，描述三行→两行）；第五十五轮内框删除（`321f239`）：套装卡 QSS 裸 `QWidget` 选择器会把虚线框泄漏给卡内图片/动画 QLabel——改 objectName 限定（`QWidget#outfitCard`），只留外围框（**坑位：卡片级 QSS 边框必须 objectName 限定**）；第五十四轮图标竖跨两行（`532fb78`）：简介四节改「左图标（60×fit AlignVCenter 占两行）+ 右侧节名/数值两行文字列（stretch 1 防提前换行）」，`_section_header`→`_intro_section`，新增结构测试（40 条）；第五十三轮数值行对齐图标（`1ef14c9`）；第五十二轮图标放大（`3aa0d8b`）：节图标两行高度（60×fit）、套装虚线框恢复、背景框加粗 #c9955e；第五十轮统一描边（`fcc323b`）：区域背景暖棕实线 #d6a880 唯一描边、套装卡内框全删、背景放大（宽+30 高+40 art）；第四十九轮补齐（进度条全删/卡内虚线/白描边已弃）；第四十八轮虚线描边（`4a02980`）：套装卡描边改 2px dashed #d6a880；第四十七轮描边与增大（`f418b72`）：分栏 +20%（250×72）、内容上移 30、区域背景+套装卡暖棕描边（#d6a880）；第四十六轮分栏素材互换（`6791cf9`）：简介位=tab_outfit、套装位=tab_intro（按用户确认对调）；第四十五轮骑背景边（`3aafa31`）：背景下移 50（TAB_BAR y736/CONTENT y788）、分栏按钮增大 30%（208×60）严格骑背景上边缘（不是内容区）；第四十二轮分栏骑边（`89849d3`）：分栏按钮几何走 `_R` 换算（**存量 bug：此前直接用 art px 当显示 px，按钮位置总不对的根因**），骑在内容区上边缘半嵌；内容区下移 50 显示px；第三十九轮圆角统一背景（`332e7c4`）：`_RoundedBgLabel`（radius 28 圆角裁剪）绘 `region_background.png`（Combined_29，jieshao/taozhuang 保留备用），两枚素材分栏按钮骑背景顶边（raise_）；第三十八轮去框换景（`e39e8d5`）：`_FramedStack` 虚线外框删除（_content 回 QStackedWidget），`_show_tab` 时 `_region_bg` 画 jieshao/taozhuang 背景随页互换（上轮只建 label 没接图），两页内部重复 bg_label 删除（曾顶出背景）；第三十七轮区域覆盖（`18f1540`）：`_region_bg` 背景图覆盖分栏+内容整块（每页换 jieshao/taozhuang），参考图裁切 `tab_intro/tab_outfit` 作素材分栏按钮（选中全彩/未选中半透明 0.45，悬停放大按住缩小松开切换）；description_bg 横条弃用；坑位：参考图按钮须按内容 bbox 裁切，TAB_SLOTS 变「名称→素材文件名」；第三十六轮素材化（`831a175`）：进度条 track/fill 贴图（整条素材按中线色变拆分 x=279）、star/heart/paw/leaf 图标节标（icon+标题行）、简介/套装页背景图垫底；坑位：整条进度素材须拆 track/fill、节头变 icon 行后测试取文本用 findChildren(QLabel)；第三十五轮进度条真的移动（`1cbc782`）：`_MiniBar` 重写——数值变化 450ms OutCubic 缓动滑动（_display_value 浮点驱动）、2.4s 周期高光带循环扫过（clip 到填充内）；坑位：QVariantAnimation 存比例值（0..1）；第三十四轮 C 位置还原（`10811b1`）：34B 的全局 -50 是误解语义（用户指背景素材裁剪，非 UI 平移），全部还原到 y230/272/470 等原位；region_background 裁剪保留；坑位：**'裁背景'≠'平移 UI'，先确认语义再动手**；第三十四轮切换提速（`281641e`）：**帧缓存** `_IDLE_FRAMES_CACHE`（pet_id+anim_key+height）+ 首帧后台预热（singleShot 预载全部动画帧）——切换 250ms→6-15ms、测试 11s→3.4s；反馈略减（缩 3px/黑闪 α60）；**坑位：QPixmap 在无 QApplication 时调用、或 singleShot 槽在窗口销毁后触发 → qFatal 静默终止（rc=127 无 traceback），槽必须 try/except RuntimeError；涉及 QPixmap 的测试必须放在有 QApplication 的类**；第三十三轮横滚修复（`1446f1e`）：套装图定框 150×126 等比（防按高缩放过宽挤爆行）、文字 min-width 280、动画框 130——横滚 0；第三十二轮头像式按住（`89f16b9`）：`_ArtButton` 改**按住持续缩小+压暗（alpha 80）直至松开**、内松开立即执行、拖走取消——与 `_AvatarButton` 完全一致（两段定时动画仅家园按键保留）；文字行宽 +10 显示px；第三十一轮：触发链 `_pending_fire` 修复、黑闪限素材区、行宽自适应（QFontMetrics 折行测量超 2 行加高卡）；第三十轮：全按键 release-inside、穿装动画等比方形、装备钮 190×60；第二十八轮：套装卡=左图+右文+右侧穿装动画（idle_dinosaur/idle_strawberry，高 160）；坑位：pyqtSignal 必须类属性（实例属性无 connect）；第二十七轮套装页商店化（滚动条入框 contentsMargins 10+商店手柄 QSS、框下限上移 10、区块左移 20 x279）；第二十六轮：改名组件右移+名字居中+_FramedStack 浅色虚线外框；第二十五轮：头像框 118px、选中淡琥珀虚线；坑位：`_R` 双比例会把正方形拉成长方形——方形 UI 用 setFixedSize 固定像素边长；第二十三轮 `_AvatarButton` 自绘整幅头像——坑位：QPushButton iconSize≥可用区必裁切；_ArtButton 绘制必须 KeepAspectRatio 居中（drawPixmap(rect,pm) 拉伸压扁，第二十二轮 `8b7bc82` 修）；QSS 洗色反馈只适合规则形控件；此前：切换卡/改名键/idle 动画/两行数值（`225ef4c`），壳 0.7 比例 841×913 圆角 64、paintEvent 圆角裁剪 30px（`CORNER_RADIUS`）叠 background+base_UI、拖拽/居中入口沿用；`pet_profile_snapshot` 数据层与套装预览路径修复保留。旧艺术稿布局（`2e59452`）用户评估搁置，旧素材目录 `ui/pet_profile/` 暂留待清理。**长期规则：所有按键必须带悬停+点击两态反馈**（已入 AGENTS.md）。详见 Obsidian `宠物系统\宠物详情面板新素材重建记录` |

### v1.6.3（当前）

| 领域 | 内容 |
|------|------|
| **小屋宠物键素材** | 菜单「宠物」键（action `pets`）原本无素材走程序绘制兜底（`HOME_BUTTON_PATHS` 只注册了 `pet`=抚摸键）；新增 `buttons/pets.png`（睡窝柴犬横幅，提交 `f6406a4`）。**素材比例 3.03 vs 槽位 2.5**：从狗窝与爪印间的虚线空档精确裁 292px（≈6×顶线节距 48.2/5.9×底线 49.3，接缝相位误差 <1px 渲染）拼接成 2.487，零变形；运行时「宠物」标签照常画在空白区 |
| **家园性能** | `load_pet_registry` 按 mtime 缓存；`current_pet_id` 记忆化；墙面状态卡按内容签名缓存；`home_decoration_transform` 纯读取不跑全量 ensure——paintEvent 从 ~100ms 降到 ~2ms |
| **胶囊按键反馈** | 两段式：按下缩小 3px+灰黑块 40ms → 回弹原大小+悬浮描边/白洗 40ms → 80ms 时关闭菜单并触发动作（`_click_defer_timer`，总时长短于旧版单段 100ms）；悬停放大 3px + 描边 + 白洗 |
| **影子实测驱动** | 冰淇淋家园行走影子按当前帧 alpha 实测倾角与脚掌中心（`_ice_shadow_params`，QBuffer→BytesIO→PIL），四向方向数学保证正确；预加载消除首次卡顿 |
| ** painter save 泄漏** | `_draw_action_button` 内两个 save 配一个 restore（编辑残留），泄漏导致装饰面板被裁剪吞掉+置顶错觉——已修 |
| **菜单/圆形按钮键名匹配** | `_hit_scene_button` 存带前缀键（`menu:shop`/`toggle:interaction`），paint 拿裸名比较——恒 None 导致反馈不生效；已改为统一走 `_button_state(name)` |
| **恐龙装拖拽动画** | 8 帧原色版接入 `outfits/dinosaur/drag`，套装感知播放，未装备回退共享 drag |
| **喂食循环修复** | home 场景停了桌面 tick 导致 behavior="eat" 永不超时——`trigger_animation` 加 finished_callback 复位 behavior |
| **睡觉亮度还原** | 恢复通道烘焙前的原始帧（git checkout ecbeee7~1） |
| **NOACTIVATE 移除** | `Qt.WindowDoesNotAcceptFocus` 导致小屋窗口无法被其它程序覆盖——已删 |
| **小屋可拖动** | 非装饰模式下空白处按住拖动整个小屋窗口（`_window_drag_offset`） |

### v1.6.2

| 领域 | 内容 |
|------|------|
| **商店徽标+反馈统一** | 免费/使用中/已拥有素材缩 5%（47→45、50→48）；四页页首小字删除；`FeedbackButton` 升级为**真缩放反馈**（延迟抓素颜帧整体缩放：悬浮放大 2px+白洗描边、按住内缩 3px+压暗、松开键内回弹 40ms 后触发，checkable 原生时序；**坑位：paint 事件内 render 抓帧真机抓到空帧致整键消失——必须延迟到事件循环抓**）；**家园按键语义迁移**：按住持续内缩、松开键内回弹 40ms 后触发、拖走取消（弃 80ms 自动触发，`BUTTON_CLICK_DEFER_MS` 删除）；**装修面板按键**（关闭/分类签/放置收纳）并入两段式状态机（`_hit_decoration_button`；坑位：press 与 hover 是两条独立链路，mouseMove 的 hover 追踪也要接 `_hit_decoration_button`）；装修卡文字行加高居中（名字 23→32px 居中、动作 27→30px，`67413c5`）；**按键交互规范入 AGENTS.md**（`e8d4da8`..`9a1f293`） |
| **面板统一** | 商店/成就/记录/设置/小游戏/聊天统一 850×960 + 暖色素材 + 屏幕居中 |
| **成就筛选** | 合并为六大类（全部/互动/聊天/游戏/换装强化/成长），未来新前缀自动归"其它" |
| **温暖记录** | 按小狗划分：总计页共有数值 + 每宠页签独立数据；时长改小时制 |
| **设置页** | 三档偏好胶囊滑动选择；字体档位 小 20 / 中 24 / 大 26；移除聊天窗口大小设置 |
| **聊天** | 头像 60px；字体全局幼圆；历史区透明；口播去"汪" |

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
| `ShopWindow` | `petpet/progression/ui.py` | 商店四页、固定标签栏、page header、scroll body、CoinPillLabel |
| `AchievementsWindow` | `petpet/progression/ui.py` | 成就页、shop_theme、固定总览/筛选栏、前缀过滤 |
| `RecordsWindow` | `petpet/progression/ui.py` | 记录页（shop_theme 850×960，按宠页签） |
| `CozyProgressWindow` | `petpet/progression/ui.py` | 无边框壳、标题栏/币量/关闭、shop_theme/title_image、背景绘制、`show_near_pet` 居中+滚动清零 |
| `FeedbackButton` | `petpet/progression/ui.py` | 悬浮/按下叠加层、手型光标 |
| `PurchasePopup` | `petpet/progression/ui.py` | 购买确认弹窗、商店背景裁切圆角、Esc/遮罩关闭 |
| `HomeSceneWindow` | `petpet/home/window.py` | 家园场景、交互按钮（实测影子/反馈）、装饰面板、窗口拖动 |
| `HomePetController` | `petpet/home/pet.py` | 2.5D 移动/走路/睡觉/自主漫游（3 秒玩家指令闸门） |
| `SettingsWindow` | `petpet/ui/settings.py` | 设置页（shop 背景 850×960、胶囊字体选择、无置顶） |

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
| 版本发布 | 更新 `version.py` + README + 发布说明 → `scripts/release.ps1 -Version X.Y.Z` |

**测试约束**：
- `QT_QPA_PLATFORM=offscreen` 跑全量（~80s，707 passed）
- Windows 平台截图需真实字体库（offscreen 无字体数据库，渲染会缺字）
- `setPixmap` 会清空 `QLabel.text()` → 必须用 `PreservedTextLabel` 保留文本

---

## 8. 常见坑位 & 应对

| 现象 | 原因 | 修复 |
|------|------|------|
| 重启后"完全没变化" | 进程活着但**所有窗口 `IsWindowVisible=0`** | 再起一遍实例触发单实例召回（`activate_existing_instance`） |
| 价格签/徽章有残留底纹 | QSS `border-image` 与 `border` 互不覆盖 | 内联补 `border-image: none; background: transparent; border: 0;` |
| `QLabel.setPixmap` 导致文字消失 | Qt 行为 | 用 `PreservedTextLabel` 存 `_stored_text` |
| offscreen 下 `QFontDatabase.addApplicationFont` 崩 | 平台限制 | 仅在 `main()` 真实启动时调用 |
| PowerShell `Set-Content -Encoding UTF8` 写 BOM → ast 解析失败 | PS 5.1 默认加 BOM | 用 `[System.IO.File]::WriteAllText(..., New-Object System.Text.UTF8Encoding($false))` 无 BOM 写入 |
| paintEvent / Qt 槽内未捕获异常 | **PyQt5 对槽内异常直接终止进程**，无输出无 traceback | 所有槽/绘制函数加 try/except 或确保不抛 |
| `sip.voidptr` 无 `asarray` / `bytes(ptr)` 无 size | PyQt5 constBits() 返回值不可直接用 | 用 `QBuffer`→`bytes(buffer.data())`→PIL，或 `ptr.setsize(n)` 后 `bytes(ptr)` |
| `QPainterPath.addEllipse(QRect)` 原生段错误 | 本机 PyQt5 构建的 QRect 重载 bug | 传 `QRectF` 而非 `QRect` |
| `QImage.mirrored()` 后 `constBits()` 尺寸异常 | 镜像后 stride 对齐变化 | 用 `QBuffer`→PNG→PIL 路径替代 |
| 影子像素 diff 有大量变化 | 小狗动画帧在动，不是悬停效果 | 冻结动画定时器后再做像素 diff |

---

## 9. 待办 / 可迭代方向

1. **发布脚本健壮化**：release.ps1 可加"自动停本机宠物进程"步骤，避免冒烟测试撞单实例锁
2. **动画素材扩充**：冰淇淋走/吃/抚摸等动作用已跑通的"生成→导入→对色→接线"流水线批量补齐
3. **长期记忆**：结构化记录用户信息并在对话中自然召回
4. **CI**：GitHub Actions 跑 offscreen pytest + Windows self-hosted 跑渲染对比
5. **打包**：PyInstaller / Nuitka 单文件 + 资源内嵌（当前需带 assets 目录）

---

## 10. 关键文档

- **Obsidian 文档规范**（写库前必读，归类/命名/流程的唯一规则源）：`D:\Github Desktop\My-Obsidian\项目\Petpet\文档规范.md`
- **Obsidian 总档案**：`D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`（只放项目级总览；2026-09-01 已拆分瘦身，日志类内容全部在各分类目录）
- **Obsidian 开发记录**：`D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\`（按日命名 `YYYY-MM-DD 主题.md`；最新：`2026-09-05 小屋宠物按键新素材.md`、`2026-09-01 小屋按键两段式按压反馈.md`、`2026-08-27 成就分类筛选与弹窗交互完善.md` 含 v1.6.1→v1.6.3 全部迭代细节）
- **版本规划索引**：`D:\Github Desktop\My-Obsidian\项目\Petpet\发布系统\版本规划与发布索引.md`
- **最新 Release**：https://github.com/Gsheen76/Petpet/releases/tag/v1.6.3

---

> **核心原则**：视觉改动**必须**经历"offscreen 全量测试 → Windows 平台截图 → 精确重启（EnumWindows 验证可见） → Obsidian 记录"四步，方可视为完成。
> **切勿**在未验证可见性的情况下假设代码生效。
> **注意**：PyQt5 槽/绘制事件内未捕获异常 = 无输出静默崩溃；影子像素 diff 必须冻结动画定时器。
