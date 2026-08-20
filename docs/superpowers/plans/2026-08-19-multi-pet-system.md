# 多宠物系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将桌面宠物和家园宠物统一为由 `active_pet_id` 驱动的可购买、可切换多宠物系统，首期统一显示午餐肉，并在商店展示冰淇淋。

**Architecture:** 保留单一 `pet_state.json`，把数据分成玩家共享区和以稳定宠物 ID 为键的独立宠物区。新增运行资源注册表提供场景资源解析和当前宠物待机回退；桌面、家园、聊天和商店都通过同一当前宠物状态工作，切换由应用控制器统一保存并刷新两个场景。

**Tech Stack:** Python 3.11、PyQt5、JSON、Pillow/Qt 资源加载、pytest。

## Global Constraints

- `lunch_meat` 是新用户默认拥有并激活的宠物，默认名字为“午餐肉”。
- `ice_cream` 使用当前家园小狗的资源来源，首期显示在“宠物”商店但不默认拥有；原价 `1000` Pet币，按 `76 折`销售，实际价格 `760` Pet币。售价只从注册表读取，购买时扣除玩家共享 Pet币。
- 等级、经验、Pet币、家具、成就、强化和玩家进度共享。
- 饱腹、心情、精力、好感、昵称、位置和聊天记忆按宠物独立保存。
- 桌面和家园使用同一个 `active_pet_id`，切换后同步显示同一只宠物。
- 缺少动作资源时回退当前宠物自己的静态待机图，不借用另一只宠物的动作。
- 商店不增加复杂动作预览槽位；缺失资源可以使用待机图或简单方块占位，正式资源替换时不改存档接口。
- 旧 `desktop/home` 双档案和旧 `memory.json`/`memory-home.json` 必须可迁移，迁移幂等且不重复发放货币。
- 保留根目录兼容入口，不把新包内实现反向依赖到根目录兼容模块。
- Windows/macOS 打包继续只包含 `assets/runtime`，制作源图继续放在 `assets/source`。

---

## 文件地图

| 文件 | 责任 |
|---|---|
| `petpet/app/pets.py` | 宠物注册表、稳定 ID、资源路径和动作回退 |
| `assets/runtime/pets/manifest.json` | 午餐肉、冰淇淋的运行资源声明 |
| `petpet/app/state.py` | 玩家共享区、宠物独立区、旧存档迁移和活动宠物投影 |
| `petpet/chat/memory.py`、`petpet/chat/api.py` | 按宠物 ID 保存、迁移和读取聊天记忆 |
| `petpet/app/pet_window.py` | 桌面当前宠物资源加载、动画和切换刷新 |
| `petpet/home/rendering.py`、`petpet/home/window.py` | 家园当前宠物资源加载、缺图回退和切换刷新 |
| `petpet/progression/core.py` | 宠物拥有、购买和共享 Pet币结算规则 |
| `petpet/progression/ui.py` | “宠物”商店页面、预览、购买和切换按钮 |
| `pet.py` | 应用级切换协调、聊天名称同步、桌面/家园刷新 |
| `tests/test_pet_registry.py` | 注册表和资源回退测试 |
| `tests/test_app_state.py`、`tests/test_pet_state_io.py` | 存档迁移、共享/独立字段和幂等性测试 |
| `tests/test_chat_memory.py`、`tests/test_chat_window_boundary.py` | 按宠物记忆隔离和聊天切换测试 |
| `tests/test_pet_window_boundary.py`、`tests/test_home_window_boundary.py` | 两场景资源和刷新测试 |
| `tests/test_progression.py`、`tests/test_progression_ui_boundary.py` | 宠物经济和商店状态测试 |
| `README.md`、`assets/runtime/knowledge/game_knowledge.json` | 面向玩家的功能说明和聊天知识库 |

## Task 1: 建立宠物注册表和资源解析边界

**Files:**
- Create: `petpet/app/pets.py`
- Create: `assets/runtime/pets/manifest.json`
- Create: `tests/test_pet_registry.py`
- Modify: `petpet/app/paths.py`

