# 午餐肉家园移动动画设计

## 目标

让午餐肉在家园中的手动、自动和前往睡眠点移动时播放连贯的 8 帧行走动画，不影响冰淇淋已有的家园四向动画。

## 现状

午餐肉已有 `assets/runtime/pets/lunch_meat/desktop/animations/walk/000.png` 至 `007.png` 八帧原生行走资源。家园未登记午餐肉的 `walk_down` / `walk_back_right`，因此当前回退为静态待机图。

## 方案

- 不生成新图：直接复用午餐肉现有桌面 `walk` 八帧，保持角色、毛发与动作连续性。
- `HomeSceneWindow.refresh_pet_assets()` 仅在缺少专属家园行走图时预载当前宠物的桌面 walk 帧；缺帧时继续使用现有待机回退。
- `home_pet_walk_render_spec()` 按既有 `HOME_PET_WALK_FPS` 选择帧，使用整段帧的 alpha 并集裁剪稳定显示尺寸；左向镜像，右向保持原始朝向。
- 行走显示高度为家园标准比例 `1.0`，脚底接触和阴影沿用家园既有逻辑。

## 验证

- 回归测试覆盖午餐肉桌面帧被登记为 `desktop_animation`、帧索引推进、镜像方向和缺帧待机回退。
- 运行家园焦点测试和全量 pytest；重启源码小狗进行家园人工验证。
