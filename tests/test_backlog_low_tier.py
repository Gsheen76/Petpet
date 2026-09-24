# -*- coding: utf-8 -*-
"""低危遗留三项清偿（2026-09-23，HANDOFF §9 低⑪⑫⑭）：
⑪ 聊天搜索：发送新消息即退出过滤（修流式直显→完成又消失的不一致）
⑫ 单击去抖 QTimer：只建一次复用（修每击 new QTimer(self.app) 慢泄漏）
⑭ 备份还原：staging+逐文件原子替换+失败回滚（修中途失败混合态）
"""
import os
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtCore import QEvent, QPointF, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QLineEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class ChatSendExitsSearchFilterTests(unittest.TestCase):
    """低⑪：_begin_reply 清空搜索框并按全量视图续排。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _shell(self):
        from petpet.ui.chat import ChatWindow

        window = ChatWindow.__new__(ChatWindow)
        window.search_input = QLineEdit()
        window.search_input.setText("关键词")
        window.chat_notice = mock.Mock()
        window.mem = {"history": []}
        window.busy = False
        window.input = mock.Mock()
        window._pet_name = lambda: "小狗"
        captured = []
        window._set_log_messages = lambda rows: captured.append(list(rows))
        window._refresh_ai_tool_buttons = lambda: None
        window._ai_thread = lambda *a, **k: None  # 不真启网络线程
        return window, captured

    def test_begin_reply_clears_keyword(self):
        window, captured = self._shell()
        window._begin_reply("你好呀", None, "你好呀")
        self.assertEqual(window.search_input.text(), "")
        # 列表里必须带着新用户行与助手占位（全量视图，非过滤视图）
        roles = [row[0] for row in captured[-1]]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_no_keyword_no_touch(self):
        window, captured = self._shell()
        window.search_input.clear()
        window._begin_reply("你好呀", None, "你好呀")
        self.assertEqual(window.search_input.text(), "")


def _release_event(x=10, y=10):
    return QEvent  # placeholder, real construction below


class SingleClickTimerReuseTests(unittest.TestCase):
    """低⑫：单击去抖定时器常驻复用，连续点击不新增 QTimer。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tray(self):
        import pet

        tray = pet.TrayApp(self.app)
        self.addCleanup(tray.pet.close)
        tray.pet.open_home_scene = lambda: None  # 双击分支不真开家园
        tray.pet.pet_click = lambda: None
        return tray

    @staticmethod
    def _press(button=Qt.LeftButton):
        return _mouse_event(QEvent.MouseButtonPress, button)

    @staticmethod
    def _release(button=Qt.LeftButton):
        return _mouse_event(QEvent.MouseButtonRelease, button)

    def test_repeated_clicks_reuse_one_timer(self):
        tray = self._tray()
        before = len(self.app.findChildren(QTimer))
        timer_first = tray._pending_single_click

        for _ in range(3):
            tray._wrap_press(self._press())
            tray._wrap_release(self._release())
            tray._pending_single_click.stop()  # 不等 320ms 真触发

        self.assertIsInstance(timer_first, QTimer)
        self.assertIs(tray._pending_single_click, timer_first)
        self.assertEqual(len(self.app.findChildren(QTimer)), before)

    def test_double_click_stops_timer_without_recreate(self):
        tray = self._tray()
        timer = tray._pending_single_click
        tray._wrap_press(self._press())
        tray._wrap_release(self._release())  # 首击：start
        self.assertTrue(timer.isActive())
        tray._wrap_press(self._press())
        tray._wrap_release(self._release())  # 双击：stop
        self.assertFalse(timer.isActive())
        self.assertIs(tray._pending_single_click, timer)


def _mouse_event(event_type, button):
    return QMouseEvent_(event_type, QPointF(10, 10), button, button, Qt.NoModifier)


def QMouseEvent_(event_type, pos, button, buttons, modifiers):
    from PyQt5.QtGui import QMouseEvent

    return QMouseEvent(event_type, pos, button, buttons, modifiers)


class BackupRestoreAtomicTests(unittest.TestCase):
    """低⑭：还原失败必须回滚到原状，不留混合态。"""

    def _make_zip(self, tmp, entries):
        path = tmp / "bundle.zip"
        with zipfile.ZipFile(path, "w") as bundle:
            for name, payload in entries.items():
                bundle.writestr(name, payload)
        return path

    def test_failure_mid_swap_rolls_back_all_targets(self):
        import tempfile

        from petpet.app import backup

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            data = tmp / "data"
            data.mkdir()
            # 预置两个现役文件，备份包带两个新版本
            (data / "pet_state.json").write_text("OLD-STATE", encoding="utf-8")
            (data / "pet_settings.json").write_text("OLD-SETTINGS", encoding="utf-8")
            zpath = self._make_zip(tmp, {
                "pet_state.json": "NEW-STATE",
                "pet_settings.json": "NEW-SETTINGS",
            })

            real_replace = os.replace
            calls = {"n": 0}

            def flaky_replace(src, dst):
                calls["n"] += 1
                if calls["n"] == 2:  # 第二个文件替换时失败
                    raise OSError("disk full (simulated)")
                return real_replace(src, dst)

            with mock.patch.object(backup.os, "replace", side_effect=flaky_replace):
                with self.assertRaises(OSError):
                    backup.restore_backup_zip(str(zpath), data_dir=str(data))

            self.assertEqual(
                (data / "pet_state.json").read_text(encoding="utf-8"),
                "OLD-STATE",
            )
            self.assertEqual(
                (data / "pet_settings.json").read_text(encoding="utf-8"),
                "OLD-SETTINGS",
            )

    def test_success_restores_all(self):
        import tempfile

        from petpet.app import backup

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            data = tmp / "data"
            data.mkdir()
            (data / "pet_state.json").write_text("OLD", encoding="utf-8")
            zpath = self._make_zip(tmp, {
                "pet_state.json": "NEW",
                "pet_settings.json": "FRESH",
            })
            names = backup.restore_backup_zip(str(zpath), data_dir=str(data))
            self.assertEqual(sorted(names), ["pet_settings.json", "pet_state.json"])
            self.assertEqual(
                (data / "pet_state.json").read_text(encoding="utf-8"), "NEW"
            )
            self.assertEqual(
                (data / "pet_settings.json").read_text(encoding="utf-8"), "FRESH"
            )


if __name__ == "__main__":
    unittest.main()
