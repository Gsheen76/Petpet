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
