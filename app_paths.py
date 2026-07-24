"""Shared resource and writable-data paths for Petpet."""

from __future__ import annotations

import os
import shutil
import sys


APP_NAME = "Petpet"
MAC_BUNDLE_ID = "com.gsheen.petpet"
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_FROZEN = bool(getattr(sys, "frozen", False))

if IS_FROZEN:
    RESOURCE_DIR = sys._MEIPASS
    if sys.platform == "darwin":
        DATA_DIR = os.path.join(
            os.path.expanduser("~/Library/Application Support"), APP_NAME
        )
    else:
        DATA_DIR = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = SOURCE_DIR
    DATA_DIR = os.path.join(SOURCE_DIR, "data")

ASSETS_DIR = os.path.join(RESOURCE_DIR, "assets")
POSES_DIR = os.path.join(ASSETS_DIR, "poses")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")
ANIMATIONS_DIR = os.path.join(ASSETS_DIR, "animations")

os.makedirs(DATA_DIR, exist_ok=True)


def _migrate_legacy_source_data() -> None:
    """Move pre-v1.2 development data from the project root into data/."""
    if IS_FROZEN:
        return
    for filename in (
        "config.json",
        "memory.json",
        "pet_settings.json",
        "pet_state.json",
    ):
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
