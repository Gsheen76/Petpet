# 宠物 ID 资源目录迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将运行时宠物资源按宠物 ID 组织，并把冰淇淋 4×4 图集导入为当前宠物同步使用的 16 帧待机动画。

**Architecture:** `manifest.json` 是宠物专属资源的唯一入口；桌面窗口和现有家园窗口都用 `pet_asset_path()` 解析当前活动宠物。旧共享运行时宠物目录被移动到午餐肉和冰淇淋各自目录，`paths.py` 的兼容常量只保留冰淇淋家园尺寸裁剪所需的默认路径。

**Tech Stack:** Python 3、PyQt5、Pillow、pytest、PyInstaller 资源打包。

## Global Constraints

- 宠物专属运行时资源必须位于 `assets/runtime/pets/<pet_id>/`。
- 冰淇淋待机图集是 4×4 共 16 帧，按行优先完整导出 `000.png` 至 `015.png`。
- 桌面与家园始终显示活动宠物；午餐肉缺少家园动作时只能回退到午餐肉自身待机图。
- 家具、场景、通用音效、通用道具和 `assets/source/` 不迁移。
- 不改宠物 ID、价格、存档格式、购买规则或共享资源路径。

---

### Task 1: 迁移宠物运行时目录并更新资源注册表

**Files:**
- Modify: `assets/runtime/pets/manifest.json`
- Move: `assets/runtime/pets/desktop/` → `assets/runtime/pets/lunch_meat/desktop/`
- Move: `assets/runtime/pets/home/` → `assets/runtime/pets/ice_cream/home/`
- Modify: `petpet/app/paths.py:86-95`
- Modify: `tests/test_app_paths.py:45-58`
- Modify: `tests/test_pet_registry.py:40-48`
- Modify: `tests/test_packaging_assets.py:42-83`

**Interfaces:**
- Consumes: `pet_asset_path(pet_id: str, scene: str, action: str = "idle") -> str | None`。
- Produces: manifest 中所有资源路径均以 `pets/<pet_id>/` 开头；`HOME_POSES_DIR` 指向 `pets/ice_cream/home/poses`，仅保留既有尺寸裁剪兼容用途。

- [ ] **Step 1: 写入失败的资源边界测试**

```python
def test_registered_assets_are_owned_by_the_selected_pet():
    assert pet_asset_path("lunch_meat", "desktop", "idle").endswith(
        "pets/lunch_meat/desktop/poses/idle.png"
    )
    assert pet_asset_path("ice_cream", "home", "idle").endswith(
        "pets/ice_cream/home/poses/home-pet-idle-sit.png"
    )
    assert pet_asset_path("lunch_meat", "home", "sleep").endswith(
        "pets/lunch_meat/desktop/poses/idle.png"
    )
```

- [ ] **Step 2: 运行测试确认旧共享路径导致失败**

Run: `python -m pytest tests/test_pet_registry.py::test_registered_assets_are_owned_by_the_selected_pet -q`

Expected: FAIL，当前 manifest 仍解析 `pets/desktop` 或 `pets/home`。

- [ ] **Step 3: 最小化迁移和 manifest 更新**

```powershell
New-Item -ItemType Directory -Force assets/runtime/pets/lunch_meat,assets/runtime/pets/ice_cream
git mv assets/runtime/pets/desktop assets/runtime/pets/lunch_meat/desktop
git mv assets/runtime/pets/home assets/runtime/pets/ice_cream/home
```

更新 `lunch_meat` 的桌面 root/动画 manifest/预览，并为其 home 配置自身桌面 idle；更新 `ice_cream` 的预览、桌面和 home 路径。将 `paths.py` 的兼容常量改到新目录；共享场景、家具、道具、音效和 source 目录不得移动。

- [ ] **Step 4: 运行聚焦测试确认通过**

Run: `python -m pytest tests/test_app_paths.py tests/test_pet_registry.py tests/test_packaging_assets.py -q`

Expected: PASS；打包仍递归包含 `assets/runtime`，且旧 `pets/desktop`、`pets/home` 不存在。

- [ ] **Step 5: 提交迁移**

```bash
git add assets/runtime/pets petpet/app/paths.py tests/test_app_paths.py tests/test_pet_registry.py tests/test_packaging_assets.py
git commit -m "refactor: organize pet assets by id"
```

### Task 2: 导入冰淇淋 16 帧桌面待机图

