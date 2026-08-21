# Task 2 Report: Ice Cream Desktop Idle Animation

## Implementation

- Extended `tools/slice_sprite_sheet.py` to accept optional `--output-dir` while preserving the existing equal-cell validation and frame-count bounds.
- Added alpha cleanup in the slicer so output pixels with alpha below `8` are written back as fully transparent.
- Generated `assets/runtime/pets/ice_cream/desktop/animations/idle/000.png` through `015.png` from `C:\Users\sheen\Downloads\job_e34141f5408f40449bb5313a04d9db0d-transparent.png`.
- Copied `000.png` to `assets/runtime/pets/ice_cream/desktop/poses/idle.png`.
- Added `assets/runtime/pets/ice_cream/desktop/animations/manifest.json` with a single looping `idle` animation at `8` FPS and fallback `idle`.
- Updated `assets/runtime/pets/manifest.json` so `ice_cream.desktop` now points to its own `root` and `animations_manifest`.
- Updated stale desktop fallback assertions in registry-related tests to expect `pets/ice_cream/desktop/poses/idle.png`.

## RED / GREEN Evidence

### RED

Command:

```powershell
python -m pytest tests/test_packaging_assets.py::PackagingAssetTests::test_ice_cream_idle_has_all_sixteen_transparent_frames -q
```

Result:

```text
FAILED tests/test_packaging_assets.py::PackagingAssetTests::test_ice_cream_idle_has_all_sixteen_transparent_frames
AssertionError: False is not true : D:\Agent_project\Petpet\.worktrees\pet-assets-by-id\assets\runtime\pets\ice_cream\desktop\animations\idle
```

Failure reason matched expectation: the `ice_cream` desktop idle animation directory did not exist yet.

### GREEN

Command:

```powershell
python -m pytest tests/test_packaging_assets.py tests/test_pet_registry.py -q
```

Result:

```text
19 passed in 0.76s
```

Command:

```powershell
python -m pytest tests/test_animation_colors.py -q
```

Result:

```text
4 passed in 0.29s
```

Command:

```powershell
python -m pytest -q
```

Result:

```text
605 passed in 81.25s (0:01:21)
```

## Test Commands And Results

1. `python -m pytest tests/test_packaging_assets.py::PackagingAssetTests::test_ice_cream_idle_has_all_sixteen_transparent_frames -q`
   - Failed as expected before implementation because the idle frame directory was missing.
2. `python -m pytest tests/test_packaging_assets.py tests/test_pet_registry.py -q`
   - Passed: `19 passed in 0.76s`.
3. `python -m pytest tests/test_animation_colors.py -q`
   - Passed after updating stale fallback expectations: `4 passed in 0.29s`.
4. `python -m pytest -q`
   - Passed: `605 passed in 81.25s (0:01:21)`.
5. `python -m compileall -q petpet pet.py tests`
   - Passed with exit code `0`.
6. `git diff --check`
   - Passed with exit code `0` and only line-ending warnings from Git.

## Files Changed

- `tools/slice_sprite_sheet.py`
- `assets/runtime/pets/manifest.json`
- `assets/runtime/pets/ice_cream/desktop/animations/manifest.json`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/000.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/001.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/002.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/003.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/004.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/005.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/006.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/007.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/008.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/009.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/010.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/011.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/012.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/013.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/014.png`
- `assets/runtime/pets/ice_cream/desktop/animations/idle/015.png`
- `assets/runtime/pets/ice_cream/desktop/poses/idle.png`
- `tests/test_packaging_assets.py`
- `tests/test_pet_registry.py`
- `tests/test_animation_colors.py`
- `.superpowers/sdd/2026-08-21-pet-assets-by-id/task-2-report.md`

## Self-Review

- Confirmed the generated source sheet split row-major into exactly `000` through `015`.
- Verified the committed runtime frames are `640x640` `RGBA` PNGs with transparent top-left pixels.
- Checked that the desktop window will load frames in lexical order because `pet_window.py` sorts PNG filenames by basename.
- Kept `lunch_meat` and shared runtime resources untouched.

## Concerns

- `git diff --check` reported only LF-to-CRLF warnings in the working copy; there were no whitespace errors or malformed patches.
