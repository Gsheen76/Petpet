# -*- coding: utf-8 -*-
"""陪伴度系统测试（2026-09-30 用户定稿）：per-pet interactions_total
mirror 修复 + companionship_score 加权计算。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class InteractionsTotalMirrorTests(unittest.TestCase):
    def test_basic_interactions_mirror_total(self):
        from petpet.progression.core import (
            ensure_progression, record_action, pet_interaction_records,
        )
        state = ensure_progression({"active_pet_id": "lunch_meat"})
        state["pets"] = {"lunch_meat": {"pet_records": {}}}
        record_action(state, "pettings", 3)
        record_action(state, "feedings", 2)
        rec = pet_interaction_records(state, "lunch_meat")
        self.assertEqual(rec["interactions_total"], 5,
                         "四项基础互动的合计应 mirror 到宠物记录")

    def test_non_basic_action_not_counted(self):
        from petpet.progression.core import (
            ensure_progression, record_action, pet_interaction_records,
        )
        state = ensure_progression({"active_pet_id": "lunch_meat"})
        state["pets"] = {"lunch_meat": {"pet_records": {}}}
        record_action(state, "pick_ups", 5)
        rec = pet_interaction_records(state, "lunch_meat")
        self.assertEqual(rec["interactions_total"], 0,
                         "抓起不是基础互动，不计入总互动")


class CompanionshipScoreTests(unittest.TestCase):
    def test_score_weights(self):
        from petpet.progression.core import companionship_score
        r = {"feedings": 2, "play_sessions": 1, "pettings": 3,
             "chats_opened": 5, "pick_ups": 2}
        # 2×5 + 1×5 + 3×2 + 5×3 + 2×1 + 10(基础) = 48
        self.assertEqual(companionship_score(r), 48)

    def test_zero_interactions(self):
        from petpet.progression.core import companionship_score
        self.assertEqual(companionship_score({}), 0)

    def test_level_labels(self):
        from petpet.progression.core import companionship_level
        self.assertEqual(companionship_level(0), "")
        self.assertEqual(companionship_level(15), "匆匆一瞥")
        self.assertEqual(companionship_level(30), "惦记着 TA")
        self.assertEqual(companionship_level(60), "温暖用心")
        self.assertEqual(companionship_level(90), "无微不至的陪伴")


if __name__ == "__main__":
    unittest.main()