**Interfaces:**
- `petpet.app.pets.DEFAULT_PET_ID: str`，值为 `lunch_meat`。
- `petpet.app.pets.load_pet_registry() -> dict[str, dict]`，读取 manifest 并对路径、ID、默认名做最小校验。
- `petpet.app.pets.pet_definition(pet_id: str) -> dict`，未知 ID 回退到 `lunch_meat`。
- `petpet.app.pets.pet_asset_path(pet_id: str, scene: str, action: str = "idle") -> str | None`，按“当前动作 → 当前宠物 idle → 当前宠物 preview”顺序回退，只返回存在的文件。
- `petpet.app.pets.pet_display_name(pet_id: str, state: dict) -> str`，读取该宠物昵称并回退注册表默认名。

- [ ] **Step 1: Write the failing tests**

```python
def test_registry_contains_lunch_meat_and_ice_cream():
    registry = load_pet_registry()
    assert registry["lunch_meat"]["default_name"] == "午餐肉"
    assert registry["ice_cream"]["default_name"] == "冰淇淋"


def test_missing_action_falls_back_to_current_pet_idle():
    assert pet_asset_path("ice_cream", "desktop", "play").endswith(
        "pets/home/poses/home-pet-idle-sit.png"
    )


def test_unknown_pet_falls_back_to_default():
    assert pet_definition("unknown")["id"] == "lunch_meat"
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `python -m pytest -q tests/test_pet_registry.py`

Expected: FAIL because the registry module, manifest, and resource resolver do not exist.

- [ ] **Step 3: Add the registry and manifest**

Declare existing resources without copying files. The first manifest entries must resolve as follows:

```json
{
  "lunch_meat": {
    "id": "lunch_meat",
    "default_name": "午餐肉",
    "price": 0,
    "preview": "pets/desktop/poses/idle.png",
    "desktop": {
      "root": "pets/desktop",
      "animations_manifest": "pets/desktop/animations/manifest.json"
    },
    "home": {"idle": "pets/desktop/poses/idle.png"}
  },
  "ice_cream": {
    "id": "ice_cream",
    "default_name": "冰淇淋",
    "original_price": 1000,
    "discount": 0.76,
    "price": 760,
    "preview": "pets/home/poses/home-pet-idle-sit.png",
    "desktop": {"idle": "pets/home/poses/home-pet-idle-sit.png"},
    "home": {
      "idle": "pets/home/poses/home-pet-idle-sit.png",
      "walk_down": "pets/home/poses/home-pet-walk-down.png",
      "walk_back_right": "pets/home/poses/home-pet-walk-back-right.png",
      "sleep": "pets/home/poses/home-pet-sleep.png"
    }
  }
}
```

Use `ASSETS_DIR` as the only root, reject paths that escape it, and return `None` only after all current-pet fallbacks are absent.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_pet_registry.py tests/test_app_paths.py`

Expected: PASS.

- [ ] **Step 5: Commit the resource boundary**

```powershell
git add petpet/app/pets.py petpet/app/paths.py assets/runtime/pets/manifest.json tests/test_pet_registry.py
git commit -m "feat: add multi-pet resource registry"
```

## Task 2: Migrate the state model to stable pet IDs

**Files:**
- Modify: `petpet/app/state.py`
- Modify: `pet.py`
- Modify: `tests/test_app_state.py`
- Modify: `tests/test_pet_state_io.py`

**Interfaces:**
- `ensure_state_schema(state, default_pet_name, normalize_pet_name) -> dict` keeps the existing call signature and creates `active_pet_id`, `owned_pet_ids`, `player`, and `pets[lunch_meat]`.
- `active_pet_profile(state) -> dict` returns the active pet profile.
- `capture_active_pet(state) -> dict` copies the legacy top-level pet facade into the active profile.
- `bind_active_pet(state, pet_id) -> dict` captures the old active profile, switches `active_pet_id`, and projects the new profile to the legacy top-level facade.
- `pet_profile(state, pet_id) -> dict` returns a normalized independent pet profile without changing the active pet.

- [ ] **Step 1: Add failing migration and isolation tests**

