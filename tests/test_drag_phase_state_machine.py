# -*- coding: utf-8 -*-
"""四态拖拽状态机行为测试（2026-10-13 用户定稿流程）：

1. 抓起（_promote_to_grab）→ 先播完第一阶段 sway，不直接进 hover
2. sway 播完 → 自动回 hover 循环
3. sway 播放中移动不打断、停止回调不误触发（「播放完再进入后面的循环」）
4. 移动后停住 → 重播 sway → 播完回 hover
5. sway 完成定时器可重启（替换未到期触发——根治双触发拦腰切断）
6. falling 态渲染名 = sway 变体（far-past 末帧显示的前置）
"""
from __future__ import annotations

import copy
import unittest

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QApplication

import pet


class DragPhaseStateMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({
            "x": 100, "y": 100, "tutorial_completed": True,
            "active_pet_id": "lunch_meat",
            "owned_outfits": ["strawberry_suit"],
            "equipped_outfit": "strawberry_suit",
        })
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def _grab(self, window):
        window._grab_pending = True
        window._grab_press_pos = QPoint(100, 100)
        window._promote_to_grab()

    def test_grab_plays_phase_one_before_hover_loop(self):
        window = self._window()
        self._grab(window)
        self.assertTrue(window.dragging)
        self.assertEqual(window._drag_anim_state, "sway")
        self.assertEqual(
            window._current_animation_name(), "drag_sway_strawberry")
        self.assertTrue(window._drag_sway_timer.isActive())

    def test_sway_finish_returns_to_hover_loop(self):
        window = self._window()
        self._grab(window)
        window._on_sway_finished()
        self.assertEqual(window._drag_anim_state, "held")
        self.assertEqual(
            window._current_animation_name(), "drag_hover_strawberry")

    def test_movement_does_not_cut_phase_one(self):
        window = self._window()
        self._grab(window)
        # 播放中移动：状态保持 sway（用户定稿「播放完再进入后面的循环」）
        self.assertEqual(window._drag_anim_state, "sway")
        # 停止回调在 sway 中必须 no-op（只认 moving）
        window._on_drag_mouse_stopped()
        self.assertEqual(window._drag_anim_state, "sway")
        self.assertTrue(window._drag_sway_timer.isActive())

    def test_stop_after_move_keeps_hover_loop(self):
        """2026-10-15 用户定稿：停住不再重播 sway，保持 hover 循环。"""
        window = self._window()
        self._grab(window)
        window._on_sway_finished()  # 第一阶段播完 → hover
        self.assertEqual(window._drag_anim_state, "held")
        window._drag_anim_state = "moving"  # 模拟移动后停住
        window._on_drag_mouse_stopped()
        # 停住 → 直接回 held（hover 循环继续），不重播 sway
        self.assertEqual(window._drag_anim_state, "held")
        self.assertEqual(
            window._current_animation_name(), "drag_hover_strawberry")

    def test_sway_finish_timer_is_restarted_not_stacked(self):
        """再次进入 sway 时同一 QTimer 成员被 restart（start 语义=取消
        未到期触发）。老实现用不可取消的 QTimer.singleShot，快速
        「动→停」双触发时旧 shot 先到期把新 sway 拦腰切断——正是
        「定住之后感觉没播放完整」的根因。"""
        window = self._window()
        self._grab(window)
        timer = window._drag_sway_timer
        self.assertTrue(timer.isActive())
        window._drag_anim_state = "moving"
        window._on_drag_mouse_stopped()
        self.assertIs(window._drag_sway_timer, timer)
        self.assertTrue(timer.isActive(), "重启后必须仍在计时")
        window._on_sway_finished()
        self.assertEqual(window._drag_anim_state, "held")

    def test_falling_state_renders_sway_variant(self):
        window = self._window()
        self._grab(window)
        window._drag_anim_state = "falling"
        self.assertEqual(
            window._current_animation_name(), "drag_sway_strawberry")


if __name__ == "__main__":
    unittest.main()
