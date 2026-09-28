# -*- coding: utf-8 -*-
"""四角锁定特效根除（2026-09-28 用户反馈）：点击过的 FeedbackButton
抓素颜帧把 Windows 焦点框抓进缓存，hover 永久带四角折角。修复后
点击过的键与未点击键的素颜帧逐像素一致。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication


class FocusFrameSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _buttons(self):
        from petpet.progression.ui import FeedbackButton

        clicked = FeedbackButton("测试")
        fresh = FeedbackButton("测试")
        for b in (clicked, fresh):
            b.resize(120, 48)
            b.show()
        self.addCleanup(clicked.close)
        self.addCleanup(fresh.close)
        return clicked, fresh

    def test_clicked_button_skin_has_no_focus_frame(self):
        clicked, fresh = self._buttons()
        clicked.setFocus()
        clicked.setDown(True)
        clicked.releaseMouse()  # no-op safeguard
        clicked.setDown(False)  # 模拟一次点击（持有焦点）
        self.assertTrue(clicked.hasFocus())
        clicked._capture_skin()
        fresh._capture_skin()
        a = clicked._skin_cache.toImage()
        b = fresh._skin_cache.toImage()
        self.assertEqual(a.size(), b.size())
        self.assertTrue(
            a == b, "点击过的键素颜帧不得带焦点框（四角锁定特效根除）"
        )


if __name__ == "__main__":
    unittest.main()
