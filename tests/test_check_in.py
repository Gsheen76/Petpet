# -*- coding: utf-8 -*-
"""每日签到系统（2026-09-24 用户点名）：连续签到 + 7 天阶梯奖励循环。

规则：本地日期判重；昨天已签 → streak+1，断签（或首签）→ streak=1；
奖励 = CHECK_IN_REWARD_CYCLE[(streak-1) % 7]，第 7 天 60 币大奖后循环。
"""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from petpet.progression import core as progression
from petpet.progression.core import (
    CHECK_IN_REWARD_CYCLE,
    check_in_status,
    do_check_in,
    ensure_check_in,
)


def fresh_state():
    state = {"pets": {}}
    progression.ensure_progression(state)
    return state


class CheckInCoreTests(unittest.TestCase):
    def test_first_check_in_grants_day1_reward(self):
        state = fresh_state()
        day = datetime(2026, 9, 24, 9, 0, 0)
        self.assertEqual(
            do_check_in(state, now=day), CHECK_IN_REWARD_CYCLE[0]
        )
        self.assertEqual(state["check_in"]["streak"], 1)
        self.assertEqual(state["check_in"]["last_date"], "2026-09-24")

    def test_same_day_check_in_is_idempotent(self):
        state = fresh_state()
        day = datetime(2026, 9, 24, 9, 0, 0)
        do_check_in(state, now=day)
        self.assertEqual(do_check_in(state, now=day.replace(hour=23)), 0)
        self.assertEqual(state["check_in"]["streak"], 1)

    def test_consecutive_day_increments_streak_and_reward(self):
        state = fresh_state()
        day = datetime(2026, 9, 24, 9, 0, 0)
        do_check_in(state, now=day)
        granted = do_check_in(state, now=day + timedelta(days=1))
        self.assertEqual(granted, CHECK_IN_REWARD_CYCLE[1])
        self.assertEqual(state["check_in"]["streak"], 2)

    def test_gap_resets_streak_to_one(self):
        state = fresh_state()
        day = datetime(2026, 9, 24, 9, 0, 0)
        do_check_in(state, now=day)
        do_check_in(state, now=day + timedelta(days=1))
        granted = do_check_in(state, now=day + timedelta(days=3))  # 断了一天
        self.assertEqual(granted, CHECK_IN_REWARD_CYCLE[0])
        self.assertEqual(state["check_in"]["streak"], 1)

    def test_seventh_day_bonus_then_cycle_restarts(self):
        state = fresh_state()
        day = datetime(2026, 9, 18, 9, 0, 0)
        for i in range(7):
            granted = do_check_in(state, now=day + timedelta(days=i))
            self.assertEqual(granted, CHECK_IN_REWARD_CYCLE[i])
        self.assertEqual(state["check_in"]["streak"], 7)
        granted8 = do_check_in(state, now=day + timedelta(days=7))
        self.assertEqual(granted8, CHECK_IN_REWARD_CYCLE[0])
        self.assertEqual(state["check_in"]["streak"], 8)

    def test_coins_credited(self):
        state = fresh_state()
        before = state["pet_coins"]
        do_check_in(state, now=datetime(2026, 9, 24, 9, 0, 0))
        self.assertEqual(state["pet_coins"], before + CHECK_IN_REWARD_CYCLE[0])

    def test_status_reports_availability_and_streak(self):
        state = fresh_state()
        ensure_check_in(state, now=datetime(2026, 9, 24, 9, 0, 0))
        status = check_in_status(state, now=datetime(2026, 9, 24, 12, 0, 0))
        self.assertTrue(status["available"])
        self.assertEqual(status["streak"], 0)
        self.assertEqual(status["today_reward"], CHECK_IN_REWARD_CYCLE[0])
        do_check_in(state, now=datetime(2026, 9, 24, 12, 0, 0))
        status = check_in_status(state, now=datetime(2026, 9, 24, 20, 0, 0))
        self.assertFalse(status["available"])
        self.assertEqual(status["streak"], 1)

    def test_ensure_creates_block_and_tolerates_legacy_state(self):
        state = fresh_state()
        ensure_check_in(state)
        self.assertEqual(state["check_in"], {"last_date": None, "streak": 0})
        state["check_in"] = {"last_date": "2026-09-24", "streak": 3}
        ensure_check_in(state, now=datetime(2026, 9, 24, 10, 0, 0))
        self.assertEqual(state["check_in"]["streak"], 3)  # 已有合法块不动


if __name__ == "__main__":
    unittest.main()
