# -*- coding: utf-8 -*-
"""2026-09-25 三件套测试：悬浮残留清理 / QMenu 收养 / 后台诊断日志。"""
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QApplication, QMenu


class BubbleMenuHoverLeaveTests(unittest.TestCase):
    """鼠标移出菜单后悬浮高亮必须清除（用户反馈：残留）。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _menu(self):
        import pet
        from petpet.progression import core as progression

        host = SimpleNamespace(
            state=progression.ensure_progression({}),
            pet_name="烟花",
            interface_anchor_rect=lambda: QRect(900, 700, 190, 220),
            interface_screen_rect=lambda: QRect(0, 0, 1920, 1080),
            set_pet_name=Mock(),
        )
        return pet.BubbleMenu(host, show_window=False)

    def test_leave_event_resets_hover(self):
        menu = self._menu()
        self.addCleanup(menu._close)
        menu._hover = 2
        menu.leaveEvent(None)
        self.assertEqual(menu._hover, -1)


class AdoptedWindowTests(unittest.TestCase):
    """无父 QMenu 收养：保活到销毁、关闭即出表。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_adopt_release_and_fresh_menu_pins(self):
        import gc

        from petpet.ui.common import _ADOPTED_WINDOWS, adopt_window

        menu = QMenu()
        adopt_window(menu)
        self.assertIn(menu, _ADOPTED_WINDOWS)
        self.assertTrue(menu.testAttribute(Qt.WA_DeleteOnClose))
        menu.deleteLater()  # WA_DeleteOnClose 的销毁路径（offscreen 直证）
        from PyQt5.QtCore import QEvent
        QApplication.instance().sendPostedEvents(None, QEvent.DeferredDelete)
        QApplication.processEvents()
        gc.collect()
        QApplication.processEvents()
        self.assertNotIn(menu, _ADOPTED_WINDOWS)

        # _fresh_menu 的收养用文本钉住（TrayApp 构造过重不起真实例）
        import pet
        import inspect
        source = inspect.getsource(pet.TrayApp._fresh_menu)
        self.assertIn("adopt_window(m)", source)

    def test_adopt_window_non_widget_noop(self):
        from petpet.ui.common import _ADOPTED_WINDOWS, adopt_window

        before = len(_ADOPTED_WINDOWS)
        adopt_window("not a widget")
        self.assertEqual(len(_ADOPTED_WINDOWS), before)


class DiagnosticsTests(unittest.TestCase):
    """后台诊断：JSONL 事件、轮转、excepthook 记录且不杀。"""

    def test_log_event_writes_jsonl(self):
        import tempfile

        from petpet.app import diagnostics

        with tempfile.TemporaryDirectory() as raw:
            with unittest.mock.patch.object(
                diagnostics, "_log_path",
                lambda: os.path.join(raw, "diag.log"),
            ):
                diagnostics.log_event("unit_test", foo=1, bar="值")
                path = os.path.join(raw, "diag.log")
                self.assertTrue(os.path.exists(path))
                entry = json.loads(
                    open(path, encoding="utf-8").readlines()[-1]
                )
        self.assertEqual(entry["event"], "unit_test")
        self.assertEqual(entry["foo"], 1)
        self.assertIn("ts", entry)

    def test_rotation_at_cap(self):
        import tempfile

        from petpet.app import diagnostics

        with tempfile.TemporaryDirectory() as raw:
            path = os.path.join(raw, "diag.log")
            with open(path, "wb") as fh:
                fh.write(b"x" * (diagnostics.LOG_MAX_BYTES + 10))
            with unittest.mock.patch.object(
                diagnostics, "_log_path", lambda: path
            ):
                diagnostics.log_event("after_cap")
            self.assertFalse(os.path.exists(path + ".1") is False)
            self.assertTrue(os.path.getsize(path) < 1024)

    def test_excepthook_records_and_survives(self):
        import tempfile

        from petpet.app import diagnostics

        with tempfile.TemporaryDirectory() as raw:
            path = os.path.join(raw, "diag.log")
            with unittest.mock.patch.object(
                diagnostics, "_log_path", lambda: path
            ):
                diagnostics.install_excepthooks()
                try:
                    raise ValueError("boom")
                except ValueError:
                    diagnostics.sys.excepthook(
                        *sys.exc_info()
                    )
                lines = open(path, encoding="utf-8").readlines()
        entry = json.loads(lines[-1])
        self.assertEqual(entry["event"], "unhandled_exception")
        self.assertIn("ValueError: boom", entry["exc"])
        self.assertIn("Traceback", entry["stack"])


import unittest.mock  # noqa: E402  (供上方 patch 使用)

if __name__ == "__main__":
    unittest.main()
