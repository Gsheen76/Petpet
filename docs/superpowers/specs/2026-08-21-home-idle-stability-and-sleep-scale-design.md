# 家园待机稳定与睡眠尺寸设计

## 背景

用户观察到两只宠物在家园待机时会持续产生微小左右晃动；午餐肉进入睡眠后又明显比待机和走路状态大。

家园待机目前通过 `PetWindow.shared_animation_frame()` 获取桌面动画当前帧。`HomeSceneWindow.home_pet_render_spec()` 每一帧都调用 `home_pet_static_source_rect()`，根据当前图片的非透明边界生成新的源矩形，再把这个源矩形居中绘制到固定世界坐标。

## 根因证据

对午餐肉和冰淇淋各 16 张待机帧进行 alpha 边界分析后得到：

- 午餐肉部分图片在画布边缘存在 alpha 值为 1 的几乎不可见残点。当前 `QPixmap.mask()` 把这些残点视为有效内容，使单帧边界在 `(0, 0, 455, 593)`、`(170, 0, 640, 593)`、`(186, 76, 455, 593)` 等位置间变化。
- 当前逐帧裁剪换算到家园显示空间后，午餐肉的 alpha 质心横向跨度约为 `37.023px`。
- 冰淇淋帧的左边界在 `80..115` 之间变化，当前家园 alpha 质心横向跨度约为 `4.267px`。
- Qt 原生 `QImage.createAlphaMask(Qt.ThresholdDither)` 可以在 C++ 层忽略低透明残点。对全部帧取联合边界后，午餐肉得到 `(111, 77, 342, 514)`，冰淇淋得到 `(83, 88, 408, 458)`。
- 使用 Qt 阈值统一联合边界后，午餐肉的剩余质心跨度约为 `2.986px`，冰淇淋约为 `0.375px`；剩余变化来自角色动画本身，而不是裁剪框反复居中。

睡眠尺寸方面，家园专用睡眠素材的源矩形约为 `592×288`，现有 `visual_scale=0.62` 会得到约 `146.8×71.4px` 的横躺目标矩形。用户确认把睡眠比例统一改为 `0.50`，目标约为 `118.4×57.6px`。

## 目标

- 午餐肉和冰淇淋在家园待机时不再因逐帧裁剪产生左右抖动。
- 保留动画作者实际制作的呼吸、眨眼、尾巴等帧内动作，不强行冻结角色。
- 两只宠物睡眠时使用各自注册的家园睡眠素材，显示比例统一为 `0.50`。
- 睡眠、待机和走路继续使用同一个世界坐标脚底锚点。
- 阴影位置保持与宠物脚底匹配，不跟随逐帧透明边界左右跳动。
- 不修改 PNG 资源，不增加运行依赖，不改变桌面动画显示。

## 方案比较

### 方案 A：统一 alpha 联合边界并缓存（采用）

对当前共享动画已经加载的全部帧使用 Qt 原生阈值 alpha mask，取所有有效边界的联合矩形。家园绘制同一动画的每一帧时使用同一个源矩形，并按宠物 ID 与动画名缓存结果。宠物切换或资源刷新时清空缓存。

优点是直接消除逐帧裁剪重新居中的根因，不改资源，不引入依赖，新增宠物也会自动获得相同行为。

### 方案 B：逐张修正 PNG 画布和角色位置

可以在资源层彻底统一边界，但午餐肉、冰淇淋及未来每套动画都要人工处理，且容易破坏原始帧动作和透明边缘，不采用。

### 方案 C：对家园目标矩形位置做插值平滑

能够降低视觉跳动，却保留了错误的逐帧边界，角色仍会缓慢漂移；状态切换时也可能积累延迟，不采用。

## 详细设计

### 1. Qt 原生稳定联合边界

在 `petpet/home/rendering.py` 增加纯渲染 helper：

```python
home_pet_animation_source_rect(frames: Sequence[QPixmap]) -> QRect
```

