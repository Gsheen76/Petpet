# Task 1 Report: Pet Assets By ID

Date: 2026-08-21

## Implementation

- Moved runtime desktop pet assets from `assets/runtime/pets/desktop/` to `assets/runtime/pets/lunch_meat/desktop/`.
- Moved runtime home pet assets from `assets/runtime/pets/home/` to `assets/runtime/pets/ice_cream/home/`.
- Updated `assets/runtime/pets/manifest.json` so every pet-owned asset path now starts with `pets/<pet_id>/`.
- Preserved lunch meat's home fallback as its own desktop idle asset: `pets/lunch_meat/desktop/poses/idle.png`.
- Kept ice cream home actions on its own home assets under `pets/ice_cream/home/poses/`.
- Updated compatibility constants in `petpet/app/paths.py` so `POSES_DIR` points at lunch meat desktop assets and `HOME_POSES_DIR` points at `pets/ice_cream/home/poses` for legacy home size/crop code.
- Updated test expectations across registry, path, packaging, chat, animation-color, and home-window coverage to reflect the per-ID runtime layout.
- Added a packaging assertion that legacy shared pet directories `assets/runtime/pets/desktop` and `assets/runtime/pets/home` no longer exist.

## Files Changed

- `assets/runtime/pets/manifest.json`
- `assets/runtime/pets/lunch_meat/desktop/**` (renamed from `assets/runtime/pets/desktop/**`)
- `assets/runtime/pets/ice_cream/home/**` (renamed from `assets/runtime/pets/home/**`)
- `petpet/app/paths.py`
- `tests/test_animation_colors.py`
- `tests/test_app_paths.py`
- `tests/test_chat_tools.py`
- `tests/test_home_window_boundary.py`
- `tests/test_packaging_assets.py`
- `tests/test_pet_registry.py`

## RED / GREEN Evidence

### RED

Command:

```powershell
python -m pytest tests/test_pet_registry.py::test_registered_assets_are_owned_by_the_selected_pet -q
```

Result:

- Exit code `1`
- Failed because lunch meat desktop idle still resolved to the old shared path:

```text
E AssertionError: assert False
E ... '.../assets/runtime/pets/desktop/poses/idle.png'.endswith(
E     'pets/lunch_meat/desktop/poses/idle.png'
E )
```

### GREEN

Focused task verification:

```powershell
python -m pytest tests/test_app_paths.py tests/test_pet_registry.py tests/test_packaging_assets.py -q
```

- Exit code `0`
- `23 passed in 0.54s`

Regression follow-up after updating stale expectations outside the focused slice:

```powershell
python -m pytest tests/test_animation_colors.py tests/test_chat_tools.py tests/test_home_window_boundary.py -q
```

- Exit code `0`
- `53 passed in 6.20s`

Final full-suite verification:

```powershell
python -m pytest -q
```

- Exit code `0`
- `604 passed in 77.29s (0:01:17)`

## Verification Commands And Results

```powershell
python -m pytest tests/test_pet_registry.py::test_registered_assets_are_owned_by_the_selected_pet -q
```

- RED confirmed, exit code `1`

```powershell
python -m pytest tests/test_app_paths.py tests/test_pet_registry.py tests/test_packaging_assets.py -q
```

- PASS, exit code `0`, `23 passed in 0.54s`

```powershell
python -m pytest tests/test_animation_colors.py tests/test_chat_tools.py tests/test_home_window_boundary.py -q
```

- PASS, exit code `0`, `53 passed in 6.20s`

```powershell
python -m pytest -q
```

- PASS, exit code `0`, `604 passed in 77.29s (0:01:17)`

```powershell
python -m compileall -q petpet pet.py tests
```

- PASS, exit code `0`

```powershell
git -C 'D:\Agent_project\Petpet\.worktrees\pet-assets-by-id' diff --check
```

- Exit code `0`
- Git emitted CRLF normalization warnings for edited files, but no diff-check whitespace errors.

## Self-Review

- Verified the runtime move stayed inside pet-owned domains only; shared scenes, furniture, props, sounds, decorations, knowledge, and source assets were not moved.
- Verified lunch meat home fallback remains lunch meat's own desktop idle asset.
- Verified ice cream home idle/sleep/walk actions resolve under `pets/ice_cream/home/`.
- Verified old shared pet runtime directories are now absent through packaging tests.
- Reviewed the diff for accidental scope creep; only manifest/path wiring, expected test updates, and tracked asset renames are included.

## Concerns

- No functional concerns from this task.
- `git diff --check` reported only line-ending normalization warnings, not content errors.
- I could not use a dedicated review subagent in this session because the collaboration tooling for spawning one was unavailable here, so I compensated with manual diff review plus full verification.
