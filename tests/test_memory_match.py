# -*- coding: utf-8 -*-
"""记忆翻牌小游戏（2026-09-26 创新轮）：纯逻辑 + 奖励公式 TDD。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from petpet.minigames.memory import MemoryBoard, memory_reward


class MemoryBoardTests(unittest.TestCase):
    def test_deck_has_pairs_shuffled(self):
        board = MemoryBoard(pairs=8, rng=__import__("random").Random(7))
        self.assertEqual(len(board.deck), 16)
        self.assertEqual(len(set(board.deck)), 8)
        self.assertTrue(all(board.deck.count(k) == 2 for k in board.deck))

    def test_flip_opens_then_match(self):
        board = MemoryBoard(pairs=2, rng=__import__("random").Random(1))
        i, j = (index for index, key in enumerate(board.deck)
                if key == board.deck[0])
        first = board.flip(i)
        self.assertEqual(first, ("open", i))
        second = board.flip(j)
        self.assertEqual(second, ("match", (i, j)))
        self.assertTrue(board.is_matched(i))
        self.assertEqual(board.moves, 1)

    def test_miss_autocloses_on_third_flip(self):
        board = MemoryBoard(pairs=2, rng=__import__("random").Random(1))
        keys = board.deck
        i = 0
        j = next(k for k in range(len(keys)) if keys[k] != keys[i])
        m = next(k for k in range(len(keys))
                 if k not in (i, j) and keys[k] != keys[i])
        board.flip(i)
        self.assertEqual(board.flip(j), ("miss", (i, j)))
        # 第三次翻牌：未配对的两张自动合上
        event = board.flip(m)
        self.assertEqual(event, ("open", m))
        self.assertFalse(board.is_open(i))
        self.assertFalse(board.is_matched(j))
        # 步数=已完成的配对尝试：失误那次已计 1，新一张是新一轮开端
        self.assertEqual(board.moves, 1)

    def test_done_and_reward(self):
        board = MemoryBoard(pairs=2, rng=__import__("random").Random(1))
        for key in set(board.deck):
            i, j = (index for index, k in enumerate(board.deck) if k == key)
            board.flip(i)
            board.flip(j)
        self.assertTrue(board.done)
        self.assertEqual(board.moves, 2)
        self.assertEqual(memory_reward(board), 40)  # 完美 = 每对一步

    def test_reward_floors_and_penalizes(self):
        board = MemoryBoard(pairs=2, rng=__import__("random").Random(1))
        board.moves = 2 + 16  # 多翻 16 步
        self.assertEqual(memory_reward(board), 8)  # 下限
        board.moves = 2 + 4
        self.assertEqual(memory_reward(board), 32)

    def test_flip_matched_or_open_is_noop(self):
        board = MemoryBoard(pairs=2, rng=__import__("random").Random(1))
        board.flip(0)
        self.assertEqual(board.flip(0), ("busy", 0))


if __name__ == "__main__":
    unittest.main()


class MemoryWindowOpenPathTests(unittest.TestCase):
    """真实打开路径（2026-09-26 玩不了回归钉）：hub 走 show_near_pet，
    其内部必调 refresh——未 override 基类 abstract 的窗口当场抛
    NotImplementedError（曾以 excepthook 日志定案）。"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_every_game_window_overrides_refresh(self):
        from petpet.minigames.ui import (
            CoinCatchGameWindow,
            LuckyPawsGameWindow,
            MemoryMatchGameWindow,
        )
        from petpet.progression.ui import CozyProgressWindow

        for cls in (CoinCatchGameWindow, LuckyPawsGameWindow,
                    MemoryMatchGameWindow):
            self.assertIsNot(
                cls.refresh, CozyProgressWindow.refresh, cls.__name__
            )

    def test_memory_window_show_near_pet_does_not_raise(self):
        from types import SimpleNamespace

        from petpet.minigames.ui import MemoryMatchGameWindow

        pet = SimpleNamespace(
            state={"pets": {}},
            interface_screen_rect=lambda: __import__("PyQt5.QtCore", fromlist=["QRect"]).QRect(0, 0, 1920, 1080),
        )
        window = MemoryMatchGameWindow(pet, lambda s: None)
        self.addCleanup(window.close)
        window.show_near_pet()  # 修复前此处 NotImplementedError

        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class CoinLabelOnEntryTests(unittest.TestCase):
    """入场币值显示（2026-09-26 用户报：点进去 Pet币变 0，玩一局才好）。"""

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_shows_real_balance_on_open(self):
        from types import SimpleNamespace

        from petpet.minigames.ui import MemoryMatchGameWindow
        from petpet.progression import core as progression

        state = {"pets": {}}
        progression.ensure_progression(state)
        progression.add_coins(state, 123)
        pet = SimpleNamespace(state=state)
        window = MemoryMatchGameWindow(pet, lambda s: None)
        self.addCleanup(window.close)
        window.refresh()
        self.assertEqual(window.coin_label._balance, 123)