```python
def test_legacy_desktop_home_profiles_migrate_to_lunch_meat():
    state = ensure_state_schema(
        {"pet_name": "小肉", "hunger": 12, "pets": {
            "desktop": {"pet_name": "小肉", "hunger": 12},
            "home": {"pet_name": "旧家园", "hunger": 88},
        }},
        "午餐肉",
        lambda value: str(value or "午餐肉"),
    )
    assert state["active_pet_id"] == "lunch_meat"
    assert state["pets"]["lunch_meat"]["pet_name"] == "小肉"
    assert state["pets"]["lunch_meat"]["hunger"] == 12


def test_switch_keeps_player_data_and_isolates_pet_data():
    state = ensure_state_schema(
        {},
        "午餐肉",
        lambda value: str(value or "午餐肉"),
    )
    state["player"]["pet_coins"] = 100
    state["pets"]["ice_cream"] = {
        "pet_name": "冰淇淋",
        "hunger": 80,
        "mood": 70,
        "energy": 90,
        "affection_level": 1,
        "affection_points": 0,
        "passive_affection_buffer": 0.0,
        "affection_last_gains": {},
        "sleeping": False,
        "sleep_mode": None,
        "x": None,
        "y": None,
        "equipped_decorations": {},
        "decoration_adjustments": {},
    }
    state["pets"]["lunch_meat"]["hunger"] = 20
    bind_active_pet(state, "ice_cream")
    state["hunger"] = 90
    capture_active_pet(state)
    assert state["player"]["pet_coins"] == 100
    assert state["pets"]["lunch_meat"]["hunger"] == 20
    assert state["pets"]["ice_cream"]["hunger"] == 90
```

- [ ] **Step 2: Run state tests and verify failure**

Run: `python -m pytest -q tests/test_app_state.py tests/test_pet_state_io.py`

Expected: FAIL because the current schema uses `desktop` and `home` as profile keys and has no active pet ID.

- [ ] **Step 3: Implement the stable-ID schema and compatibility facade**

Move player-owned fields to `state["player"]`, move `PET_FIELDS` to `state["pets"][pet_id]`, and preserve top-level aliases only while existing callers migrate. Convert legacy `pets.desktop` and `pets.home` into `lunch_meat`; do not duplicate or merge values on the second load. Add per-pet `desktop_position`, `home_position`, `chat_memory_key`, and `equipped_outfit` fields. Keep `home_scene` furniture and camera data in the player section.

Update `load_state()` and `save_state()` so every load normalizes the schema and every save captures the active facade before serializing. Existing records, Pet币, furniture, upgrades, achievements, and tutorial flags remain in `player`.

- [ ] **Step 4: Run focused and regression tests**

Run: `python -m pytest -q tests/test_app_state.py tests/test_pet_state_io.py tests/test_progression.py`

Expected: PASS, with old compatibility tests updated only where their expected profile key changes from `desktop/home` to `lunch_meat/ice_cream`.

- [ ] **Step 5: Commit the state migration**

```powershell
git add petpet/app/state.py pet.py tests/test_app_state.py tests/test_pet_state_io.py
git commit -m "feat: migrate saves to stable pet identities"
```

## Task 3: Isolate chat memory by pet identity

**Files:**
- Modify: `petpet/chat/memory.py`
- Modify: `petpet/chat/api.py`
- Modify: `petpet/ui/chat.py`
- Modify: `pet.py`
- Modify: `tests/test_chat_memory.py`
- Modify: `tests/test_chat_window_boundary.py`

**Interfaces:**
- `normalize_memory_pet_id(value) -> str` accepts registered IDs and maps old `desktop`/`home` calls to `lunch_meat`.
- `memory_path(pet_id="lunch_meat") -> str` keeps lunch meat at `memory.json` and stores other identities as `memory-<pet_id>.json`.
- `load_memory(pet_id="lunch_meat") -> dict` migrates old `memory-home.json` into the lunch meat profile once when needed.
- `save_memory(memory, pet_id="lunch_meat") -> None` writes only that pet’s memory.
- `set_pet_name(name, pet_id="lunch_meat") -> None` updates the selected pet profile instead of one global name.

- [ ] **Step 1: Write failing memory-isolation tests**

