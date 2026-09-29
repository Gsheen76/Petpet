"""User settings defaults and JSON persistence."""

from __future__ import annotations

import json
import os

from petpet.app.paths import DATA_DIR


SETTINGS_PATH = os.path.join(DATA_DIR, "pet_settings.json")

DEFAULT_SETTINGS = {
    "chat_width": 640,
    "chat_height": 820,
    "chat_font_size": 24,
    "ui_font_size": 24,
    "always_on_top": True,
    "auto_check_updates": True,
    "hide_in_game": True,
    "remind_drink_min": 60,
    "remind_rest_min": 90,
    "remind_stand_min": 45,
    "sound_enabled": True,
    # 三属性清醒消耗（2026-09-30 用户定稿：无强化待机 12 小时、持久活力
    # 满级 24 小时——实际速率 = 此值 × 0.5 全局系数 × 强化减伤，三值
    # 统一 0.0092593：0.0046296/2s = 0.13889/分 = 100 点约 720 分钟；
    # 历史 0.0556（2h/4h）与 0.0139（8h/16h）由 load_settings 迁移覆盖）。
    "decay_hunger": 0.0092593,
    "decay_energy": 0.0092593,
    "decay_mood": 0.0092593,
    "decay_hunger_sleeping": 0.08,
    "decay_energy_sleeping_gain": 4,
    "needy_speak_chance": 0.13,
    "chatter_frequency_boost": 1.2,
    "ask_weight_normal": 0.5,
    "ask_weight_needy": 0.5,
    "nudge_idle_min": 1800,
    "nudge_gap_min": 10800,
}


def load_settings(path=SETTINGS_PATH):
    """Load user settings while preserving the existing migration rules."""
    try:
        with open(path, "r", encoding="utf-8") as stream:
            loaded = json.load(stream)
        settings = {**DEFAULT_SETTINGS, **loaded}
        settings.pop("chat_bubble_max", None)
        # 消耗延长迁移（2026-09-30 更新）：历史默认（0.0556=2h/4h、
        # 0.0139=8h/16h）未被用户改过时一律升到新默认 0.0092593
        # （12h/24h）；自定义值尊重保留
        _decay_trio = ("decay_hunger", "decay_energy", "decay_mood")
        if all(
            settings.get(key) in (0.0556, 0.0139) for key in _decay_trio
        ):
            for key in _decay_trio:
                settings[key] = DEFAULT_SETTINGS[key]
        if not (20 <= settings.get("ui_font_size", 24) <= 40):
            settings["ui_font_size"] = DEFAULT_SETTINGS["ui_font_size"]
        if not (12 <= settings.get("chat_font_size", 20) <= 32):
            settings["chat_font_size"] = DEFAULT_SETTINGS["chat_font_size"]
        return settings
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(settings, path=SETTINGS_PATH):
    """Persist user settings, retaining the launcher's tolerant behavior."""
    try:
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, ensure_ascii=False, indent=2)
    except Exception:
        pass
