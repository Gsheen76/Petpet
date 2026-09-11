"""开机自启动（2026-09-12）：Windows HKCU Run 键注册。

源码运行时优先用同目录的 pythonw（无控制台闪窗）；打包版直接
注册自身 exe。仅 Windows——其他平台 ``is_supported`` 为假，UI 隐藏。
"""

from __future__ import annotations

import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Petpet"


def is_supported() -> bool:
    return sys.platform.startswith("win")


def _launcher_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    interpreter = pythonw if os.path.isfile(pythonw) else sys.executable
    # pet.py 在仓库根：petpet/app/ 要上两级。
    pet = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "pet.py"))
    return f'"{interpreter}" "{pet}"'


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """写入/移除自启动项；返回是否成功。"""
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(
                    key, VALUE_NAME, 0, winreg.REG_SZ, _launcher_path())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
