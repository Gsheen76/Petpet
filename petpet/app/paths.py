"""Shared resource and writable-data paths for Petpet."""

from __future__ import annotations

import os
import shutil
import sys


APP_NAME = "Petpet"
MAC_BUNDLE_ID = "com.gsheen.petpet"
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.dirname(PACKAGE_DIR)
IS_FROZEN = bool(getattr(sys, "frozen", False))
DATA_FILENAMES = (
    "config.json",
    "memory.json",
    "pet_settings.json",
    "pet_state.json",
)
LEGACY_UPDATE_DIR_NAMES = {"update", "updates", "updata"}


def _windows_app_data_dir(environment=None) -> str:
    """Return a stable per-user directory that is independent of the EXE."""
    environment = os.environ if environment is None else environment
    base_dir = (
        environment.get("LOCALAPPDATA")
        or environment.get("APPDATA")
        or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    )
    return os.path.join(base_dir, APP_NAME)


def _legacy_windows_data_dirs(executable=None):
    """Find old portable data, including data above an updates/vX folder."""
    executable = os.path.abspath(executable or sys.executable)
    executable_dir = os.path.dirname(executable)
    parent_dir = os.path.dirname(executable_dir)
    candidates = []

    if os.path.basename(parent_dir).lower() in LEGACY_UPDATE_DIR_NAMES:
        # Old releases could be started from <install>/updates/vX/Petpet.exe.
        # Prefer the real install directory over the newly-created empty data
        # beside that downloaded executable.
        candidates.append(os.path.dirname(parent_dir))
    elif os.path.basename(executable_dir).lower() in LEGACY_UPDATE_DIR_NAMES:
        candidates.append(parent_dir)

    candidates.append(executable_dir)
    unique = []
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized not in {
                os.path.normcase(os.path.abspath(item)) for item in unique}:
            unique.append(candidate)
    return unique


def _copy_missing_data_files(source_dirs, target_dir):
    """Copy legacy user data without ever overwriting newer stable data."""
    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for filename in DATA_FILENAMES:
        target_path = os.path.join(target_dir, filename)
        if os.path.exists(target_path):
            continue
        for source_dir in source_dirs:
            source_path = os.path.join(source_dir, filename)
            if (
                os.path.isfile(source_path)
                and os.path.abspath(source_path) != os.path.abspath(target_path)
            ):
                try:
                    shutil.copy2(source_path, target_path)
                    copied.append(filename)
                except OSError:
                    pass
                break
    return copied


if IS_FROZEN:
    RESOURCE_DIR = sys._MEIPASS
else:
    RESOURCE_DIR = SOURCE_DIR

if sys.platform == "darwin":
    DATA_DIR = os.path.join(
        os.path.expanduser("~/Library/Application Support"), APP_NAME
    )
elif sys.platform.startswith("win"):
    # Source and packaged Windows builds share one stable profile. This
    # prevents switching between `python pet.py` and Petpet.exe from creating
    # a second empty save inside the repository.
    DATA_DIR = _windows_app_data_dir()
else:
    DATA_DIR = os.path.dirname(sys.executable) if IS_FROZEN else os.path.join(
        SOURCE_DIR, "data"
    )

ASSET_ROOT_DIR = os.path.join(RESOURCE_DIR, "assets")
ASSETS_DIR = os.path.join(ASSET_ROOT_DIR, "runtime")
SOURCE_ASSETS_DIR = os.path.join(ASSET_ROOT_DIR, "source")
PETS_DIR = os.path.join(ASSETS_DIR, "pets")
PETS_MANIFEST_PATH = os.path.join(PETS_DIR, "manifest.json")
DESKTOP_PET_DIR = os.path.join(ASSETS_DIR, "pets", "desktop")
HOME_PET_DIR = os.path.join(ASSETS_DIR, "pets", "home")
POSES_DIR = os.path.join(DESKTOP_PET_DIR, "poses")
HOME_POSES_DIR = os.path.join(HOME_PET_DIR, "poses")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
PROPS_DIR = os.path.join(ASSETS_DIR, "props")
ANIMATIONS_DIR = os.path.join(DESKTOP_PET_DIR, "animations")
OUTFITS_DIR = os.path.join(DESKTOP_PET_DIR, "outfits")
DECORATIONS_DIR = os.path.join(ASSETS_DIR, "decorations")
SCENES_DIR = os.path.join(ASSETS_DIR, "scenes")
HOME_SCENES_DIR = os.path.join(SCENES_DIR, "home")
FURNITURE_DIR = os.path.join(ASSETS_DIR, "furniture")
HOME_FURNITURE_DIR = os.path.join(FURNITURE_DIR, "home")
KNOWLEDGE_DIR = os.path.join(ASSETS_DIR, "knowledge")

os.makedirs(DATA_DIR, exist_ok=True)


def _migrate_legacy_source_data() -> None:
    """Move pre-v1.2 development data from the project root into data/."""
    if IS_FROZEN:
        if sys.platform.startswith("win"):
            _copy_missing_data_files(
                _legacy_windows_data_dirs(), DATA_DIR
            )
        return
    if sys.platform.startswith("win"):
        _copy_missing_data_files(
            [SOURCE_DIR, os.path.join(SOURCE_DIR, "data")], DATA_DIR
        )
        return
    for filename in DATA_FILENAMES:
        legacy_path = os.path.join(SOURCE_DIR, filename)
        current_path = os.path.join(DATA_DIR, filename)
        if os.path.isfile(legacy_path) and not os.path.exists(current_path):
            try:
                shutil.move(legacy_path, current_path)
            except OSError:
                pass


def _seed_default_config() -> None:
    config_path = os.path.join(DATA_DIR, "config.json")
    example_path = os.path.join(RESOURCE_DIR, "config.json.example")
    if os.path.exists(config_path) or not os.path.exists(example_path):
        return
    try:
        shutil.copyfile(example_path, config_path)
    except OSError:
        pass


_migrate_legacy_source_data()
_seed_default_config()