```python
def test_pet_memories_use_separate_files(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", str(tmp_path))
    lunch = {"pet_name": "午餐肉", "history": [{"role": "user", "content": "肉松"}]}
    ice = {"pet_name": "冰淇淋", "history": [{"role": "user", "content": "甜筒"}]}
    api.save_memory(lunch, "lunch_meat")
    api.save_memory(ice, "ice_cream")
    assert api.load_memory("lunch_meat")["history"][0]["content"] == "肉松"
    assert api.load_memory("ice_cream")["history"][0]["content"] == "甜筒"


def test_old_home_memory_is_migrated_to_lunch_meat(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", str(tmp_path))
    write_json(tmp_path / "memory-home.json", {"history": [{"role": "assistant", "content": "旧记录"}]})
    assert "旧记录" in str(api.load_memory("lunch_meat"))
```

- [ ] **Step 2: Run chat tests and verify failure**

Run: `python -m pytest -q tests/test_chat_memory.py tests/test_chat_window_boundary.py`

Expected: FAIL because the current API only knows `desktop` and `home` profiles.

- [ ] **Step 3: Implement pet-ID memory paths and UI propagation**

Replace profile-specific branching with pet-ID paths while preserving `profile="desktop"` and `profile="home"` as compatibility aliases. Pass the active pet ID from `PetWindow`/application controller into `ChatWindow`, prompt construction, history loading, image-thumbnail cleanup, and name refresh. Opening chat after a switch must load the selected pet’s history; switching must not delete the previous pet’s history.

- [ ] **Step 4: Run focused chat tests**

Run: `python -m pytest -q tests/test_chat_memory.py tests/test_chat_window_boundary.py tests/test_chat_service.py tests/test_buddy_ai_boundary.py`

Expected: PASS.

- [ ] **Step 5: Commit the memory boundary**

```powershell
git add petpet/chat/memory.py petpet/chat/api.py petpet/ui/chat.py pet.py tests/test_chat_memory.py tests/test_chat_window_boundary.py
git commit -m "feat: isolate chat memory by pet"
```

## Task 4: Make the desktop renderer resolve the active pet

**Files:**
- Modify: `petpet/app/pet_window.py`
- Modify: `petpet/app/paths.py`
- Modify: `pet.py`
- Modify: `tests/test_pet_window_boundary.py`
- Modify: `tests/test_animation_colors.py`

**Interfaces:**
- `PetWindow.refresh_pet_assets(pet_id: str | None = None) -> None` reloads static poses, idle/action paths and preview cache for the selected pet.
- `PetWindow.set_active_pet(pet_id: str) -> None` captures the current state through the application callback, switches the profile, reloads assets, resets the animation to the selected pet idle, and updates the UI name.
- `PetWindow.current_pet_id -> str` exposes the selected ID to the app and chat UI.

- [ ] **Step 1: Add failing desktop asset tests**

```python
def test_desktop_asset_lookup_uses_active_pet():
    assert pet_asset_path("ice_cream", "desktop", "idle").endswith(
        "pets/home/poses/home-pet-idle-sit.png"
    )


def test_missing_ice_cream_action_returns_ice_cream_idle():
    assert pet_asset_path("ice_cream", "desktop", "play").endswith(
        "home-pet-idle-sit.png"
    )
```

- [ ] **Step 2: Run desktop boundary tests and verify failure**

Run: `python -m pytest -q tests/test_pet_window_boundary.py tests/test_animation_colors.py`

Expected: FAIL because `PetWindow` imports fixed desktop paths at module load and has no refresh method.

- [ ] **Step 3: Move path selection behind the resolver**

Keep the existing animation state machine and memory limits. Replace fixed `POSES_DIR`/`ANIMATIONS_DIR` reads with the current pet asset resolver; rebuild frame paths on refresh, retain only preloaded/active frames, and use current-pet idle when an action directory is absent. Keep outfit animation lookup separate so outfit data does not become a pet identity.

- [ ] **Step 4: Run desktop tests**

Run: `python -m pytest -q tests/test_pet_window_boundary.py tests/test_animation_colors.py tests/test_petting_animation.py tests/test_sleep_interaction.py`

Expected: PASS.

- [ ] **Step 5: Commit desktop resource resolution**

```powershell
git add petpet/app/pet_window.py petpet/app/paths.py pet.py tests/test_pet_window_boundary.py tests/test_animation_colors.py
git commit -m "feat: render the active pet on desktop"
```

