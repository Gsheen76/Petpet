# -*- coding: utf-8 -*-
"""每日任务系统（2026-09-23 创新甲）：三条日常 + 全勤奖励，跨日重置。

进度钩子挂在 record_action 单漏斗——喂食/摸摸/玩耍/聊天/送礼全走
record_action，任务进度自动累积，无需各调用点改造。
"""
import copy
import sys
import unittest
import unittest.mock
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import petpet.app.pet_window as pet_window_mod
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


class MidnightRolloverTests(unittest.TestCase):
    """零点自动刷新（2026-09-25 用户定稿）：到点立即重置任务/签到块。

    红点缓存（菜单 _attention_flags）同步失效、开着的每日窗重建、
    重排下一个零点——不再依赖「打开窗口才刷新」。
    """

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import copy

        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_ms_until_next_midnight(self):
        from petpet.progression.daily import ms_until_next_midnight

        almost = ms_until_next_midnight(datetime(2026, 9, 25, 23, 59, 0))
        self.assertTrue(59_000 <= almost <= 60_500, almost)
        fresh = ms_until_next_midnight(datetime(2026, 9, 25, 0, 0, 5))
        self.assertTrue(24 * 3600_000 - 10_000 <= fresh <= 24 * 3600_000, fresh)

    def test_rollover_resets_blocks_flags_and_reschedules(self):
        from types import SimpleNamespace

        window = self._window()
        yesterday = datetime.now() - timedelta(days=1)
        window.state["daily_quests"] = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "quests": [],
            "bonus_claimed": True,
        }
        window.state["check_in"] = {
            "last_date": yesterday.strftime("%Y-%m-%d"),
            "streak": 3,
            "history": [yesterday.strftime("%Y-%m-%d")],
        }
        menu = SimpleNamespace(
            _attention_flags=object(),
            update=lambda: None,
        )
        window._prewarmed_bubble_menus = {"primary": menu}
        scheduled = []
        window._schedule_midnight_rollover = lambda: scheduled.append(1)
        saved = []
        window._rollover_save = lambda s: saved.append(1)

        window._midnight_rollover()

        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(window.state["daily_quests"]["date"], today)
        self.assertFalse(window.state["daily_quests"]["bonus_claimed"])
        self.assertEqual(window.state["check_in"]["last_date"],
                         yesterday.strftime("%Y-%m-%d"))  # 昨天签过不自动补签
        from petpet.progression.daily import check_in_status
        self.assertTrue(check_in_status(window.state)["available"])
        self.assertIsNone(menu._attention_flags)
        self.assertEqual(scheduled, [1])
        self.assertEqual(saved, [1])


class RewardJuiceTests(unittest.TestCase):
    """奖励回路果汁感（2026-09-25 创新轮）：领取有反应、任务完成即报信。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import copy

        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_quest_completion_notifies_once(self):
        window = self._window()
        ensure_daily_quests(window.state)
        quest = window.state["daily_quests"]["quests"][0]
        quest["progress"] = quest["target"]
        said = []
        window.say = lambda text, ms=2200: said.append(text)

        window._notify_daily_ready()
        window._notify_daily_ready()  # 第二个 tick 不得重播

        self.assertEqual(len(said), 1)
        self.assertIn(quest["label"], said[0])
        self.assertTrue(quest["notified"])  # 持久化标记（重启不重播）
        quest["claimed"] = True
        window._notify_daily_ready()
        self.assertEqual(len(said), 1)

    def test_check_in_claim_reacts_with_milestone(self):
        from types import SimpleNamespace

        from petpet.progression.ui import DailyWindow

        state = fresh_state()
        # 预置 6 天连续 → 今天签完 streak=7（周里程碑）
        state["check_in"] = {
            "last_date": "2026-09-24", "streak": 6,
            "history": ["2026-09-24"],
        }
        dw = DailyWindow.__new__(DailyWindow)
        dw.pet = SimpleNamespace(state=state)
        dw.save_callback = lambda s: None
        dw.refresh = lambda: None
        lines = []
        dw._pet_react = lambda text: lines.append(text)

        dw._do_check_in(now=datetime(2026, 9, 25, 10, 0, 0))

        self.assertTrue(any("签到" in x and "80" in x for x in lines), lines)  # Day7 大奖 80
        self.assertTrue(any("连续签到 7 天" in x for x in lines), lines)

    def test_quest_claim_reacts(self):
        from types import SimpleNamespace

        from petpet.progression.ui import DailyWindow

        state = fresh_state()
        ensure_daily_quests(state, now=datetime(2026, 9, 25, 9, 0, 0))
        quest = state["daily_quests"]["quests"][0]
        quest["progress"] = quest["target"]
        dw = DailyWindow.__new__(DailyWindow)
        dw.pet = SimpleNamespace(state=state)
        dw.save_callback = lambda s: None
        dw.refresh = lambda: None
        lines = []
        dw._pet_react = lambda text: lines.append(text)

        dw._claim_daily_quest(0, now=datetime(2026, 9, 25, 10, 0, 0))

        self.assertEqual(len(lines), 1)
        self.assertIn(str(quest["reward"]), lines[0])


class ClaimAllReadyTests(unittest.TestCase):
    """一键领取（2026-09-25 续新轮）：可领任务≥1 时聚合领全部+全勤。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _shell(self, state):
        from types import SimpleNamespace

        from petpet.progression.ui import DailyWindow

        dw = DailyWindow.__new__(DailyWindow)
        dw.pet = SimpleNamespace(state=state)
        dw.save_callback = lambda s: None
        dw.refresh = lambda: None
        lines = []
        dw._pet_react = lambda text: lines.append(text)
        return dw, lines

    def test_claim_all_collects_completed_and_bonus(self):
        day = datetime(2026, 9, 25, 12, 0, 0)
        state = fresh_state()
        ensure_daily_quests(state, now=day)
        rewards = []
        for quest in state["daily_quests"]["quests"]:
            quest["progress"] = quest["target"]
            rewards.append(quest["reward"])
        dw, lines = self._shell(state)

        granted = dw._claim_all_ready(now=day)

        self.assertEqual(granted, sum(rewards) + DAILY_QUEST_BONUS)  # 3 任务 + 全勤
        self.assertTrue(all(q["claimed"] for q in state["daily_quests"]["quests"]))
        self.assertTrue(state["daily_quests"]["bonus_claimed"])
        self.assertEqual(len(lines), 1, lines)  # 聚合一次反应
        self.assertIn(str(granted), lines[0])

    def test_claim_all_nothing_ready_returns_zero(self):
        day = datetime(2026, 9, 25, 12, 0, 0)
        state = fresh_state()
        ensure_daily_quests(state, now=day)
        dw, lines = self._shell(state)
        self.assertEqual(dw._claim_all_ready(now=day), 0)
        self.assertEqual(lines, [])


