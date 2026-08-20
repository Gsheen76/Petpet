import json
from pathlib import Path

import pet


ROOT = Path(__file__).resolve().parents[1]


def test_root_reexports_package_settings_api():
    from petpet.app import settings as app_settings
    from petpet.ui import settings as ui_settings

    assert pet.DEFAULT_SETTINGS is app_settings.DEFAULT_SETTINGS
    assert pet.SETTINGS_PATH == app_settings.SETTINGS_PATH
    assert pet.load_settings is app_settings.load_settings
    assert pet.save_settings is app_settings.save_settings
    assert pet.SettingsWindow.HEALTH_PRESETS is ui_settings.HEALTH_PRESETS
    assert (
        pet.SettingsWindow.PERSONALITY_PRESETS
        is ui_settings.PERSONALITY_PRESETS
    )


def test_load_settings_keeps_legacy_cleanup_and_font_validation(tmp_path):
    from petpet.app.settings import DEFAULT_SETTINGS, load_settings

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "chat_width": 720,
        "chat_bubble_max": 999,
        "chat_font_size": 99,
        "ui_font_size": 1,
    }), encoding="utf-8")

    loaded = load_settings(path)

    assert loaded["chat_width"] == 720
    assert "chat_bubble_max" not in loaded
    assert loaded["chat_font_size"] == DEFAULT_SETTINGS["chat_font_size"]
    assert loaded["ui_font_size"] == DEFAULT_SETTINGS["ui_font_size"]


def test_save_settings_accepts_an_explicit_path(tmp_path):
    from petpet.app.settings import save_settings

    path = tmp_path / "settings.json"
    save_settings({"sound_enabled": False}, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "sound_enabled": False,
    }


def test_settings_window_is_owned_by_package_module():
    from petpet.ui.settings import SettingsWindow

    assert pet.SettingsWindow is SettingsWindow
    root_source = (ROOT / "pet.py").read_text(encoding="utf-8")
    package_source = (
        ROOT / "petpet" / "ui" / "settings.py"
    ).read_text(encoding="utf-8")
    assert "class SettingsWindow" not in root_source
    assert "class SettingsWindow" in package_source
