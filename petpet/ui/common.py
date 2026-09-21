"""DPI-independent typography shared by Petpet's full-window UI."""

from __future__ import annotations

from PyQt5.QtGui import QFont


FIXED_FONT_SCALE = 2.0
SETTINGS_FONT_SCALE = 1.08


def font_px(size):
    """Scale typography used by the pet's compact on-screen surfaces."""
    return max(1, int(round(float(size) * FIXED_FONT_SCALE)))


def independent_font_px(size):
    """Keep full-window and system-menu typography at its authored size."""
    return max(1, int(round(float(size))))


def settings_font_px(size):
    """Map the settings value 20 to the former value-12 visual size."""
    return max(1, int(round(float(size) * SETTINGS_FONT_SCALE)))


def tutorial_font_px(size):
    """Keep tutorial typography independent from the compact pet scale."""
    return independent_font_px(size)


def pixel_font(size, weight=QFont.Normal, family="Microsoft YaHei"):
    """Create a font whose rendered size is independent of monitor DPI."""
    font = QFont(family)
    font.setPixelSize(font_px(size))
    font.setWeight(weight)
    return font


def independent_pixel_font(
    size, weight=QFont.Normal, family="Microsoft YaHei"
):
    """Create crisp full-window typography without compact-surface scaling."""
    font = QFont(family)
    font.setPixelSize(independent_font_px(size))
    font.setWeight(weight)
    return font


def pet_screen_rect(pet):
    """宠物当前所在屏的矩形（多屏定稿 2026-09-20）。

    面板打开位置跟随宠物所在屏：优先 interface_screen_rect（含界面
    锚点逻辑，聊天窗/设置页同款），退 current_screen_rect（测试夹具
    常用），再退主屏可用区。返回 QRect。
    """
    from PyQt5.QtCore import QRect
    from PyQt5.QtWidgets import QApplication

    for name in ("interface_screen_rect", "current_screen_rect"):
        getter = getattr(pet, name, None)
        if callable(getter):
            try:
                rect = getter()
            except RuntimeError:
                rect = None
            if isinstance(rect, QRect) and not rect.isEmpty():
                return rect
    return QApplication.primaryScreen().availableGeometry()
