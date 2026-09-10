"""游戏中自动隐藏：判定纯函数、设置开关与主窗口隐藏/恢复行为。

win32 采集不可离线测（测试注入伪造快照走 `is_game_present`/
`_on_game_guard_tick` 注入路径）；真实采集在 Windows 平台手工验证。
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from petpet.app import game_guard

MONITOR = (0, 0, 1920, 1080)


def _info(hwnd=99, rect=(0, 0, 1920, 1080), monitor=MONITOR,
          cls="UnrealWindow", exe=r"C:\Games\SomeGame\bin\game.exe"):
    return {"hwnd": hwnd, "rect": rect, "monitor": monitor,
            "class": cls, "exe": exe, "pid": 4242}


class PredicatesTests(unittest.TestCase):
    def test_none_and_junk_info_are_not_game(self):
        self.assertFalse(game_guard.is_game_present(None))
        self.assertFalse(game_guard.is_game_present({}))
        self.assertFalse(game_guard.is_game_present("junk"))

    def test_platform_path_alone_triggers_even_windowed(self):
        # 唯一信号=游戏路径：窗口化 WeGame 游戏也触发。
        self.assertTrue(game_guard.is_game_present(
            _info(rect=(100, 100, 1280, 800),
                  exe=r"D:\WeGameApps\英雄联盟\Game\League of Legends.exe"),
        ))
        self.assertTrue(game_guard.is_game_present(
            _info(rect=(100, 100, 1280, 800),
                  exe=r"D:\Steam\steamapps\common\Game\game.exe"),
        ))

    def test_direct_install_cn_games_trigger(self):
        for exe in (
            r"C:\Program Files\Genshin Impact\GenshinImpact.exe",
            r"D:\Games\Star Rail\Game\StarRail.exe",
            r"E:\miHoYo\崩坏3\BH3.exe",
        ):
            self.assertTrue(game_guard.is_game_present(_info(exe=exe)))

    def test_fullscreen_alone_does_not_trigger(self):
        """用户定稿（2026-09-08）：全屏不再独立判定——IDE/浏览器 F11/
        播放器/PPT 等全屏非游戏应用不隐藏小狗。"""
        for exe in (
            r"D:\DirectInstall\SomeMMO\client.exe",           # 直装未知游戏
            r"D:\Program Files\ZCode\ZCode.exe",               # Electron IDE 全屏
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"D:\Players\PotPlayer\PotPlayerMini64.exe",
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C\Windows\System32\mstsc.exe",
        ):
            self.assertFalse(
                game_guard.is_game_present(_info(exe=exe)),
                f"{exe} 即使全屏也不应触发隐藏",
            )

    def test_blocklist_beats_platform_path(self):
        # 双保险：黑名单进程即使路径撞上关键词也不算（浏览器装在
        # 含 games 的目录）。
        self.assertFalse(game_guard.is_game_present(
            _info(exe=r"D:\Games\Tools\chrome.exe"),
        ))

    def test_exclusions(self):
        # 自身窗口 / 自身进程 / 桌面壁纸层 / explorer 都不算游戏。
        self.assertFalse(game_guard.is_game_present(
            _info(hwnd=7), own_hwnds=(7,),
        ))
        self.assertFalse(game_guard.is_game_present(
            _info(exe=r"D:\Agent_project\Petpet\wegame\pet.py",
                  rect=(0, 0, 1920, 1080)),
            own_exe_markers=(r"D:\Agent_project\Petpet",),
        ))
        self.assertFalse(game_guard.is_game_present(
            _info(cls="Progman", exe=r"C:\Windows\explorer.exe"),
        ))
        self.assertFalse(game_guard.is_game_present(
            _info(cls="Chrome_WidgetWin_1",
                  exe=r"C:\Windows\explorer.exe"),
        ))

    def test_coverage_math(self):
        self.assertAlmostEqual(
            game_guard.fullscreen_coverage((0, 0, 1920, 1080), MONITOR), 1.0,
        )
        self.assertAlmostEqual(
            game_guard.fullscreen_coverage((0, 0, 960, 1080), MONITOR), 0.5,
        )
        self.assertEqual(
            game_guard.fullscreen_coverage(None, MONITOR), 0.0,
        )


class SettingsTests(unittest.TestCase):
    def test_default_enabled_and_roundtrip(self):
        from petpet.app.settings import DEFAULT_SETTINGS, load_settings, save_settings
        import tempfile, json, os as _os

        self.assertIs(DEFAULT_SETTINGS["hide_in_game"], True)
        with tempfile.TemporaryDirectory() as tmp:
            path = _os.path.join(tmp, "pet_settings.json")
            save_settings({"hide_in_game": False}, path)
            loaded = load_settings(path)
            self.assertIs(loaded["hide_in_game"], False)
            # 旧存档无该键 → 默认开。
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"sound_enabled": True}, f)
            self.assertIs(load_settings(path)["hide_in_game"], True)


class PetWindowGameGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        import copy

        import pet

        state = copy.deepcopy(pet.DEFAULT_STATE)
        state.update({"tutorial_completed": True})
        window = pet.PetWindow(state)
        self.addCleanup(window.close)
        return window

    def test_tick_hides_and_restores(self):
        window = self._window()
        window.show()
        self.assertTrue(window.isVisible())

        snapshots = iter([
            _info(hwnd=int(window.winId()) + 1),   # 游戏 → 隐藏
            None,                                   # 游戏退出 → 恢复
        ])
        original = game_guard.collect_foreground_info

        def fake_collect():
            try:
                return next(snapshots)
            except StopIteration:
                return None

        game_guard.collect_foreground_info = fake_collect
        try:
            window._on_game_guard_tick()
            self.assertFalse(window.isVisible())
            self.assertTrue(window._game_auto_hidden)
            # 存在守卫不得把自动隐藏拉回来。
            self.assertFalse(window._maintain_desktop_presence())
            window._on_game_guard_tick()
            self.assertTrue(window.isVisible())
            self.assertFalse(window._game_auto_hidden)
        finally:
            game_guard.collect_foreground_info = original

    def test_manual_hidden_not_restored_by_game_end(self):
        window = self._window()
        window.set_user_visible(False)
        self.assertFalse(window.isVisible())

        original = game_guard.collect_foreground_info
        game_guard.collect_foreground_info = lambda: None
        try:
            window._on_game_guard_tick()  # 无游戏 → 不该把手动藏的拉回来
            self.assertFalse(window.isVisible())
        finally:
            game_guard.collect_foreground_info = original

    def test_setting_toggles_timer(self):
        window = self._window()
        self.assertTrue(window._game_guard_timer.isActive())
        window.settings["hide_in_game"] = False
        window._sync_game_guard_timer()
        self.assertFalse(window._game_guard_timer.isActive())
        window.settings["hide_in_game"] = True
        window.apply_runtime_settings({})
        self.assertTrue(window._game_guard_timer.isActive())

    def test_disabling_restores_auto_hidden_pet(self):
        window = self._window()
        window.show()
        window._game_auto_hidden = True
        window.hide()
        window.settings["hide_in_game"] = False
        window._sync_game_guard_timer()
        self.assertFalse(window._game_guard_timer.isActive())
        self.assertTrue(window.isVisible())