**Files:**
- Modify: `tools/slice_sprite_sheet.py`
- Modify: `assets/runtime/pets/ice_cream/desktop/animations/manifest.json`
- Create: `assets/runtime/pets/ice_cream/desktop/animations/idle/000.png` through `015.png`
- Create: `assets/runtime/pets/ice_cream/desktop/poses/idle.png`
- Modify: `assets/runtime/pets/manifest.json`
- Modify: `tests/test_packaging_assets.py`

**Interfaces:**
- Consumes: `tools/slice_sprite_sheet.py IMAGE ACTION --columns 4 --rows 4 --frames 16 --output-dir PATH`。
- Produces: 16 个 640×640 RGBA 待机帧；manifest 的 `ice_cream.desktop.animations_manifest` 指向冰淇淋自己的动画 manifest。

- [ ] **Step 1: 写入失败的冰淇淋图集验收测试**

```python
def test_ice_cream_idle_has_all_sixteen_transparent_frames(self):
    folder = root / "assets/runtime/pets/ice_cream/desktop/animations/idle"
    frames = [folder / f"{index:03d}.png" for index in range(16)]
    self.assertTrue(all(path.is_file() for path in frames))
    image = QImage(str(frames[0]))
    self.assertEqual(image.size().width(), 640)
    self.assertEqual(image.size().height(), 640)
    self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
```

- [ ] **Step 2: 运行测试确认帧尚未导入而失败**

Run: `python -m pytest tests/test_packaging_assets.py::PackagingAssetTests::test_ice_cream_idle_has_all_sixteen_transparent_frames -q`

Expected: FAIL，冰淇淋 idle 文件夹尚不存在。

- [ ] **Step 3: 让切图工具支持明确输出目录并导入图集**

```python
parser.add_argument("--output-dir", type=Path, required=True)
output_dir = args.output_dir
```

对 alpha 小于 8 的背景像素设为 0，保留角色边缘；使用用户文件 `C:\Users\sheen\Downloads\job_e34141f5408f40449bb5313a04d9db0d-transparent.png` 执行：

```powershell
python tools/slice_sprite_sheet.py C:\Users\sheen\Downloads\job_e34141f5408f40449bb5313a04d9db0d-transparent.png idle --columns 4 --rows 4 --frames 16 --output-dir assets/runtime/pets/ice_cream/desktop/animations/idle
```

将 `000.png` 复制为 `desktop/poses/idle.png`；写入仅含 `idle` 的 16 帧循环动画 manifest，保持帧序为 0 至 15。

- [ ] **Step 4: 运行聚焦测试确认通过**

Run: `python -m pytest tests/test_packaging_assets.py tests/test_pet_registry.py -q`

Expected: PASS；16 帧、尺寸、透明角像素和冰淇淋桌面 manifest 均符合要求。

- [ ] **Step 5: 提交动画资源**

```bash
git add tools/slice_sprite_sheet.py assets/runtime/pets/ice_cream tests/test_packaging_assets.py assets/runtime/pets/manifest.json
git commit -m "feat: add ice cream idle animation"
```

### Task 3: 同步项目与 Obsidian 记录并验证完整行为

**Files:**
- Modify: `docs/superpowers/specs/2026-08-21-pet-assets-by-id-design.md`
- Modify: `docs/superpowers/plans/2026-08-21-pet-assets-by-id.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\商店信息与双列布局设计.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\开发记录\商店信息与双列布局实施计划.md`

**Interfaces:**
- Consumes: 两项迁移提交及验证输出。
- Produces: 项目规格、实施计划和 Obsidian 记录的相同最终目录/16 帧/当前宠物同步说明。

- [ ] **Step 1: 更新实施结果**

在四份 Markdown 中写明 `pets/<pet_id>/` 结构、冰淇淋 `000–015` 16 帧、桌面/家园读取活动宠物和午餐肉自身 idle 回退；记录实际测试计数，不预设版本号。

- [ ] **Step 2: 运行最终验证**

Run: `python -m pytest -q; python -m compileall -q petpet pet.py tests; git diff --check`

Expected: 全量 pytest 通过；编译与空白检查退出码 0。

- [ ] **Step 3: 提交记录**

```bash
git add docs/superpowers/specs/2026-08-21-pet-assets-by-id-design.md docs/superpowers/plans/2026-08-21-pet-assets-by-id.md
git commit -m "docs: record pet asset migration"
```
