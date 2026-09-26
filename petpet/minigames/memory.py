# -*- coding: utf-8 -*-
"""记忆翻牌纯逻辑（2026-09-26）：牌组/翻牌状态机/奖励公式，UI 无关。"""
from __future__ import annotations

import random

MEMORY_PAIRS = 8
REWARD_BASE = 40
REWARD_STEP_COST = 2
REWARD_FLOOR = 8


def memory_reward(board):
    """按步数效率计币：每对牌一步为完美（40），每多一步 -2，下限 8。"""
    extra = max(0, board.moves - board.pairs)
    return max(REWARD_FLOOR, REWARD_BASE - REWARD_STEP_COST * extra)


class MemoryBoard:
    """翻牌状态机：同键两张配对；两张未配对时翻第三张自动合上前者。

    moves 计「一次配对尝试」（第二次翻开时 +1），配对成功或失误都算。
    """

    def __init__(self, pairs=MEMORY_PAIRS, rng=None):
        self.pairs = int(pairs)
        keys = [f"icon_{n}" for n in range(self.pairs)]
        self.deck = keys * 2
        (rng or random).shuffle(self.deck)
        self.opened = []      # 当前翻开未判定的下标（0~2 张）
        self.matched = set()  # 已配对下标
        self.moves = 0

    def is_open(self, index):
        return index in self.opened

    def is_matched(self, index):
        return index in self.matched

    @property
    def done(self):
        return len(self.matched) == len(self.deck)

    def flip(self, index):
        """翻一张牌，返回事件：busy/open/match/miss。"""
        if index in self.matched or index in self.opened:
            return ("busy", index)
        # 规则：同时最多两张开着——第三张翻牌先合上未配对的两张
        if len(self.opened) == 2 and not self._resolve_pending():
            return ("busy", index)
        self.opened.append(index)
        if len(self.opened) == 2:
            self.moves += 1
            i, j = self.opened
            if self.deck[i] == self.deck[j]:
                self.matched.update((i, j))
                self.opened = []
                return ("match", (i, j))
            return ("miss", (i, j))
        return ("open", index)

    def _resolve_pending(self):
        """合上当前未配对的两张（第三张翻牌前的自动收拾）。"""
        if len(self.opened) != 2:
            return True
        i, j = self.opened
        if self.deck[i] == self.deck[j]:
            return False  # 正在动画等待中的配对不收拾
        self.opened = []
        return True
