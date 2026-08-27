
## Review Fixes (2026-08-19)

- Corrected `pet_asset_path()` ordering to check the requested current-pet action, root-derived action, current-pet idle, root-derived idle, then preview.
- Added a regression test proving a valid root-derived action wins over an explicit idle asset.
- Replaced hard-coded path-key validation with recursive dict/list traversal using path-bearing keys and path containers, while leaving non-path metadata untouched.
- Added a nested list/dict escape test for unknown `asset_path` fields.
- Added checks for `DEFAULT_PET_ID`, the required `lunch_meat` manifest entry, and ice cream pricing fields.
- Normalized unknown pet IDs to the default definition before reading nickname state.

### Review-fix verification

- `python -m pytest -q tests/test_pet_registry.py tests/test_app_paths.py tests/test_packaging_assets.py tests/test_windows_packaging.py tests/test_release_metadata.py`
  - `34 passed`
- `python -m compileall -q petpet pet.py tests`
  - Passed with no output.
- `git diff --check`
  - Passed; Git emitted only its normal LF/CRLF working-copy warning for `petpet/app/paths.py`.

### Commit status

Commit was attempted but remains blocked because the linked worktree Git metadata cannot create `.git/worktrees/home-scene-system/index.lock` under the available permissions. The elevated retry was rejected by the approval service. The Task 1 implementation and review-fix changes are left in the working tree; design/spec/plan documents were not modified.
