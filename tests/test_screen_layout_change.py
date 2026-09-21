# -*- coding: utf-8 -*-
"""屏幕热变更自愈（2026-09-21）：拔插显示器/改缩放后窗口必须钳回有效屏。

用户在大屏看到面板「被截一半」的根因：运行中进程持有旧屏幕模型，落位
按已消失/已变更的屏算出界外坐标（本会话内实况：双屏150% → 单屏125%）。
修复 = 监听 screenAdded/screenRemoved/primaryScreenChanged，把所有可见
顶层窗口钳进最近有效屏；宠物本体即使隐藏也钳，防拔屏后重现悬空。
"""
import copy
import unittest

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QApplication, QWidget

import pet
from petpet.ui.common import (
    clamp_rect_into_screen,
    clamp_window_into_nearest_screen,
    pick_screen_rect_for,
)


class ClampRectIntoScreenTests(unittest.TestCase):
    """纯函数：矩形平移钳进屏（不缩放；超大窗对齐左上角）。"""

    def test_rect_moved_fully_inside_preserving_size(self):
        # 右屏消失后按旧双屏布局落在 x=3400 的面板，钳回单屏右缘内
        self.assertEqual(
            clamp_rect_into_screen(QRect(3400, 200, 850, 960), QRect(0, 0, 2560, 1380)),
            QRect(2560 - 850, 200, 850, 960),
        )

    def test_negative_origin_screen_keeps_negative_coords(self):
        # 主屏左接副屏（副屏原点为负）时钳位以屏矩形为准，不吃虚拟桌面 (0,0)；
        # 原窗口骑跨边界（0..700，副屏右缘为 0）→ 右对齐收进副屏
        self.assertEqual(
            clamp_rect_into_screen(QRect(0, 100, 700, 500), QRect(-1707, 0, 1707, 960)),
            QRect(-700, 100, 700, 500),
        )

    def test_oversized_window_aligns_top_left(self):
        # 窗口某轴比屏大（如装修全景 2138 宽遇上 1920 屏）：该轴对齐屏左缘
        # 不压缩；另一轴仍正常钳位（底部越界 1268>1080 → 上收到 312）
        self.assertEqual(
            clamp_rect_into_screen(QRect(500, 500, 2138, 768), QRect(0, 0, 1920, 1080)),
            QRect(0, 312, 2138, 768),
        )

    def test_already_inside_rect_untouched(self):
        rect = QRect(100, 100, 800, 600)
        self.assertEqual(
            clamp_rect_into_screen(rect, QRect(0, 0, 2560, 1380)), rect
        )

    def test_bottom_overflow_clamped_to_bottom_edge(self):
        self.assertEqual(
            clamp_rect_into_screen(QRect(100, 1200, 800, 400), QRect(0, 0, 2560, 1380)),
            QRect(100, 1380 - 400, 800, 400),
        )


class PickScreenRectTests(unittest.TestCase):
    """重叠面积最大者优先；全无重叠时中心距最近者优先。"""

    def test_max_overlap_wins(self):
        rect = QRect(2400, 200, 800, 600)  # 大半在右屏
        left = QRect(0, 0, 2560, 1440)
        right = QRect(2560, 0, 2560, 1440)
        self.assertIs(pick_screen_rect_for(rect, [left, right]), right)

    def test_zero_overlap_picks_nearest_center(self):
        rect = QRect(5000, 200, 800, 600)  # 悬在右屏右侧更远处
        left = QRect(0, 0, 2560, 1440)
        right = QRect(2560, 0, 2560, 1440)
        self.assertIs(pick_screen_rect_for(rect, [left, right]), right)

    def test_empty_list_returns_none(self):
        self.assertIsNone(pick_screen_rect_for(QRect(0, 0, 100, 100), []))


