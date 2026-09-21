"""DPI-independent typography shared by Petpet's full-window UI."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, QRect
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
    from PyQt5.QtCore import QPoint, QRect
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


def center_window_on_screen(
    window, screen, min_width=520, min_height=560,
    margin_x=30, margin_y=35,
):
    """窗口自适应落位（2026-09-20 定稿，任意屏幕尺寸/布局/DPR）：
    先按目标屏收缩超出部分（保留最小可用尺寸），再居中并整体钳进
    屏内——小副屏不溢出、负原点屏（左/上副屏）不落错、大屏零改动。
    """
    size = window.size()
    width, height = size.width(), size.height()
    max_width = max(min_width, screen.width() - margin_x * 2)
    max_height = max(min_height, screen.height() - margin_y * 2)
    if width > max_width or height > max_height:
        width, height = min(width, max_width), min(height, max_height)
        window.setFixedSize(width, height)
    x = screen.x() + (screen.width() - width) // 2
    y = screen.y() + (screen.height() - height) // 2
    window.move(QPoint(
        max(screen.x(), min(x, screen.right() + 1 - width)),
        max(screen.y(), min(y, screen.bottom() + 1 - height)),
    ))


def clamp_rect_into_screen(rect, screen_rect):
    """把窗口矩形平移钳进目标屏（屏幕热变更自愈 2026-09-21）。

    只平移不缩放：窗口任一边越出屏就贴回该边；窗口比屏大（如装修
    全景 2138 宽遇上窄屏）时对齐屏左上角，不做压缩。
    """
    if rect.width() >= screen_rect.width():
        x = screen_rect.x()
    else:
        x = max(
            screen_rect.x(),
            min(rect.x(), screen_rect.x() + screen_rect.width() - rect.width()),
        )
    if rect.height() >= screen_rect.height():
        y = screen_rect.y()
    else:
        y = max(
            screen_rect.y(),
            min(rect.y(), screen_rect.y() + screen_rect.height() - rect.height()),
        )
    return QRect(x, y, rect.width(), rect.height())


def _rect_overlap_area(a, b):
    w = min(a.right(), b.right()) - max(a.x(), b.x()) + 1
    h = min(a.bottom(), b.bottom()) - max(a.y(), b.y()) + 1
    return max(0, w) * max(0, h)


def pick_screen_rect_for(rect, screen_rects):
    """返回与窗口矩形最相干的屏矩形：重叠面积最大者优先，全无重叠时
    中心距最近者优先；空列表返回 None。"""
    if not screen_rects:
        return None
    cx, cy = rect.x() + rect.width() / 2, rect.y() + rect.height() / 2

    def score(screen):
        scx = screen.x() + screen.width() / 2
        scy = screen.y() + screen.height() / 2
        distance = ((cx - scx) ** 2 + (cy - scy) ** 2) ** 0.5
        return (_rect_overlap_area(rect, screen), -distance)

    return max(screen_rects, key=score)


def clamp_window_into_nearest_screen(window, screen_rects):
    """把窗口钳进与其最相干的有效屏（2026-09-21）。返回是否移动。"""
    rect = window.geometry()
    target = pick_screen_rect_for(rect, screen_rects)
    if target is None:
        return False
    new = clamp_rect_into_screen(rect, target)
    if new.topLeft() != rect.topLeft():
        window.move(new.topLeft())
        return True
    return False