## Task 5: Make the home renderer resolve the active pet

**Files:**
- Modify: `petpet/home/rendering.py`
- Modify: `petpet/home/window.py`
- Modify: `petpet/home/pet.py`
- Modify: `tests/test_home_window_boundary.py`
- Modify: `tests/test_home_rendering_boundary.py`
- Modify: `tests/test_home_pet_boundary.py`

**Interfaces:**
- `HomeSceneWindow.refresh_pet_assets(pet_id: str | None = None) -> None` loads the selected pet’s idle, walk and sleep assets.
- `HomeSceneWindow.home_pet_asset_state() -> dict` returns the loaded asset availability for boundary tests.
- `HomeSceneWindow._save_home_pet_position()` writes the current controller position into the active pet’s `home_position`, not a single global pet position.

- [ ] **Step 1: Add failing home rendering tests**

```python
def test_lunch_meat_home_uses_desktop_idle_asset(home_window):
    home_window.refresh_pet_assets("lunch_meat")
    assert home_window.home_pet_asset_state()["idle"].endswith("pets/desktop/poses/idle.png")


def test_missing_home_walk_falls_back_to_active_pet_idle(home_window):
    home_window.refresh_pet_assets("lunch_meat")
    assert home_window.home_pet_asset_state()["walk"] == "idle"


def test_home_position_is_saved_per_pet(home_window):
    home_window.state["active_pet_id"] = "ice_cream"
    home_window.home_pet.position = (321.0, 455.0)
    home_window._save_home_pet_position()
    assert home_window.state["pets"]["ice_cream"]["home_position"] == [321.0, 455.0]
```

- [ ] **Step 2: Run home tests and verify failure**

Run: `python -m pytest -q tests/test_home_window_boundary.py tests/test_home_rendering_boundary.py tests/test_home_pet_boundary.py`

Expected: FAIL because home paths and the saved position are fixed to the old home asset/profile.

- [ ] **Step 3: Implement active-pet home assets and fallback**

Generalize the render spec to accept a full static pixmap as a source rectangle. Keep the existing ice cream sprite-sheet slicing for its available walk/sleep resources. For lunch meat, use its desktop idle image as home idle and use it for walk/sleep/interaction fallback until authored assets exist. Preserve foot anchoring, depth scaling, furniture sorting, camera behavior, and home-only movement state.

- [ ] **Step 4: Run home regression tests**

Run: `python -m pytest -q tests/test_home_window_boundary.py tests/test_home_rendering_boundary.py tests/test_home_pet_boundary.py tests/test_home_scene.py tests/test_scene_system.py`

Expected: PASS.

- [ ] **Step 5: Commit home resource resolution**

```powershell
git add petpet/home/rendering.py petpet/home/window.py petpet/home/pet.py tests/test_home_window_boundary.py tests/test_home_rendering_boundary.py tests/test_home_pet_boundary.py
git commit -m "feat: render the active pet in the home"
```

## Task 6: Add shared pet economy rules and the “宠物” shop page

**Files:**
- Modify: `petpet/progression/core.py`
- Modify: `petpet/progression/ui.py`
- Modify: `tests/test_progression.py`
- Modify: `tests/test_progression_ui_boundary.py`

**Interfaces:**
- `pet_owned(state, pet_id: str) -> bool` reads shared `owned_pet_ids`.
- `purchase_pet(state, pet_id: str) -> dict` validates the registry item, charges shared Pet币 once, adds the ID, and returns `{ok, message, pet_id}`.
- `available_pet_ids() -> tuple[str, ...]` returns registry order for deterministic UI.
- `ShopWindow._build_pets_page()` renders the two initial cards and uses callbacks supplied by `pet.py` for switching and saving.

- [ ] **Step 1: Add failing purchase and UI tests**

