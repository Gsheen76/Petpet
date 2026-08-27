"""App-wide font helpers for the Petpet UI."""

from __future__ import annotations

from PyQt5.QtGui import QFont

APP_FONT_FAMILY = "幼圆"


def apply_app_font(app):
    """Set the rounded YouYuan face as the default application font."""
    app.setFont(QFont(APP_FONT_FAMILY))
    return APP_FONT_FAMILY