行为：

1. 跳过空对象和 `isNull()` 帧。
2. 对每张有效帧调用 `toImage().createAlphaMask(Qt.ThresholdDither)`。
3. 把 alpha mask 转为 `QBitmap`，再用 `QRegion(...).boundingRect()` 得到阈值可见边界。
4. 对所有非空边界取 `QRect.united()`。
5. 如果没有有效阈值边界，回退到第一张有效帧的 `home_pet_static_source_rect()`；如果没有有效帧，返回空 `QRect()`。

该 helper 只使用已有 PyQt5，不使用 Pillow、NumPy 或 Python 逐像素循环。

### 2. 家园共享动画裁剪缓存

`HomeSceneWindow` 维护 `_home_pet_animation_source_rects` 字典，键为 `(current_pet_id, animation_name)`，值为稳定联合矩形。

`home_pet_render_spec()` 取得共享帧后：

- 从桌面宠物的 `animation_frames[animation_name]` 读取已加载帧序列；
- 第一次遇到该键时调用 `home_pet_animation_source_rect()` 并缓存；
- 后续帧直接使用缓存矩形；
- 如果动画序列缺失或结果为空，回退到当前帧的 `home_pet_static_source_rect()`。

`refresh_pet_assets()` 和 `refresh_active_pet()` 的资源切换路径清空缓存，确保不同宠物或重新加载后的帧不会共用旧边界。

### 3. 睡眠素材与尺寸

当 `home_pet.state == "sleeping"` 时，`home_pet_render_spec()` 先进入家园睡眠分支，不再被桌面共享动画分支提前截获。

- 使用当前宠物注册的 `self.home_pet_sleep`。
- spritesheet 继续使用现有 `home_pet_sleep_source_rect(frame)` 和 8 帧 cadence。
- 静态回退继续使用 `_home_pet_sleep_source_rect`。
- `visual_scale` 从 `0.62` 改为用户确认的 `0.50`。
- 睡眠仍不绘制脚底阴影，保持现有视觉规则。

### 4. 脚底与阴影

目标矩形继续由 `home_pet_draw_rect()` 以固定世界坐标 `world_x/world_y` 计算，统一源矩形只决定长宽比，不修改世界坐标。

待机的 `contact_center_x`、`contact_width`、`contact_foot_y` 继续作为同一动画的稳定比例使用，因此阴影中心不会随当前帧裁剪边界变化。走路逐帧接触点保持不变。

## 测试设计

### 联合边界 helper

使用两张真实 `QPixmap/QImage` 测试帧：主体矩形位置不同，并在画布边缘加入 alpha 值为 1 的残点。断言：

- 结果包含两帧的阈值主体；
- 结果不包含低透明边缘残点；
- 空帧安全回退。

### 两只宠物待机稳定性

加载午餐肉和冰淇淋的真实待机序列，断言每只宠物所有共享待机帧生成的 `render_spec.source_rect` 完全相同；连续帧的 `home_pet_render_rect()` 左边和宽度保持相同。

### 睡眠尺寸

构造家园睡眠状态并让桌面共享帧可用，断言：

- 仍选择当前宠物的 `home_pet_sleep`，而不是桌面共享睡眠帧；
- `visual_scale == 0.50`；
- 目标矩形宽高约为 `118.4×57.6px`；
- 午餐肉和冰淇淋切换后均使用各自的睡眠资源。

### 回归

- 家园走路、手动睡眠、自动睡眠、宠物切换和阴影测试继续通过。
- 运行家园焦点测试和完整 `python -m pytest -q`。
- 运行 `python -m py_compile` 与 `git diff --check`。

## 交付

- 设计、实施计划、代码和测试提交到用户指定的 `main`。
- 把根因、比例、提交和验证结果同步到 Obsidian Petpet 开发记录。
- 完整验证后重启 `D:\Agent_project\Petpet\pet.py`，供用户检查待机稳定性和睡眠尺寸。
