# -*- coding: utf-8 -*-
"""应用级点击音过滤器守卫（2026-09-28 三轮用户定稿：所有按键都要
响，包括分栏页签——checkable 不响的旧豁免废除）。

- 过滤器命中：QAbstractButton（含 checkable）/QTabBar/手势光标
  自绘 widget 的键内左键松开 → play_click 恰好一次
- 键外松开不响；非按键 widget 不响
- play_click 25ms 节流：同一毫秒双层命中只播一次
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QWidget


def _release(widget, x, y):
    ev = QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(x, y), QPointF(x, y),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    return QApplication.sendEvent(widget, ev)


class ClickSoundFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_filter_hits_buttons_tabs_and_cursor_widgets(self):
        import petpet.app.sounds as sounds

        filt = sounds.install_click_sound_filter(self.app)

        btn = QPushButton("购买")
        tab_btn = QPushButton("家居")
        tab_btn.setCheckable(True)  # 分栏键：checkable 也必须响
        art = QWidget()
        art.setCursor(Qt.PointingHandCursor)  # 自绘贴图键形态
        label = QLabel("只是标签")
        for w in (btn, tab_btn, art, label):
            w.resize(120, 40)
        hits = []

        def _spy():
            hits.append(1)

        with patch.object(sounds, "play_click", side_effect=_spy):
            self.assertTrue(_release(btn, 60, 20))
            self.assertTrue(_release(tab_btn, 60, 20))
            self.assertTrue(_release(art, 60, 20))
            self.assertEqual(len(hits), 3, "按钮/分栏/手势键都该命中")
            _release(label, 60, 20)
            self.assertEqual(len(hits), 3, "非按键 widget 不得响")
            # 键外松开（拖出取消）不响
            _release(btn, 500, 500)
            self.assertEqual(len(hits), 3, "键外松开不得响")
            # 游戏画布豁免（评审轮：金币雨/猜猜看整幅手势光标曾误响）
            canvas = QWidget()
            canvas.setCursor(Qt.PointingHandCursor)
            canvas.setProperty("petpetNoClickSound", True)
            canvas.resize(300, 300)
            _release(canvas, 150, 150)
            self.assertEqual(len(hits), 3, "豁免画布不得响")
        self.assertFalse(filt is None)

    def test_play_click_throttles_duplicate_hits(self):
        """40ms 节流：同一毫秒双层命中只播一次（>音效时长=永不
        restart 的结构性保证，见 sounds.py docstring）。"""
        import petpet.app.sounds as sounds

        class _Fake:
            def __init__(self):
                self.plays = 0

            def setVolume(self, *_):
                pass

            def play(self):
                self.plays += 1

        fake = _Fake()
        old_effect, old_ts = sounds._EFFECT, sounds._LAST_PLAY_TS
        sounds._EFFECT = fake
        sounds._LAST_PLAY_TS = 0.0
        try:
            sounds.play_click()
            sounds.play_click()  # 同一毫秒级的第二层命中——节流掉
            self.assertEqual(
                fake.plays, 1, "40ms 节流内只允许播一次（防双响）"
            )
        finally:
            sounds._EFFECT = old_effect
            sounds._LAST_PLAY_TS = old_ts


if __name__ == "__main__":
    unittest.main()
