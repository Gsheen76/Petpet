# Petpet 动画素材规范（v2，2026-09-04 素材治理轮更新）

本目录 `assets/source/spritesheets/` 是**开发期源稿**：AI 生成的精灵表、
关键帧草稿都放这里，**不随程序打包**（打包只带 `assets/runtime/`）。
运行时正式素材一律放 `assets/runtime/pets/<pet_id>/…`。

## 目录结构（现行，按宠物组织）

```text
assets/runtime/pets/<pet_id>/
├── avatar.png                     # 方形头像（聊天/详情面板）
├── desktop/
│   ├── poses/<动作>.png           # 静态姿势（缺失动画时的回退图）
│   └── animations/
│       ├── manifest.json          # 动画声明（folder/fps/loop/fallback/…）
│       ├── idle/000.png …         # 连续帧，三位数字命名
│       └── outfits/<套装>/<动作>/… # 套装专属动画
└── home/                          # 家园场景素材（poses/ 或整张精灵表）
```

动画缺失时程序回退到 `poses/<同名>.png`；连静态图也没有则按
manifest 的 `fallback` 字段落到对应姿势。**manifest 里允许预声明
尚不存在的文件夹**（如 happy/sad/sit/ask），加载器会优雅跳过。

## 命名规范（强制，守卫测试 tests/test_asset_inventory.py 会拦）

- 全库 `assets/runtime/` 文件名：**纯 ASCII、snake_case**
  `^[a-z0-9_]+\.(png|wav|json)$`；例外：动画帧 `^\d{3}\.png$`、图标 `icon-\d{2,4}\.png`
- 禁止中文文件名、大写、连字符（历史 kebab 已于 2026-09-04 全部治理）
- `assets/source/` 无此约束（开发稿自由命名，kebab 可）

## 制作流程

1. 用 AI 生成规则精灵表（4 列 × 2 行起步），存到本目录
2. 拆帧（务必用 `--output-dir` 指到目标宠物目录）：

   ```powershell
   python tools\slice_sprite_sheet.py 精灵表.png walk --columns 4 --rows 2 `
       --output-dir assets\runtime\pets\lunch_meat\desktop\animations\walk
   ```

3. 在该宠物的 `animations/manifest.json` 里声明 `folder/fps/loop/fallback`
4. 跑 `pytest`；帧数与 manifest 声明要一致

## 每帧要求（不变）

- PNG 透明背景，推荐 512×512；小狗朝向按宠物 registry `facing` 固定
- 所有帧画布、镜头、缩放、身体中心、脚底基线一致
- 不含文字/边框/编号/地面/裁切线；阴影要么全一致要么全不要
- 帧按播放顺序命名 `000.png`、`001.png`…

## 历史源稿索引

本目录现存的 `*-generated.png` / `*keyframes*.png` / `pet_hand.png` 是
已导入运行时的历史中间稿，仅作再生成参考，无代码引用。