class PetSkitTests(unittest.TestCase):
    """小剧场彩蛋（2026-09-25 续新轮）：久置闲时随机表演。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import copy

        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_skit_fires_once_per_cooldown(self):
        import random as _random

        window = self._window()
        window.state["sleeping"] = False
        window._last_skit_at = 0.0  # 冷却早已过
        said = []
        window.say = lambda t, ms=2200: said.append(t)
        window.trigger_animation = lambda name: said.append(f"[{name}]")

        with unittest.mock.patch.object(
            pet_window_mod.random, "random", lambda: 0.0
        ):
            window._maybe_skit()
            window._maybe_skit()  # 冷却内不得再演

        self.assertEqual(len(said), 2)  # 一个动画标记 + 一句台词
        self.assertTrue(said[0].startswith("["))
        self.assertNotEqual(window._last_skit_at, 0.0)

    def test_skit_sleeping_skipped(self):
        window = self._window()
        window.state["sleeping"] = True
        window._last_skit_at = 0.0
        said = []
        window.say = lambda t, ms=2200: said.append(t)
        with unittest.mock.patch.object(
            pet_window_mod.random, "random", lambda: 0.0
        ):
            window._maybe_skit()
        self.assertEqual(said, [])


class ActivityLogTests(unittest.TestCase):
    """每日活动流水（2026-09-25 c 线）：按天记互动量，喂周报图表。"""

    def test_note_and_series(self):
        from petpet.progression.daily import (
            daily_activity_series,
            note_daily_activity,
        )

        state = fresh_state()
        note_daily_activity(state, 2, now=datetime(2026, 9, 24, 10, 0, 0))
        note_daily_activity(state, 3, now=datetime(2026, 9, 25, 11, 0, 0))
        note_daily_activity(state, 1, now=datetime(2026, 9, 25, 12, 0, 0))

        series = daily_activity_series(
            state, days=3, now=datetime(2026, 9, 25, 13, 0, 0)
        )
        self.assertEqual(len(series), 3)
        self.assertEqual(series[-1][1], 4)  # 今天累计
        self.assertEqual(series[-2][1], 2)  # 昨天
        self.assertEqual(series[-3][1], 0)  # 前天（无记录为 0）

    def test_record_action_feeds_activity(self):
        state = fresh_state()
        progression.record_action(
            state, "pettings", now=datetime(2026, 9, 25, 14, 0, 0).timestamp()
        )
        log = state.get("activity_log")
        self.assertEqual(log, {datetime.now().strftime("%Y-%m-%d"): 1})

    def test_trim_old_days(self):
        from petpet.progression.daily import note_daily_activity

        state = fresh_state()
        for offset in range(35):
            day = datetime(2026, 9, 25, 10, 0, 0) - timedelta(days=offset)
            note_daily_activity(state, 1, now=day)
        self.assertLessEqual(len(state["activity_log"]), 28)


class MoodWeightedSkitTests(unittest.TestCase):
    """小剧场心情加权：低心情偏求陪伴（play/eat），高心情偏 happy。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import copy

        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_low_mood_picks_companion_skit(self):
        window = self._window()
        window.state["sleeping"] = False
        window.state["mood"] = 25
        window._last_skit_at = 0.0
        picked = []
        window.trigger_animation = lambda name: picked.append(name)
        window.say = lambda t, ms=2200: None

        with unittest.mock.patch.object(
            pet_window_mod.random, "random", lambda: 0.0
        ):
            window._maybe_skit()

        self.assertEqual(len(picked), 1)
        self.assertIn(picked[0], ("play", "eat"))
