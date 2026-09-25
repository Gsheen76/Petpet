# -*- coding: utf-8 -*-
"""属性消耗延长（2026-09-25 用户定稿）：无强化待机 8 小时、满持久强化 16 小时。

速率数学：rate/tick × 0.5 全局系数，tick=2s → 每分钟消耗
rate×0.5×30；100 点耗尽分钟 = 100 / (rate×15)。
0.0139 → 479.6 分钟 ≈ 8.0h；强化满级 awake_decay_multiplier=0.5 → ~16h。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from petpet.app import settings as settings_mod

OLD_TRIO = 0.0556
NEW_TRIO = 0.0139


def idle_minutes(rate, multiplier=1.0):
    return 100.0 / (rate * 0.5 * 30 * multiplier)


class DecayRetuneTests(unittest.TestCase):
    def test_defaults_hit_eight_hours(self):
        for key in ("decay_hunger", "decay_energy", "decay_mood"):
            self.assertEqual(settings_mod.DEFAULT_SETTINGS[key], NEW_TRIO, key)
        normal = idle_minutes(NEW_TRIO)
        self.assertTrue(7.9 * 60 <= normal <= 8.05 * 60, normal)

    def test_max_endurance_hits_sixteen_hours(self):
        upgraded = idle_minutes(NEW_TRIO, multiplier=0.5)
        self.assertTrue(15.8 * 60 <= upgraded <= 16.1 * 60, upgraded)

    def test_migration_replaces_old_default_trio(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "pet_settings.json"
            path.write_text(json.dumps({
                "decay_hunger": OLD_TRIO,
                "decay_energy": OLD_TRIO,
                "decay_mood": OLD_TRIO,
                "sound_enabled": False,  # 用户其它偏好必须保留
            }), encoding="utf-8")
            loaded = settings_mod.load_settings(path)
        for key in ("decay_hunger", "decay_energy", "decay_mood"):
            self.assertEqual(loaded[key], NEW_TRIO, key)
        self.assertFalse(loaded["sound_enabled"])

    def test_migration_respects_custom_rates(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "pet_settings.json"
            path.write_text(json.dumps({"decay_hunger": 0.02}), encoding="utf-8")
            loaded = settings_mod.load_settings(path)
        self.assertEqual(loaded["decay_hunger"], 0.02)


if __name__ == "__main__":
    unittest.main()