class ClampWindowIntoNearestScreenTests(unittest.TestCase):
    """窗口对象包装：移动真窗口，返回是否移动。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stray_window_moved_and_reported(self):
        stray = QWidget()
        self.addCleanup(stray.close)
        stray.setGeometry(3400, 200, 850, 960)
        moved = clamp_window_into_nearest_screen(
            stray, [QRect(0, 0, 2560, 1380)]
        )
        self.assertTrue(moved)
        self.assertTrue(QRect(0, 0, 2560, 1380).contains(stray.geometry()))

    def test_inside_window_not_moved(self):
        inside = QWidget()
        self.addCleanup(inside.close)
        inside.setGeometry(300, 300, 400, 300)
        before = QRect(inside.geometry())
        moved = clamp_window_into_nearest_screen(
            inside, [QRect(0, 0, 2560, 1380)]
        )
        self.assertFalse(moved)
        self.assertEqual(QRect(inside.geometry()), before)


class _FakeScreen:
    def __init__(self, rect):
        self._rect = rect

    def availableGeometry(self):
        return self._rect


class ScreenLayoutSelfHealTests(unittest.TestCase):
    """PetWindow 接线：屏幕变更信号到达时可见顶层窗全部钳回屏内。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"x": 100, "y": 100, "tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def _patch_screens(self, fake_screens, widgets):
        QApplication.screens = staticmethod(lambda: fake_screens)
        QApplication.topLevelWidgets = staticmethod(lambda: widgets)

    def _restore_screens(self):
        del QApplication.screens
        del QApplication.topLevelWidgets

    def test_offscreen_stray_panel_moved_into_single_screen(self):
        window = self._window()
        stray = QWidget()
        self.addCleanup(stray.close)
        stray.setGeometry(3400, 200, 850, 960)  # 按旧双屏布局的坐标
        stray.show()

        self._patch_screens([_FakeScreen(QRect(0, 0, 2560, 1380))], [stray])
        try:
            moved = window._handle_screen_layout_change()
        finally:
            self._restore_screens()

        self.assertGreaterEqual(moved, 1)
        # offscreen 窗管给可见窗口的 move() 叠加不定帧偏移（实测 +2~+9px；
        # 生产面板为 FramelessWindowHint 无此偏移），右/下缘按 16px 容差
        g = stray.geometry()
        self.assertGreaterEqual(g.x(), 0)
        self.assertGreaterEqual(g.y(), 0)
        self.assertLessEqual(g.x(), 2560 - 850 + 16)
        self.assertLessEqual(g.y(), 1380 - 960 + 16)

    def test_inside_window_not_touched(self):
        window = self._window()
        inside = QWidget()
        self.addCleanup(inside.close)
        inside.setGeometry(300, 300, 400, 300)
        inside.show()
        before = QRect(inside.geometry())

        self._patch_screens([_FakeScreen(QRect(0, 0, 2560, 1380))], [inside])
        try:
            moved = window._handle_screen_layout_change()
        finally:
            self._restore_screens()

        self.assertEqual(moved, 0)
        self.assertEqual(QRect(inside.geometry()), before)

    def test_prewarmed_parked_windows_not_rescued(self):
        # 预热交互面停靠在 (-10000,-10000)（系统钳显 -8000），绝不能被
        # 屏幕变更自愈拽进可见屏——救援半径外的窗口不碰
        window = self._window()
        parked = QWidget()
        self.addCleanup(parked.close)
        parked.move(-10000, -10000)
        parked.resize(472, 174)
        parked.show()
        before = QRect(parked.geometry())

        self._patch_screens(
            [_FakeScreen(QRect(0, 0, 2560, 1380))],
            [parked],
        )
        try:
            moved = window._handle_screen_layout_change()
        finally:
            self._restore_screens()

        self.assertEqual(moved, 0)
        self.assertEqual(QRect(parked.geometry()).topLeft(), before.topLeft())

    def test_hidden_pet_itself_still_clamped(self):
        # 宠物隐藏期间拔屏，恢复屏幕后本体也要钳回（隐藏状态下无可见窗口）
        window = self._window()
        window.move(3400, 200)
        window.hide()

        self._patch_screens(
            [_FakeScreen(QRect(0, 0, 2560, 1380))],
            [],  # 无其它可见窗口
        )
        try:
            window._handle_screen_layout_change()
        finally:
            self._restore_screens()

        self.assertTrue(
            QRect(0, 0, 2560, 1380).intersects(window.geometry())
        )


if __name__ == "__main__":
    unittest.main()