```python
def test_purchase_pet_uses_shared_coins_once():
    state = {
        "player": {
            "pet_coins": 900,
            "owned_pet_ids": ["lunch_meat"],
        },
        "owned_pet_ids": ["lunch_meat"],
        "pets": {"lunch_meat": {"pet_name": "午餐肉"}},
    }
    result = purchase_pet(state, "ice_cream")
    assert result["ok"] is True
    assert result["price"] == 760
    assert result["original_price"] == 1000
    assert result["discount"] == 0.76
    assert state["player"]["pet_coins"] == 140
    assert state["owned_pet_ids"] == ["lunch_meat", "ice_cream"]
    assert purchase_pet(state, "ice_cream")["ok"] is False


def test_shop_pages_include_pets_before_outfits(shop_window):
    shop_window.refresh()
    assert shop_window.page_ids() == ("pets", "outfits", "home", "upgrades")
```

- [ ] **Step 2: Run progression tests and verify failure**

Run: `python -m pytest -q tests/test_progression.py tests/test_progression_ui_boundary.py`

Expected: FAIL because the progression layer and shop have no pet definitions or pets page.

- [ ] **Step 3: Implement shared purchase rules and cards**

Keep purchase state in shared player data, do not copy Pet币 into a pet profile. Add the `宠物` tab before `套装`; each card must show the preview image, current nickname/default name, price or owned status, and a single purchase/switch action. Use a simple colored block or the pet idle pixmap when a preview asset is missing; do not add action slots. The page must refresh after purchase or switching without destroying the whole app.

- [ ] **Step 4: Run progression/UI tests**

Run: `python -m pytest -q tests/test_progression.py tests/test_progression_ui_boundary.py tests/test_progression_integration.py`

Expected: PASS.

- [ ] **Step 5: Commit the pet shop**

```powershell
git add petpet/progression/core.py petpet/progression/ui.py tests/test_progression.py tests/test_progression_ui_boundary.py
git commit -m "feat: add pet shop purchases"
```

## Task 7: Coordinate switching, names, positions, and live windows

**Files:**
- Modify: `pet.py`
- Modify: `petpet/app/pet_window.py`
- Modify: `petpet/home/window.py`
- Modify: `petpet/ui/chat.py`
- Modify: `tests/test_desktop_surfaces_boundary.py`
- Modify: `tests/test_home_window_boundary.py`
- Modify: `tests/test_chat_window_boundary.py`

**Interfaces:**
- `TrayApp.set_active_pet(pet_id: str) -> dict` captures the active facade, validates ownership, switches the state profile, saves, refreshes desktop/home resources, updates the tray tooltip and refreshes open chat/shop windows.
- `PetWindow.set_pet_name(value: str) -> str` writes the active pet profile and active chat memory name.
- `HomeSceneWindow.refresh_active_pet() -> None` resets its controller from the active pet’s `home_position` and refreshes assets.

- [ ] **Step 1: Add failing synchronization tests**

```python
def test_switch_refreshes_desktop_and_home_and_keeps_shared_progress(app):
    app.state["player"]["pet_coins"] = 123
    app.state["owned_pet_ids"].append("ice_cream")
    result = app.set_active_pet("ice_cream")
    assert result["ok"] is True
    assert app.pet.current_pet_id == "ice_cream"
    assert app.home_scene_window.current_pet_id == "ice_cream"
    assert app.state["player"]["pet_coins"] == 123


def test_names_and_chat_memory_follow_active_pet(app):
    app.set_active_pet("ice_cream")
    app.pet.set_pet_name("甜筒")
    app.set_active_pet("lunch_meat")
    assert app.pet.pet_name == "午餐肉"
    app.set_active_pet("ice_cream")
    assert app.pet.pet_name == "甜筒"
```

- [ ] **Step 2: Run synchronization tests and verify failure**

Run: `python -m pytest -q tests/test_desktop_surfaces_boundary.py tests/test_home_window_boundary.py tests/test_chat_window_boundary.py`

Expected: FAIL because there is no application-level switch method and the two windows retain fixed resources.

- [ ] **Step 3: Implement one application-level switch transaction**

Perform the following in `TrayApp.set_active_pet`: validate the ID and ownership, call `capture_active_pet`, update `active_pet_id`, call `bind_active_pet`, persist once, call both window refresh methods, update `ai.set_pet_name(name, pet_id)`, and refresh any visible chat/shop/records surfaces. If a refresh fails because a window has already been closed, leave the saved state valid and recreate the window lazily on its next open.

