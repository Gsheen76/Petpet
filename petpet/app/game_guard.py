"""游戏中自动隐藏：前台窗口采集（Windows）+ 游戏判定（纯函数）。

采集与判定分离：`is_game_present` 只吃普通 dict，离线测试可直接喂
伪造快照；非 Windows 平台采集恒返回 None，功能自动空转。

判定单信号（2026-09-08 用户定稿"只有启动游戏才隐藏，别的应用不隐藏"）：
前台进程可执行文件路径命中游戏平台/直装游戏目录（steamapps、
Epic、WeGame、Riot、米哈游系、库洛系等）即游戏中；再过一道
非游戏程序黑名单（浏览器/播放器/PPT/远程工具等）双保险。

全屏覆盖不再独立触发——IDE（Electron 全屏）、浏览器 F11、播放器、
PPT 放映都会全屏，按窗口几何判定会误隐藏非游戏应用。
`fullscreen_coverage` 保留为诊断工具函数。

排除：自身窗口/自身进程、桌面壁纸层（Progman/WorkerW）、explorer。
"""

from __future__ import annotations

import ctypes
import os
import sys

# 平台/游戏目录关键词（小写、反斜杠口径匹配）。这是唯一触发信号
# （2026-09-08 用户定稿：只有启动游戏才隐藏，别的应用不隐藏——
# 全屏不再独立判定，否则 IDE/浏览器 F11/播放器等全屏应用会误触发）。
GAME_PLATFORM_MARKERS = (
    "steamapps",
    "epic games\\",
    "wegame",
    "riot games",
    "battle.net",
    "\\games\\",
    "gog galaxy",
    # 常见直装国产/跨平台游戏目录
    "\\genshin impact",
    "yuanshen",
    "starrail",
    "star rail",
    "honkai",
    "zenless",
    "wuthering waves",
    "\\mihoyo",
    "\\cognosphere",
    "\\kurogames",
)
# 匹配前 exe 会转小写，marker 统一小写防大小写漏配（\\miHoYo 教训）。
GAME_PLATFORM_MARKERS = tuple(
    marker.lower() for marker in GAME_PLATFORM_MARKERS
)

# 前台窗口覆盖显示器的面积比例阈值。
FULLSCREEN_COVERAGE = 0.98

# 桌面壁纸层窗口类（全屏矩形但不是游戏）。
DESKTOP_WINDOW_CLASSES = ("progman", "workerw")

# 非游戏程序黑名单（进程名，小写）：这些应用经常主动全屏
# （浏览器 F11、播放器、PPT 放映、PDF、看图、远程桌面、OBS 投屏），
# 但不是游戏——用户定稿"只有启动游戏时才隐藏，别的应用不隐藏"。
NON_GAME_EXES = (
    # 浏览器
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe",
    "vivaldi.exe", "brave.exe", "maxthon.exe", "2345explorer.exe",
    "qqbrowser.exe", "ubrowser.exe", "liebao.exe",
    # 视频/音乐播放器
    "vlc.exe", "potplayermini64.exe", "potplayermini.exe",
    "mpc-hc64.exe", "mpc-hc.exe", "mpc-be64.exe", "wmplayer.exe",
    "qqplayer.exe", "xmp.exe", "kugou.exe", "cloudmusic.exe",
    # 办公/文档/看图
    "powerpnt.exe", "winword.exe", "excel.exe", "onenote.exe",
    "acrord32.exe", "acrobat.exe", "sumatrapdf.exe", "foxitpdfreader.exe",
    "photoshop.exe", "illustrator.exe",
    # 远程/投屏/录屏
    "mstsc.exe", "teamviewer.exe", "anydesk.exe", "todesk.exe",
    "sunloginclient.exe", "obs64.exe", "obs32.exe",
    # 阅读器/其他常见全屏应用
    "kindle.exe", "ibooks.exe", "windowsdefender.exe",
)

_SHELL_EXE = "explorer.exe"


