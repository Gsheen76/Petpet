# -*- coding: utf-8 -*-
"""每日任务系统（2026-09-23 创新甲）：三条日常 + 全勤奖励，跨日重置。

进度钩子挂在 record_action 单漏斗——喂食/摸摸/玩耍/聊天/送礼全走
record_action，任务进度自动累积，无需各调用点改造。
"""
import copy
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from petpet.progression import core as progression
from petpet.progression.core import (
    DAILY_QUEST_BONUS,
    DAILY_QUEST_POOL,
    claim_daily_bonus,
    claim_daily_quest,
    ensure_daily_quests,
)


def fresh_state():
    state = {"pets": {}}
    progression.ensure_progression(state)
    return state


class DailyQuestCoreTests(unittest.TestCase):
    def test_ensure_creates_three_distinct_quests(self):
        state = fresh_state()
        ensure_daily_quests(state, now=datetime(2026, 9, 23, 10, 0, 0))
        block = state["daily_quests"]
        self.assertEqual(block["date"], "2026-09-23")
        keys = [q["key"] for q in block["quests"]]
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(set(keys)), 3)
        self.assertTrue(set(keys) <= {q[0] for q in DAILY_QUEST_POOL})
        self.assertFalse(block["bonus_claimed"])

    def test_same_day_ensure_keeps_progress(self):
        state = fresh_state()
        now = datetime(2026, 9, 23, 10, 0, 0)
        ensure_daily_quests(state, now=now)
        state["daily_quests"]["quests"][0]["progress"] = 2
        state["daily_quests"]["quests"][0]["claimed"] = True
        ensure_daily_quests(state, now=now)
        self.assertEqual(state["daily_quests"]["quests"][0]["progress"], 2)
        self.assertTrue(state["daily_quests"]["quests"][0]["claimed"])

    def test_next_day_resets(self):
        state = fresh_state()
        ensure_daily_quests(state, now=datetime(2026, 9, 23, 10, 0, 0))
        state["daily_quests"]["quests"][0]["progress"] = 2
        ensure_daily_quests(state, now=datetime(2026, 9, 24, 0, 5, 0))
        block = state["daily_quests"]
        self.assertEqual(block["date"], "2026-09-24")
        self.assertTrue(all(q["progress"] == 0 and not q["claimed"] for q in block["quests"]))
        self.assertFalse(block["bonus_claimed"])

    def test_record_action_advances_matching_quest(self):
        state = fresh_state()
        now = datetime(2026, 9, 23, 10, 0, 0)
        ensure_daily_quests(state, now=now)
        block = state["daily_quests"]
        target = next(q for q in block["quests"] if q["key"] == "pettings")
        target["target"] = 2  # 缩短目标便于断言
        ts = now.timestamp()  # record_action 的 now 是浮点纪元
        for _ in range(2):
            progression.record_action(state, "pettings", now=ts)
        self.assertEqual(target["progress"], 2)

    def test_claim_flow_grants_coins_once(self):
        state = fresh_state()
        now = datetime(2026, 9, 23, 10, 0, 0)
        ensure_daily_quests(state, now=now)
        quest = state["daily_quests"]["quests"][0]
        quest["progress"] = quest["target"] - 1
        self.assertEqual(claim_daily_quest(state, 0, now=now), 0)  # 未完成
        quest["progress"] = quest["target"]
        before = progression.shared_pet_coins(state) \
            if hasattr(progression, "shared_pet_coins") else state["pet_coins"]
        granted = claim_daily_quest(state, 0, now=now)
        self.assertEqual(granted, quest["reward"])
        self.assertTrue(quest["claimed"])
        self.assertEqual(claim_daily_quest(state, 0, now=now), 0)  # 已领

    def test_bonus_requires_all_claimed_and_grants_once(self):
        state = fresh_state()
        now = datetime(2026, 9, 23, 10, 0, 0)
        ensure_daily_quests(state, now=now)
        for quest in state["daily_quests"]["quests"]:
            quest["progress"] = quest["target"]
        self.assertEqual(claim_daily_bonus(state, now=now), 0)  # 尚有未领
        for i in range(3):
            claim_daily_quest(state, i, now=now)
        self.assertEqual(claim_daily_bonus(state, now=now), DAILY_QUEST_BONUS)
        self.assertTrue(state["daily_quests"]["bonus_claimed"])
        self.assertEqual(claim_daily_bonus(state, now=now), 0)


if __name__ == "__main__":
    unittest.main()