Make the shop invoke this callback rather than mutating `active_pet_id` itself. Save the per-pet desktop position during close/restore and the per-pet home position whenever the home controller moves or exits.

- [ ] **Step 4: Run live-window boundary tests**

Run: `python -m pytest -q tests/test_desktop_surfaces_boundary.py tests/test_home_window_boundary.py tests/test_chat_window_boundary.py tests/test_menu_ui.py tests/test_onboarding.py`

Expected: PASS.

- [ ] **Step 5: Commit synchronized switching**

```powershell
git add pet.py petpet/app/pet_window.py petpet/home/window.py petpet/ui/chat.py tests/test_desktop_surfaces_boundary.py tests/test_home_window_boundary.py tests/test_chat_window_boundary.py
git commit -m "feat: synchronize active pet switching"
```

## Task 8: Update player-facing documentation and knowledge

**Files:**
- Modify: `README.md`
- Modify: `assets/runtime/knowledge/game_knowledge.json`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\Petpet 总档案.md`
- Modify: `D:\Github Desktop\My-Obsidian\项目\Petpet\宠物系统\多宠物系统设计.md`

**Interfaces:**
- README must describe the “宠物” shop, lunch meat default, ice cream availability, shared/independent data, and missing-animation fallback.
- Game knowledge must describe only behavior actually implemented and use the new `active_pet_id` model’s player-facing wording, not file internals.
- Obsidian records must distinguish implemented behavior from pending resource work.

- [ ] **Step 1: Add documentation contract assertions**

```python
def test_readme_documents_multi_pet_behavior():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "宠物" in readme
    assert "午餐肉" in readme
    assert "冰淇淋" in readme
    assert "active_pet_id" not in readme
```

- [ ] **Step 2: Run the documentation test and verify failure**

Run: `python -m pytest -q tests/test_release_metadata.py`

Expected: the new assertions fail until README and knowledge wording are updated.

- [ ] **Step 3: Update docs without claiming unfinished animations are complete**

Document the user-visible shop and switching behavior. Keep placeholder/fallback wording explicit until the formal animation files are uploaded. Update the Obsidian total archive and design note with the implementation date only after the code and tests pass. Do not create release notes or change `version.py` in this feature task; the release version will be selected after GUI acceptance.

- [ ] **Step 4: Run documentation and knowledge tests**

Run: `python -m pytest -q tests/test_release_metadata.py tests/test_game_knowledge.py`

Expected: PASS.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md assets/runtime/knowledge/game_knowledge.json
git commit -m "docs: document multi-pet behavior"
```

## Task 9: Full verification and release readiness

**Files:**
- Verify all files changed in Tasks 1-8.

- [ ] **Step 1: Run focused multi-pet tests**

```powershell
python -m pytest -q tests/test_pet_registry.py tests/test_app_state.py tests/test_pet_state_io.py tests/test_chat_memory.py tests/test_chat_window_boundary.py tests/test_pet_window_boundary.py tests/test_home_window_boundary.py tests/test_progression.py tests/test_progression_ui_boundary.py
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the full test suite**

```powershell
python -m pytest -q
```

Expected: zero failures; record the exact count in the Obsidian implementation record.

- [ ] **Step 3: Run static and packaging checks**

```powershell
python -m compileall -q petpet pet.py tests
git diff --check
```

Expected: both commands exit with code 0 and no whitespace errors.

- [ ] **Step 4: Verify resource/package boundaries**

```powershell
python -m pytest -q tests/test_packaging_assets.py tests/test_windows_packaging.py tests/test_release_metadata.py
```

Expected: both PyInstaller specs still collect `assets/runtime` only; no source reference image is packaged.

- [ ] **Step 5: Perform GUI smoke verification**

Run `python pet.py`, confirm both visible scenes show午餐肉, open `右键 → 商店 → 宠物`, confirm the冰淇淋 card, purchase/switch with a test save, verify both scenes switch together, and confirm the previous pet’s attributes and chat history return when switching back.

- [ ] **Step 6: Update the implementation records**

Record the exact tests, smoke result, resource count, and any formal animation files still absent in `Petpet 总档案.md` and `宠物系统/多宠物系统设计.md`. Do not mark a missing-animation item as complete merely because fallback rendering works.