def _rect_area(rect) -> float:
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def fullscreen_coverage(window_rect, monitor_rect) -> float:
    """窗口与显示器矩形的交集面积 / 显示器面积（0..1）。"""
    if not window_rect or not monitor_rect:
        return 0.0
    monitor_area = _rect_area(monitor_rect)
    if monitor_area <= 0:
        return 0.0
    intersect = (
        max(window_rect[0], monitor_rect[0]),
        max(window_rect[1], monitor_rect[1]),
        min(window_rect[2], monitor_rect[2]),
        min(window_rect[3], monitor_rect[3]),
    )
    return _rect_area(intersect) / monitor_area


def is_game_present(info, own_hwnds=(), own_exe_markers=()) -> bool:
    """判定一条前台窗口快照是否处于"游戏中"。

    ``info``: ``collect_foreground_info`` 的返回（或测试伪造）：
    ``{"hwnd", "rect", "monitor", "class", "exe"}``。
    """
    if not isinstance(info, dict):
        return False
    if info.get("hwnd") in tuple(own_hwnds):
        return False
    window_class = str(info.get("class") or "").lower()
    if window_class in DESKTOP_WINDOW_CLASSES:
        return False
    exe = str(info.get("exe") or "").lower().replace("/", "\\")
    if exe.endswith(_SHELL_EXE):
        return False
    for marker in own_exe_markers:
        if marker and str(marker).lower().replace("/", "\\") in exe:
            return False
    # 非游戏程序黑名单（浏览器/播放器/PPT/远程等）：双保险，路径
    # 信号命中它们也不算（如浏览器装在含 games 的目录）。
    exe_name = exe.rsplit("\\", 1)[-1]
    if exe_name in NON_GAME_EXES:
        return False
    return any(marker in exe for marker in GAME_PLATFORM_MARKERS)


def own_exe_markers() -> tuple:
    """自身进程的路径特征：前台是本程序（任意窗口）时不算游戏。"""
    markers = [sys.executable]
    try:
        from petpet.app.paths import SOURCE_DIR

        markers.append(SOURCE_DIR)
    except Exception:
        pass
    return tuple(markers)


# ---- Windows 采集（仅 win32；其余平台恒 None） ----

if sys.platform.startswith("win"):
    import ctypes.wintypes as wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _MONITOR_DEFAULTTONEAREST = 0x00000002
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class _RECT(ctypes.Structure):
        _fields_ = (("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long))

    class _MONITORINFO(ctypes.Structure):
        _fields_ = (("cbSize", wintypes.DWORD),
                    ("rcMonitor", _RECT), ("rcWork", _RECT),
                    ("dwStyle", wintypes.DWORD))


def collect_foreground_info() -> dict | None:
    """当前前台窗口快照；失败/非 Windows 返回 None。"""
    if not sys.platform.startswith("win"):
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = _RECT()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        monitor = _user32.MonitorFromWindow(
            hwnd, _MONITOR_DEFAULTTONEAREST,
        )
        info_ex = _MONITORINFO()
        info_ex.cbSize = ctypes.sizeof(_MONITORINFO)
        monitor_rect = (0, 0, 0, 0)
        if monitor and _user32.GetMonitorInfoW(
                monitor, ctypes.byref(info_ex)):
            area = info_ex.rcMonitor
            monitor_rect = (area.left, area.top, area.right, area.bottom)
        class_buffer = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, class_buffer, 256)
        pid = wintypes.DWORD(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        if pid.value:
            process = _kernel32.OpenProcess(
                _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value,
            )
            if process:
                size = wintypes.DWORD(1024)
                name_buffer = ctypes.create_unicode_buffer(1024)
                if _kernel32.QueryFullProcessImageNameW(
                        process, 0, name_buffer, ctypes.byref(size)):
                    exe = name_buffer.value
                _kernel32.CloseHandle(process)
        return {
            "hwnd": hwnd,
            "rect": (rect.left, rect.top, rect.right, rect.bottom),
            "monitor": monitor_rect,
            "class": class_buffer.value,
            "exe": exe,
            "pid": pid.value,
        }
    except Exception:
        return None
