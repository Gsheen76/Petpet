"""B 组三项（2026-09-12）：备份还原、开机自启动、聊天停止/重新生成。"""

import os
import unittest
import zipfile
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from petpet.app import backup


def write_data_files(root, names):
    for name in names:
        with open(os.path.join(root, name), "w") as fh:
            fh.write(f"content-{name}")


class RestoreBackupTests(unittest.TestCase):
    def _make_zip(self, tmp, names):
        path = os.path.join(tmp, "bundle.zip")
        with zipfile.ZipFile(path, "w") as bundle:
            for name in names:
                bundle.writestr(name, f"content-{name}")
        return path

    def test_restore_roundtrip_overwrites_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            write_data_files(tmp, ["pet_state.json"])
            # 模拟“当前新内容”，再用备份覆盖回旧内容
            with open(os.path.join(tmp, "pet_state.json"), "w") as fh:
                fh.write("NEW")
            zpath = self._make_zip(tmp, [
                "pet_state.json", "memory.json", "memory-cat.json",
            ])
            restored = backup.restore_backup_zip(zpath, data_dir=tmp)
            self.assertEqual(restored, [
                "pet_state.json", "memory.json", "memory-cat.json"])
            with open(os.path.join(tmp, "pet_state.json")) as fh:
                self.assertEqual(fh.read(), "content-pet_state.json")

    def test_unknown_entries_are_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            zpath = self._make_zip(tmp, ["pet_state.json", "evil.exe"])
            with self.assertRaises(ValueError):
                backup.restore_backup_zip(zpath, data_dir=tmp)

    def test_memory_glob_names_are_accepted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            zpath = self._make_zip(tmp, ["memory-ice_cream.json"])
            self.assertEqual(
                backup.inspect_backup_zip(zpath), ["memory-ice_cream.json"])

    def test_traversal_entry_rejected_before_any_write(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            # fnmatch 的 * 能跨分隔符：memory-../evil.json 命中
            # memory*.json 模式，必须在写入前被路径校验拦下。
            zpath = self._make_zip(tmp, [
                "pet_state.json", "memory-../evil.json",
            ])
            with self.assertRaises(ValueError):
                backup.restore_backup_zip(zpath, data_dir=tmp)
            self.assertFalse(os.path.exists(
                os.path.join(tmp, "memory-../evil.json")))

    def test_autostart_launcher_points_at_real_pet_py(self):
        import re

        from petpet.app import autostart

        if not autostart.is_supported():
            self.skipTest("Windows only")
        command = autostart._launcher_path()
        match = re.search(r'"([^"]+pet\.py)"', command)
        self.assertIsNotNone(match, command)
        self.assertTrue(os.path.isfile(match.group(1)), command)


class AutostartTests(unittest.TestCase):
    def test_roundtrip_enable_disable_registry(self):
        from petpet.app import autostart

        if not autostart.is_supported():
            self.skipTest("Windows only")
        self.assertTrue(autostart.set_enabled(True))
        try:
            self.assertTrue(autostart.is_enabled())
        finally:
            self.assertTrue(autostart.set_enabled(False))
        self.assertFalse(autostart.is_enabled())


class ChatStopRegenerateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, history):
        from types import SimpleNamespace

        from petpet.ui.chat import ChatWindow

        window = ChatWindow.__new__(ChatWindow)
        window.busy = False
        window._abort_requested = False
        window.pet_id = "lunch_meat"
        window.mem = {"history": history}
        window.pet = SimpleNamespace(pet_name="烟花", state={}, say=mock.Mock())
        return window

    def test_send_or_stop_requests_abort_while_busy(self):
        window = self._window([])
        window.busy = True
        window._send_or_stop()
        self.assertTrue(window._abort_requested)

    def test_send_or_stop_routes_to_send_when_idle(self):
        from petpet.ui.chat import ChatWindow

        window = self._window([])
        with mock.patch.object(ChatWindow, "send") as send:
            window._send_or_stop()
        send.assert_called_once()

    def test_regenerate_pops_trailing_pair_and_restarts_reply(self):
        from petpet.ui.chat import ChatWindow

        window = self._window([
            {"role": "user", "content": "第一句"},
            {"role": "assistant", "content": "旧回复"},
        ])
        with mock.patch.object(ChatWindow, "_begin_reply") as begin, \
                mock.patch("petpet.ui.chat.ai.save_memory"), \
                mock.patch(
                    "petpet.ui.chat.ai.load_memory",
                    return_value=window.mem):
            window._regenerate()
        begin.assert_called_once_with("第一句", None, "第一句")

    def test_regenerate_noop_without_assistant_tail(self):
        from petpet.ui.chat import ChatWindow

        window = self._window([{"role": "user", "content": "hi"}])
        with mock.patch.object(ChatWindow, "_begin_reply") as begin:
            window._regenerate()
        begin.assert_not_called()

    def test_ai_thread_abort_before_any_token_emits_stopped_marker(self):
        window = self._window([])

        def fake_stream(*args, **kwargs):
            yield ("token", "收到")
            yield ("token", "一半")

        bridge = mock.Mock()
        window._bridge_provider = lambda: bridge
        window._abort_requested = True  # 首个 chunk 前就置位
        with mock.patch("petpet.ui.chat.ai.chat_stream", fake_stream):
            window._ai_thread("你好")
        bridge.done.emit.assert_called_once_with("（已停止）")

    def test_ai_thread_abort_midway_keeps_partial_text(self):
        window = self._window([])

        class OneTokenThenBlock:
            def __iter__(self):
                yield ("token", "收到一半")
                # 第二个 chunk 到来前用户按了停止
                window._abort_requested = True
                yield ("token", "后半")

        bridge = mock.Mock()
        window._bridge_provider = lambda: bridge
        window._abort_requested = False
        with mock.patch("petpet.ui.chat.ai.chat_stream",
                        lambda *a, **k: OneTokenThenBlock()):
            window._ai_thread("你好")
        bridge.done.emit.assert_called_once_with("收到一半")


if __name__ == "__main__":
    unittest.main()
