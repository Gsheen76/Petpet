# Package Skeleton and Paths Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the `petpet` package and move the path implementation into it while preserving every existing import and the `python pet.py` launcher.

**Architecture:** `petpet.app.paths` becomes the single implementation of runtime, asset, and writable-data path resolution. The root `app_paths.py` remains a compatibility facade that explicitly re-exports the current public constants and migration helpers, so the rest of the application can move incrementally in later phases.

**Tech Stack:** Python 3.11, standard library, unittest/pytest, PyInstaller.

## Global Constraints

- Keep root `pet.py` as the permanent source and packaged launcher.
- Do not add dependencies, plugin systems, event buses, or dependency injection.
- Do not use `git reset` or `git checkout`, and do not overwrite unrelated uncommitted changes.
- Write a failing test before implementation, then run focused tests and `python -m pytest -q`.
- Keep root imports compatible throughout the migration.
- Do not commit, push, tag, or release unless the user explicitly requests it.
- Keep the Obsidian project archive synchronized automatically.

---

### Task 1: Establish the package path boundary

**Files:**
- Create: `petpet/__init__.py`
- Create: `petpet/app/__init__.py`
- Create: `petpet/app/paths.py`
- Modify: `app_paths.py`
- Modify: `tests/test_app_paths.py`
- Test: `tests/test_app_paths.py`

**Interfaces:**
- Consumes: the current root `app_paths.py` constants and helper functions.
- Produces: `petpet.app.paths` with `APP_NAME`, `MAC_BUNDLE_ID`, `SOURCE_DIR`, `IS_FROZEN`, `DATA_FILENAMES`, `LEGACY_UPDATE_DIR_NAMES`, `RESOURCE_DIR`, `DATA_DIR`, `ASSETS_DIR`, `POSES_DIR`, `ICONS_DIR`, `SOUNDS_DIR`, `PROPS_DIR`, `ANIMATIONS_DIR`, `DECORATIONS_DIR`, `_windows_app_data_dir`, `_legacy_windows_data_dirs`, `_copy_missing_data_files`, `_migrate_legacy_source_data`, and `_seed_default_config`.
- Produces: root `app_paths.py` as an explicit compatibility facade for the same names.

- [x] **Step 1: Write the failing package-boundary test**

Add a test that imports both modules and proves the root facade exposes the exact objects from the package implementation:

```python
def test_root_module_reexports_package_path_api(self):
    import app_paths
    from petpet.app import paths

    exported_names = (
        "APP_NAME", "MAC_BUNDLE_ID", "SOURCE_DIR", "IS_FROZEN",
        "DATA_FILENAMES", "LEGACY_UPDATE_DIR_NAMES", "RESOURCE_DIR",
        "DATA_DIR", "ASSETS_DIR", "POSES_DIR", "ICONS_DIR", "SOUNDS_DIR",
        "PROPS_DIR", "ANIMATIONS_DIR", "DECORATIONS_DIR",
        "_windows_app_data_dir", "_legacy_windows_data_dirs",
        "_copy_missing_data_files", "_migrate_legacy_source_data",
        "_seed_default_config",
    )
    for name in exported_names:
        self.assertIs(getattr(app_paths, name), getattr(paths, name))
```

- [x] **Step 2: Run the test and verify the package does not exist yet**

Run: `python -m pytest tests/test_app_paths.py::AppPathsTests::test_root_module_reexports_package_path_api -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'petpet'`.

- [x] **Step 3: Move the implementation and add the compatibility facade**

Create package marker files containing only module docstrings. Move the current implementation unchanged into `petpet/app/paths.py`, except calculate `SOURCE_DIR` from the repository/application root instead of the new package directory:

```python
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.dirname(PACKAGE_DIR)
```

Replace root `app_paths.py` with explicit imports from `petpet.app.paths`; include the private migration helpers because tests and migration compatibility rely on them.

- [x] **Step 4: Run focused path tests**

Run: `python -m pytest tests/test_app_paths.py -q`

Expected: all tests PASS.

- [x] **Step 5: Run import and source-launch checks**

Run: `python -c "import app_paths; import petpet.app.paths; import pet; print(app_paths.SOURCE_DIR)"`

Expected: exit code 0 and the current worktree root is printed.

### Task 2: Verify the first refactor slice

**Files:**
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/工程结构/项目代码与资源结构重构实施记录.md`
- Modify: `D:/Github Desktop/My-Obsidian/项目/Petpet/Petpet 总档案.md`

**Interfaces:**
- Consumes: Task 1's package boundary.
- Produces: verified compatibility evidence and synchronized maintenance notes.

- [x] **Step 1: Run the full Python suite**

Run: `python -m pytest -q`

Expected: at least the v1.5.0 baseline of 457 tests plus the new package-boundary test pass.

- [x] **Step 2: Run whitespace and worktree checks**

Run: `git diff --check` and `git status --short`

Expected: no whitespace errors; only files belonging to this refactor slice are changed.

- [x] **Step 3: Record the implementation in Obsidian**

Record the new module boundary, compatibility behavior, exact focused/full test counts, and the next slice (`player + dual-pet state migration`). Link the implementation record from `Petpet 总档案.md`.

- [x] **Step 4: Review without publishing**

Inspect the final diff and verify no version, release, tag, remote, or packaged asset was changed.
