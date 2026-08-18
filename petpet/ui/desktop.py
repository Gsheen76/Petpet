"""Desktop pet status, menu, reward, interaction, and speech surfaces."""

import math
import time

from petpet.chat import api as ai
from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PyQt5.QtWidgets import QApplication, QWidget

from petpet.ui.common import pixel_font


_dependency_resolver = None


def configure_dependency_resolver(resolver):
    """Install the legacy-entry dependency resolver used at interaction time."""
    global _dependency_resolver
    _dependency_resolver = resolver


def _dependency(name):
    if _dependency_resolver is None:
        raise RuntimeError(f"Desktop UI dependency is not configured: {name}")
    return _dependency_resolver(name)


def pet_interface_anchor_rect(pet):
    """Return the active pet geometry while preserving legacy hosts."""
    getter = getattr(pet, "interface_anchor_rect", None)
    if callable(getter):
        return getter()
    return pet.geometry()


def move_window_if_needed(widget, x, y):
    """Avoid issuing native window moves when an overlay is already aligned."""
    target = QPoint(int(x), int(y))
    position = getattr(widget, "pos", None)
    if not callable(position) or position() != target:
        widget.move(int(x), int(y))


def pet_interface_anchor_visible(pet):
    """Return anchor visibility for PetWindow and lightweight UI hosts."""
    getter = getattr(pet, "interface_anchor_visible", None)
    if callable(getter):
        return bool(getter())
    visible = getattr(pet, "isVisible", None)
    return bool(visible()) if callable(visible) else True


def pet_interface_screen_rect(pet):
    """Return the active anchor's screen with the former host fallback."""
    getter = getattr(pet, "interface_screen_rect", None)
    if callable(getter):
        return getter()
    current_screen = getattr(pet, "current_screen_rect", None)
    if callable(current_screen):
        return current_screen()
    screen = QApplication.screenAt(pet_interface_anchor_rect(pet).center())
    if screen is None:
        screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else QRect()


def pet_interface_bonus_origin(pet, y_offset=-10):
    """Return a reward origin for both PetWindow and legacy test hosts."""
    getter = getattr(pet, "interface_bonus_origin", None)
    if callable(getter):
        return getter(y_offset)
    anchor = pet_interface_anchor_rect(pet)
    return anchor.center().x(), anchor.top() + int(y_offset)


class StatBubble(QWidget):
    """A warm, readable growth card shown above the right-click actions."""
    def __init__(self, pet, show_window=True):
        super().__init__()
        self.pet = pet
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(620, 416)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)  # refresh stats 2x/sec
        self._place()
        if show_window:
            self.show()
            self.raise_()

    def _tick(self):
        self.update()

    @staticmethod
    def companionship_text(days):
        return f"♡ 陪伴 {max(1, int(days))} 天"

    @staticmethod
    def header_badge_font():
        """Use one crisp font for both compact header badges."""
        return pixel_font(9, QFont.Bold)

    def header_rects(self):
        """Keep the title, rename control and badges in separate columns."""
        width = self.width()
        return {
            "title": QRectF(27, 15, 248, 40),
            "edit": QRectF(282, 17, 36, 36),
            "coin": QRectF(width - 294, 18, 112, 33),
            "days": QRectF(width - 174, 18, 148, 33),
        }

    def name_edit_rect(self):
        return self.header_rects()["edit"]

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton
                and self.name_edit_rect().contains(QPointF(event.pos()))):
            dialog = _dependency("PetNameEditDialog")(
                self.pet.pet_name,
                self.pet.set_pet_name,
                self.pet if isinstance(self.pet, QWidget) else None,
            )
            self._name_dialog = dialog
            dialog.center_on_screen(pet_interface_screen_rect(self.pet))
            dialog.exec_()
            self._name_dialog = None
            try:
                self.update()
            except RuntimeError:
                pass
            return
        super().mousePressEvent(event)

    def _place(self):
        """Place above the action bubbles, centered on the pet."""
        g = pet_interface_anchor_rect(self.pet)
        scr = pet_interface_screen_rect(self.pet)
        w, h = self.width(), self.height()
        x = g.center().x() - w // 2
        y = g.top() - h - 112
        x = max(scr.left(), min(x, scr.right() - w))
        y = max(scr.top(), min(y, scr.bottom() - h))
        move_window_if_needed(self, x, y)

    @staticmethod
    def _fit_font(text, preferred_size, max_width, weight=QFont.Normal,
                  minimum_size=8):
        """Return the largest font that keeps dynamic text fully visible."""
        size = preferred_size
        while size > minimum_size:
            font = pixel_font(size, weight)
            if QFontMetrics(font).horizontalAdvance(str(text)) <= max_width:
                return font
            size -= 1
        return pixel_font(minimum_size, weight)

    @staticmethod
    def _draw_stat_icon(painter, rect, kind, color):
        """Draw font-independent hunger, mood, and energy pictograms."""
        painter.save()
        c = QColor(color)
        cx, cy = rect.center().x(), rect.center().y()
        if kind == "hunger":
            painter.setPen(QPen(c, 5, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(rect.left() + 10, cy),
                             QPointF(rect.right() - 10, cy))
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            for x in (rect.left() + 9, rect.right() - 9):
                painter.drawEllipse(QPointF(x, cy - 4), 3.5, 3.5)
                painter.drawEllipse(QPointF(x, cy + 4), 3.5, 3.5)
        elif kind == "mood":
            path = QPainterPath()
            path.moveTo(cx, rect.bottom() - 7)
            path.cubicTo(rect.left() + 5, cy + 2,
                         rect.left() + 5, rect.top() + 8,
                         cx, rect.top() + 12)
            path.cubicTo(rect.right() - 5, rect.top() + 8,
                         rect.right() - 5, cy + 2,
                         cx, rect.bottom() - 7)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawPath(path)
        else:
            points = QPolygonF([
                QPointF(cx + 2, rect.top() + 5),
                QPointF(cx - 8, cy + 2),
                QPointF(cx - 1, cy + 2),
                QPointF(cx - 5, rect.bottom() - 5),
                QPointF(cx + 10, cy - 4),
                QPointF(cx + 3, cy - 4),
            ])
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawPolygon(points)
        painter.restore()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        st = self.pet.state
        W, H = self.width(), self.height()
        outer = QRectF(7, 5, W - 14, H - 13)

        # Soft cocoa shadow and warm milk-card background.
        p.setBrush(QColor(92, 60, 42, 42))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(outer.adjusted(3, 4, 3, 4), 24, 24)
        bg = QLinearGradient(outer.topLeft(), outer.bottomRight())
        bg.setColorAt(0.0, QColor(255, 252, 242, 252))
        bg.setColorAt(0.55, QColor(255, 244, 224, 252))
        bg.setColorAt(1.0, QColor(255, 237, 219, 252))
        p.setBrush(bg)
        p.setPen(QPen(QColor(235, 190, 154), 1.3))
        p.drawRoundedRect(outer, 24, 24)

        lvl = st.get("level", 1)
        xp = int(st.get("xp", 0))
        need = _dependency("xp_to_next")(lvl)
        days = max(1, int((time.time() - st.get("born", time.time())) / 86400))

        # ---- Header: title and companionship badge never share a text rect. ----
        title_text = f"🐾 {self.pet.pet_name} 的小屋"
        header_rects = self.header_rects()
        title_rect = header_rects["title"]
        p.setPen(QColor("#7b4d3a"))
        p.setFont(self._fit_font(
            title_text, 16, title_rect.width(), QFont.Bold, 7
        ))
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                   title_text)
        edit_rect = self.name_edit_rect()
        p.setBrush(QColor("#fff1e5"))
        p.setPen(QPen(QColor("#eab59f"), 1))
        p.drawEllipse(edit_rect)
        p.setPen(QColor("#c2735d"))
        p.setFont(pixel_font(15, QFont.Bold))
        p.drawText(edit_rect, Qt.AlignCenter, "✎")

        coin_text = f"Pet币 {st.get('pet_coins', 0)}"
        coin_rect = header_rects["coin"]
        p.setBrush(QColor(255, 241, 198, 240))
        p.setPen(QPen(QColor("#e8be68"), 1))
        p.drawRoundedRect(coin_rect, 16, 16)
        p.setPen(QColor("#a66a26"))
        p.setFont(self.header_badge_font())
        p.drawText(
            coin_rect.adjusted(6, 0, -6, 0),
            Qt.AlignCenter | Qt.TextSingleLine,
            coin_text,
        )

        days_text = self.companionship_text(days)
        days_rect = header_rects["days"]
        p.setBrush(QColor(255, 224, 214, 235))
        p.setPen(QPen(QColor("#e9a494"), 1))
        p.drawRoundedRect(days_rect, 16, 16)
        p.setPen(QColor("#a95f55"))
        p.setFont(self.header_badge_font())
        p.drawText(days_rect.adjusted(9, 0, -9, 0),
                   Qt.AlignCenter | Qt.TextSingleLine, days_text)

        # ---- Growth card: level badge, XP label/value, then progress bar. ----
        growth = QRectF(22, 64, W - 44, 80)
        p.setBrush(QColor(255, 255, 255, 178))
        p.setPen(QPen(QColor(242, 209, 174), 1))
        p.drawRoundedRect(growth, 18, 18)

        level_rect = QRectF(34, 77, 104, 54)
        level_grad = QLinearGradient(level_rect.topLeft(), level_rect.bottomRight())
        level_grad.setColorAt(0.0, QColor("#ffb989"))
        level_grad.setColorAt(1.0, QColor("#ff8f70"))
        p.setBrush(level_grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(level_rect, 16, 16)
        level_text = f"LV.{lvl}"
        p.setPen(QColor(255, 255, 255))
        p.setFont(self._fit_font(level_text, 18, level_rect.width() - 16,
                                 QFont.Bold, 6))
        p.drawText(level_rect.adjusted(8, 0, -8, 0),
                   Qt.AlignCenter | Qt.TextSingleLine, level_text)

        xp_area_x = 158
        xp_area_w = W - xp_area_x - 34
        xp_rate = _dependency("progression").passive_xp_per_minute(st)
        rate_text = f"经验  +{xp_rate:.1f} EXP/min"
        p.setPen(QColor("#8a6654"))
        p.setFont(self._fit_font(
            rate_text, 10, 202, QFont.Bold, 7
        ))
        p.drawText(
            QRectF(xp_area_x, 76, 202, 23),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            rate_text,
        )
        xp_text = f"{xp} / {need} EXP"
        xp_value_rect = QRectF(
            xp_area_x + 205, 76, xp_area_w - 205, 23
        )
        p.setFont(self._fit_font(xp_text, 10, xp_value_rect.width(),
                                 QFont.Bold, 6))
        p.setPen(QColor("#b47b31"))
        p.drawText(xp_value_rect, Qt.AlignRight | Qt.AlignVCenter |
                   Qt.TextSingleLine, xp_text)

        xp_rect = QRectF(xp_area_x, 111, xp_area_w, 14)
        p.setBrush(QColor(244, 226, 207))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(xp_rect, 6.5, 6.5)
        progress = max(0.0, min(1.0, xp / max(1, need)))
        xp_fill = QRectF(xp_rect.left(), xp_rect.top(),
                         xp_rect.width() * progress, xp_rect.height())
        xp_grad = QLinearGradient(xp_rect.topLeft(), xp_rect.topRight())
        xp_grad.setColorAt(0.0, QColor("#ffc55c"))
        xp_grad.setColorAt(1.0, QColor("#ffdf85"))
        p.setBrush(xp_grad)
        p.drawRoundedRect(xp_fill, 7, 7)

        # ---- Affection: its level alone controls passive EXP per second. ----
        affection_level = int(st.get("affection_level", 1))
        affection_points = int(st.get("affection_points", 0))
        affection_need = _dependency("progression").affection_to_next(affection_level)
        affection_card = QRectF(22, 154, W - 44, 70)
        affection_bg = QLinearGradient(
            affection_card.topLeft(), affection_card.topRight()
        )
        affection_bg.setColorAt(0.0, QColor(255, 232, 229, 210))
        affection_bg.setColorAt(1.0, QColor(255, 246, 225, 210))
        p.setBrush(affection_bg)
        p.setPen(QPen(QColor("#efb5a7"), 1))
        p.drawRoundedRect(affection_card, 17, 17)

        heart_rect = QRectF(35, 166, 45, 45)
        p.setBrush(QColor(255, 255, 255, 210))
        p.setPen(Qt.NoPen)
        p.drawEllipse(heart_rect)
        p.setPen(QColor("#ef877c"))
        p.setFont(pixel_font(20, QFont.Bold))
        p.drawText(heart_rect, Qt.AlignCenter, "♡")

        affection_title = f"好感 Lv.{affection_level}"
        p.setPen(QColor("#82584f"))
        p.setFont(self._fit_font(
            affection_title, 11, 122, QFont.Bold, 8
        ))
        p.drawText(
            QRectF(91, 159, 122, 29),
            Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
            affection_title,
        )
        affection_value = f"{affection_points} / {affection_need}"
        p.setPen(QColor("#d37469"))
        p.setFont(self._fit_font(
            affection_value, 10, 94, QFont.Bold, 7
        ))
        p.drawText(
            QRectF(210, 159, 94, 29),
            Qt.AlignRight | Qt.AlignVCenter | Qt.TextSingleLine,
            affection_value,
        )
        affection_rate = _dependency("progression").passive_affection_per_minute(st)
        affection_rate_text = f"陪伴 +{affection_rate:.3f}/min"
        p.setPen(QColor("#a86d61"))
        p.setFont(self._fit_font(
            affection_rate_text, 9, W - 344, QFont.Bold, 7
        ))
        p.drawText(
            QRectF(320, 159, W - 354, 29),
            Qt.AlignRight | Qt.AlignVCenter | Qt.TextSingleLine,
            affection_rate_text,
        )

        affection_bar = QRectF(91, 196, W - 126, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(246, 220, 210))
        p.drawRoundedRect(affection_bar, 5, 5)
        affection_progress = max(
            0.0,
            min(1.0, affection_points / max(1, affection_need)),
        )
        affection_fill = QRectF(
            affection_bar.left(),
            affection_bar.top(),
            affection_bar.width() * affection_progress,
            affection_bar.height(),
        )
        affection_grad = QLinearGradient(
            affection_bar.topLeft(), affection_bar.topRight()
        )
        affection_grad.setColorAt(0.0, QColor("#f18d88"))
        affection_grad.setColorAt(1.0, QColor("#ffc28f"))
        p.setBrush(affection_grad)
        p.drawRoundedRect(affection_fill, 5, 5)

        # ---- Three stat cards with dedicated name/value/status regions. ----
        stats = [
            ("hunger", "饱腹", st.get("hunger", 0), "#f49a62",
             ("肚肚空空", "刚刚好", "肚肚饱饱")),
            ("mood", "心情", st.get("mood", 0), "#ef8fa2",
             ("想要抱抱", "心情不错", "开心摇尾巴")),
            ("energy", "精力", st.get("energy", 0), "#9b8ade",
             ("需要充电", "精神还好", "元气满满")),
        ]
        pad = 20
        gap = 12
        card_w = (W - pad * 2 - gap * 2) / 3
        card_y = 238
        card_h = 145
        for i, (icon_kind, name, val, color, moods) in enumerate(stats):
            val = max(0.0, min(100.0, float(val)))
            cx = pad + i * (card_w + gap)
            card = QRectF(cx, card_y, card_w, card_h)
            tint = QColor(color)
            tint.setAlpha(30)
            p.setBrush(tint)
            p.setPen(QPen(QColor(color).lighter(125), 1))
            p.drawRoundedRect(card, 16, 16)

            icon_rect = QRectF(cx + 13, card_y + 13, 42, 42)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawEllipse(icon_rect)
            self._draw_stat_icon(
                p, icon_rect.adjusted(5, 5, -5, -5), icon_kind, color)

            name_rect = QRectF(cx + 64, card_y + 12, 52, 34)
            p.setPen(QColor("#76584b"))
            p.setFont(self._fit_font(
                name, 12, name_rect.width(), QFont.Bold, 10))
            p.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter |
                       Qt.TextSingleLine, name)

            value_text = f"{int(round(val))}%"
            value_rect = QRectF(cx + 118, card_y + 11, card_w - 130, 35)
            p.setPen(QColor(color))
            p.setFont(self._fit_font(value_text, 14, value_rect.width(),
                                     QFont.Bold, 8))
            p.drawText(value_rect, Qt.AlignRight | Qt.AlignVCenter |
                       Qt.TextSingleLine, value_text)

            br = QRectF(cx + 15, card_y + 75, card_w - 30, 11)
            p.setBrush(QColor(255, 255, 255, 190))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(br, 5, 5)
            fill = QRectF(br.left(), br.top(), br.width() * val / 100, br.height())
            p.setBrush(QColor(color))
            p.drawRoundedRect(fill, 5, 5)

            mood_text = moods[0] if val < 35 else (moods[1] if val < 70 else moods[2])
            mood_rect = QRectF(cx + 12, card_y + 105, card_w - 24, 27)
            p.setPen(QColor("#8a6f62"))
            p.setFont(self._fit_font(mood_text, 9, mood_rect.width(),
                                     QFont.Normal, 8))
            p.drawText(mood_rect, Qt.AlignCenter | Qt.TextSingleLine, mood_text)


class BubbleMenu(QWidget):
    """Soft candy-style action buttons with a warm growth card."""
    PRIMARY_ACTIONS = [
        ("💬", "聊天", "chat", "#ef8fa2"),
        ("🏠", "小屋", "home", "#cf9770"),
        ("🛍", "商店", "shop", "#e0a85f"),
        ("🤝", "互动", "interaction", "#72bf9b"),
        ("⋯", "更多", "more", "#e7ae64"),
    ]
    INTERACTION_ACTIONS = [
        ("🖐", "抚摸", "pet", "#ef8fa2"),
        ("🍖", "喂食", "feed", "#f49a62"),
        ("🎾", "玩耍", "play", "#72bf9b"),
        ("💤", "睡觉", "sleep", "#9b8ade"),
    ]
    MORE_ACTIONS = [
        ("📒", "记录", "records", "#df9f6f"),
        ("🏅", "成就", "achievements", "#efa47d"),
        ("🎮", "小游戏", "minigames", "#72b6b0"),
        ("⚙️", "设置", "settings", "#e7ae64"),
        ("👁", "隐藏", "hide", "#79a9d8"),
        ("📖", "教程", "tutorial", "#d392bd"),
        ("↩", "返回", "back", "#79bd9a"),
        ("✕", "退出", "quit", "#df8f91"),
    ]
    PAGE_COLUMNS = {"primary": 5, "interaction": 4, "more": 5}

    @staticmethod
    def action_needs_attention(action, *, has_claimable,
                               needs_personal_setup, zero_actions=()):
        zero_actions = set(zero_actions)
        return (
            (action in ("more", "achievements") and has_claimable)
            or (action == "chat" and needs_personal_setup)
            or action in zero_actions
            or (action == "interaction" and bool(zero_actions))
        )

    def __init__(self, pet, page="primary", show_window=True):
        super().__init__()
        self.pet = pet
        self.page = page if page in self.PAGE_COLUMNS else "primary"
        action_sets = {
            "primary": self.PRIMARY_ACTIONS,
            "interaction": self.INTERACTION_ACTIONS,
            "more": self.MORE_ACTIONS,
        }
        self.actions = list(action_sets[self.page])
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Larger hit targets with room for both icon and label.
        self.W = 590 if self.page in ("primary", "more") else 470
        self.H = 200 if self.page == "more" else 112
        self.resize(self.W, self.H)
        self._bubble_rects = []
        self._hover = -1
        self._press = -1
        self._closing = False
        self._prewarming = False
        self._hover_scales = [0.0] * len(self.actions)
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(16)
        self._app = QApplication.instance()
        if self._app is not None:
            self._app.applicationStateChanged.connect(
                self._on_application_state_changed
            )
            self._app.installEventFilter(self)

        # The growth card belongs only to the primary interaction canvas.
        # Opening "更多" replaces the whole first canvas.
        self.stat_bubble = (
            _dependency("StatBubble")(pet, show_window=show_window)
            if self.page == "primary" else None
        )

        self._place()
        if show_window:
            self.show()
            self.raise_()
            self.activateWindow()
        self.setMouseTracking(True)

    def _tick(self):
        # ease hover scales
        target = [1.0 if i == self._hover else 0.0 for i in range(len(self.actions))]
        changed = False
        for i in range(len(self.actions)):
            diff = target[i] - self._hover_scales[i]
            if abs(diff) > 0.01:
                self._hover_scales[i] += diff * 0.25
                changed = True
        if changed:
            self.update()

    def follow_pet(self):
        """Reposition both the bubble menu and stat bubble to follow the pet."""
        self._place()
        if self.stat_bubble is not None:
            try:
                self.stat_bubble._place()
            except Exception:
                pass

    def _place(self):
        """Position the row of bubbles just above the pet's head."""
        g = pet_interface_anchor_rect(self.pet)
        x = g.center().x() - self.W // 2
        y = g.top() - self.H + 19
        scr = pet_interface_screen_rect(self.pet)
        x = max(scr.left(), min(x, scr.right() - self.W))
        y = max(scr.top(), min(y, scr.bottom() - self.H))
        self.move(int(x), int(y))

    @staticmethod
    def needs_api_key_configuration():
        return ai.needs_personal_setup_reminder()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._bubble_rects = []
        n = len(self.actions)
        button_w = 102
        button_h = 78
        gap = 10
        columns = self.PAGE_COLUMNS[self.page]
        rows = int(math.ceil(n / columns))
        total_w = columns * button_w + (columns - 1) * gap
        total_h = rows * button_h + (rows - 1) * gap
        start_x = (self.W - total_w) / 2
        start_y = (self.H - total_h) / 2
        has_claimable = _dependency("progression").has_claimable_achievements(
            self.pet.state
        )
        needs_api_key = self.needs_api_key_configuration()
        zero_record_actions = _dependency("progression").zero_stat_interaction_actions(
            self.pet.state
        )
        zero_actions = {
            {
                "pettings": "pet",
                "feedings": "feed",
                "play_sessions": "play",
                "manual_sleeps": "sleep",
            }[action]
            for action in zero_record_actions
        }
        for i, (emoji, label, action, color) in enumerate(self.actions):
            row = i // columns
            column = i % columns
            bx = start_x + column * (button_w + gap)
            by = start_y + row * (button_h + gap)
            scale = 1.0 + self._hover_scales[i] * 0.07
            if self._press == i:
                scale *= 0.96
            bw = button_w * scale
            bh = button_h * scale
            rect = QRectF(
                bx + (button_w - bw) / 2,
                by + (button_h - bh) / 2,
                bw, bh,
            )
            self._bubble_rects.append((i, rect, action, color, emoji))

            # Warm soft shadow.
            p.setBrush(QColor(92, 60, 42, 48))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect.adjusted(2, 4, 2, 4), 23, 23)

            # Pastel candy surface.
            c = QColor(color)
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, c.lighter(145))
            grad.setColorAt(1.0, c.lighter(108))
            p.setBrush(grad)
            p.setPen(QPen(c.darker(120), 1.2))
            p.drawRoundedRect(rect, 23, 23)

            # Top gloss makes each button feel like a soft candy.
            gloss = QRectF(rect.x() + 8, rect.y() + 5,
                           rect.width() - 16, rect.height() * 0.38)
            gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
            gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 105))
            gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(gloss_grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(gloss, 16, 16)

            p.setPen(QColor(255, 255, 255))
            p.setFont(pixel_font(17, QFont.Bold))
            p.drawText(QRectF(rect.x(), rect.y() + 7, rect.width(), 34),
                       Qt.AlignCenter, emoji)
            p.setFont(pixel_font(10, QFont.Bold))
            p.drawText(QRectF(rect.x() + 5, rect.y() + 43,
                              rect.width() - 10, 25),
                       Qt.AlignCenter | Qt.TextSingleLine, label)

            # Claimable achievements place a clear red reminder on both the
            # primary "更多" entry and the secondary "成就" entry.
            if self.action_needs_attention(
                    action,
                    has_claimable=has_claimable,
                    needs_personal_setup=needs_api_key,
                    zero_actions=zero_actions):
                dot_center = QPointF(rect.right() - 10, rect.top() + 10)
                p.setBrush(QColor(255, 255, 255))
                p.setPen(Qt.NoPen)
                p.drawEllipse(dot_center, 8, 8)
                p.setBrush(QColor("#ee5e62"))
                p.drawEllipse(dot_center, 5.5, 5.5)

    def mouseMoveEvent(self, e):
        pos = e.pos()
        new_hover = -1
        for i, rect, _, _, _ in self._bubble_rects:
            if rect.contains(QPointF(pos)):
                new_hover = i; break
        if new_hover != self._hover:
            self._hover = new_hover

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            self._close()
            return
        pos = e.pos()
        for i, rect, action, _, _ in self._bubble_rects:
            if rect.contains(QPointF(pos)):
                self._press = i
                self.update()
                return
        self._close()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = e.pos()
            for i, rect, action, _, _ in self._bubble_rects:
                if rect.contains(QPointF(pos)) and self._press == i:
                    self._press = -1
                    self._run_action(action)
                    return
            self._press = -1
            if not any(rect.contains(QPointF(pos)) for _, rect, _, _, _ in self._bubble_rects):
                self._close()

    def _run_action(self, action):
        pet = self.pet
        if action in ("more", "interaction", "back"):
            # Switching pages always replaces the complete current canvas.
            # Returning rebuilds the primary growth card and five bubbles.
            target_page = {
                "more": "more",
                "interaction": "interaction",
                "back": "primary",
            }[action]
            self._close()
            factory = getattr(pet, "_create_bubble_menu", None)
            pet._bubble_menu = (
                factory(target_page)
                if callable(factory)
                else _dependency("BubbleMenu")(pet, page=target_page)
            )
            return

        if action == "chat":
            pet.chat()
        elif action == "pet":
            pet.pet_click()
        elif action == "feed":
            pet.feed()
        elif action == "play":
            pet.play()
        elif action == "sleep":
            pet.toggle_sleep()
        elif action == "settings":
            pet.open_settings()
        elif action == "records":
            pet.open_records()
        elif action == "achievements":
            pet.open_achievements()
        elif action == "shop":
            pet.open_shop()
        elif action == "home":
            pet.open_home_scene()
        elif action == "minigames":
            pet.open_minigames()
        elif action in ("hide", "tutorial", "quit"):
            self._close()
            callback = getattr(pet, "_app_action_cb", None)
            if callable(callback):
                callback(action)
            return
        self._close()

    def _close(self):
        if self._closing:
            return
        self._closing = True
        if self._app is not None:
            try:
                self._app.applicationStateChanged.disconnect(
                    self._on_application_state_changed
                )
            except (TypeError, RuntimeError):
                pass
            try:
                self._app.removeEventFilter(self)
            except (TypeError, RuntimeError):
                pass
        if self.stat_bubble is not None:
            try:
                self.stat_bubble.close()
            except Exception:
                pass
        try:
            self.releaseMouse()
        except Exception:
            pass
        self.close()
        if getattr(self.pet, "_bubble_menu", None) is self:
            self.pet._bubble_menu = None
        restore = getattr(self.pet, "restore_treasure_after_menu", None)
        if callable(restore):
            QTimer.singleShot(0, restore)

    def _on_application_state_changed(self, state):
        if (state == Qt.ApplicationInactive and self.isVisible()
                and not getattr(self, "_prewarming", False)):
            self._close()

    def eventFilter(self, watched, event):
        if (not self._closing
                and not getattr(self, "_prewarming", False)
                and self.isVisible()
                and event.type() == QEvent.MouseButtonPress
                and hasattr(event, "globalPos")):
            point = event.globalPos()
            inside = self.frameGeometry().contains(point)
            if self.stat_bubble is not None:
                try:
                    inside = inside or (
                        self.stat_bubble.isVisible()
                        and self.stat_bubble.frameGeometry().contains(point)
                    )
                    name_dialog = getattr(
                        self.stat_bubble, "_name_dialog", None
                    )
                    inside = inside or (
                        name_dialog is not None
                        and name_dialog.isVisible()
                        and name_dialog.frameGeometry().contains(point)
                    )
                except RuntimeError:
                    pass
            if not inside:
                QTimer.singleShot(0, self._close)
        return False

    def event(self, event):
        if (
            event.type() == QEvent.UngrabMouse
            and self.isVisible()
            and not self._closing
            and not getattr(self, "_prewarming", False)
        ):
            QTimer.singleShot(0, self._close)
        return super().event(event)

    def hideEvent(self, event):
        if not self._closing:
            QTimer.singleShot(0, self._close)
        super().hideEvent(event)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._close()


class BonusBubble(QWidget):
    """A floating '+25 饱腹' style bubble that drifts up and fades out.
    Shown after the user interacts with the pet via an InteractiveBubble."""
    def __init__(self, text, x, y, color="#ff8c42"):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.text = text
        self.color = QColor(color)
        self.life = 0
        self.setFont(pixel_font(14, QFont.Bold))
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(text) + 36
        h = fm.height() + 20
        self.resize(w, h)
        self.move(int(x - w/2), int(y - h))
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(33)
        self.show()

    def _tick(self):
        self.life += 1
        if self.life <= 36:
            self.move(self.x(), self.y() - 2)
        if self.life > 36:
            op = max(0, 1 - (self.life - 36) / 18)
            self.setWindowOpacity(op)
        if self.life > 54:
            self.close()
            return
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)
        # soft shadow
        shadow = QRectF(r.x()+2, r.y()+3, r.width(), r.height())
        p.setBrush(QColor(0, 0, 0, 45))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(shadow, 14, 14)
        # main pill — white with subtle color tint
        bg = QColor(self.color); bg.setAlpha(35)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor(255, 255, 255))
        grad.setColorAt(1.0, bg)
        p.setBrush(grad)
        p.setPen(QPen(self.color, 1.5))
        p.drawRoundedRect(r, 14, 14)
        # top gloss highlight
        gloss = QRectF(r.x()+3, r.y()+2, r.width()-6, r.height()/2.5)
        g2 = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        g2.setColorAt(0.0, QColor(255, 255, 255, 120))
        g2.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(g2)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(gloss, 11, 11)
        # colored bold text
        p.setPen(self.color)
        p.setFont(self.font())
        p.drawText(r, Qt.AlignCenter, self.text)


class InteractiveBubble(QWidget):
    """A clickable bubble floating above the pet, e.g. '🦴 喂我'.
    Refined style: soft shadow, gradient, pulse animation, oval shape.
    Clicking triggers the associated action and shows a BonusBubble."""
    def __init__(self, pet, label, action_name, color, bonus_text):
        super().__init__()
        self.pet = pet
        self.action_name = action_name
        self.bonus_text = bonus_text
        self.color = color
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(pixel_font(12, QFont.Bold))
        if action_name == "dig_reward":
            self.resize(80, 80)
        else:
            fm = self.fontMetrics()
            w = max(148, fm.horizontalAdvance(label) + 64)
            self.resize(w + 16, 64)
        self.label = label
        self._pulse = 0.0
        self._hovered = False
        self._tail_on_left = True
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._anim.start(40)
        self._place_above_pet()
        self.show()

    def _tick(self):
        self._pulse += 0.08
        self.update()

    def _place_above_pet(self):
        """Place bubble to the side of the pet that has more room.
        If pet is in left half of screen -> bubble goes right; else left."""
        g = pet_interface_anchor_rect(self.pet)
        scr = pet_interface_screen_rect(self.pet)
        pet_cx = g.center().x()
        screen_cx = scr.center().x()
        if getattr(self, "action_name", None) == "dig_reward":
            x = pet_cx - self.width() // 2
            # Keep the treasure badge clear of the pet's head: this places
            # its bottom edge 22px above the pet's top edge.
            y = g.top() - 21
            x = max(scr.left(), min(x, scr.right() - self.width()))
            y = max(scr.top(), min(y, scr.bottom() - self.height()))
            move_window_if_needed(self, x, y)
            return
        toward_pet = 12
        if pet_cx < screen_cx:
            # Bubble is on the right, so shift it left toward the pet.
            x = g.right() + 8 - toward_pet
            self._tail_on_left = True
        else:
            # Bubble is on the left, so shift it right toward the pet.
            x = g.left() - self.width() - 8 + toward_pet
            self._tail_on_left = False
        y = g.center().y() - self.height() // 2 + 15
        # clamp to screen
        x = max(scr.left(), min(x, scr.right() - self.width()))
        y = max(scr.top(), min(y, scr.bottom() - self.height()))
        move_window_if_needed(self, x, y)

    def mousePressEvent(self, e):
        if (e.button() == Qt.LeftButton and
                self._ellipse_rect().contains(QPointF(e.pos()))):
            self._trigger()

    def _ellipse_rect(self):
        return QRectF(
            8, 6,
            self.width() - 16,
            self.height() - 12,
        )

    def _trigger(self):
        """Execute the action and pop a BonusBubble with explicit deltas.
        Compute deltas from before/after state so feedback is always shown,
        even if the pet was sleeping (we wake it first)."""
        pet = self.pet
        _dependency("progression").ensure_progression(pet.state)
        if self.action_name == "dig_reward":
            pet._interactive_bubble = None
            self.close()
            pet.claim_dig_reward()
            return
        before = dict(pet.state)
        before_xp_earned = pet.state["records"]["xp_earned"]
        before_affection_earned = pet.state["records"]["affection_earned"]
        before_affection_level = int(
            pet.state.get("affection_level", 1)
        )
        before_level = int(pet.state.get("level", 1))
        acted = True
        # wake the pet if sleeping, so feed/play actually take effect
        if pet.state.get("sleeping") and self.action_name in ("feed", "play"):
            pet.state["sleeping"] = False
            pet.state["sleep_mode"] = None
            pet._auto_sleep_phase = None
            pet._auto_sleep_target_x = None
            pet._auto_sleep_snooze_until = time.time() + 60.0
            pet.refresh_pose_from_state()
        if self.action_name == "feed":
            pet.feed(grant_xp=False)
        elif self.action_name == "play":
            play_cost = _dependency("progression").upgrade_effects(
                pet.state
            )["play_energy_cost"]
            if pet.state["energy"] < 15 and play_cost > 0:
                pet.state["mood"] = min(100, pet.state["mood"] + 6)
                pet.say("没力气…摸摸我也行", 1500)
                acted = False
            else:
                pet.play(grant_xp=False)
        elif self.action_name == "sleep":
            pet.state["energy"] = min(100, pet.state["energy"] + 30)
            _dependency("progression").grant_interaction_affection(
                pet.state, "rest_bubble"
            )
            pet.say("小憩一下 💤", 1800)
            pet.refresh_pose_from_state()
            _dependency("save_state")(pet.state)

        # compute deltas from before vs after state
        deltas = []
        labels = {"hunger":"饱腹", "mood":"心情", "energy":"精力"}
        for k, name in labels.items():
            d = pet.state.get(k, 0) - before.get(k, 0)
            if abs(d) >= 0.5:
                sign = "+" if d > 0 else ""
                deltas.append(f"{name}{sign}{int(round(d))}")

        xp_gain = max(
            0, pet.state["records"]["xp_earned"] - before_xp_earned
        )
        leveled_up = int(pet.state.get("level", 1)) > before_level

        parts = list(deltas)
        affection_gain = max(
            0,
            pet.state["records"]["affection_earned"]
            - before_affection_earned,
        )
        if affection_gain:
            parts.append(f"好感+{affection_gain}")
        if (
            int(pet.state.get("affection_level", 1))
            > before_affection_level
        ):
            parts.append(
                f"好感Lv.{pet.state.get('affection_level', 1)}"
            )
        if xp_gain:
            parts.append(f"EXP+{xp_gain}")
        if leveled_up:
            parts.append(f"LVUP→{pet.state.get('level',1)}")
        bonus_text = "  ".join(parts) if parts else "✨"

        # ALWAYS pop the floating BonusBubble (guaranteed visible)
        bonus_x, bonus_y = pet_interface_bonus_origin(pet, -10)
        color = "#ffcc00" if leveled_up else self.color
        try:
            bb = _dependency("BonusBubble")(bonus_text, bonus_x, bonus_y, color)
            pet._last_bonus = bb  # keep ref so it isn't GC'd
        except Exception as e:
            print("BonusBubble fail:", e)

        if leveled_up:
            lvl = pet.state.get("level", 1)
            def _celebrate():
                celebrate_x, celebrate_y = pet_interface_bonus_origin(
                    pet, -30
                )
                try:
                    _dependency("BonusBubble")(
                        f"🎉 Lv.{lvl}",
                        celebrate_x,
                        celebrate_y,
                        "#ffcc00",
                    )
                except Exception: pass
                pet.say(f"升级啦！Lv.{lvl} 🎉", 2500)
            QTimer.singleShot(700, _celebrate)

        # release the slot so a new interactive bubble can spawn later
        pet._interactive_bubble = None
        self.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = (
            1.0
            + math.sin(self._pulse) * 0.008
            + (0.022 if self._hovered else 0.0)
        )
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        p.scale(scale, scale)
        p.translate(-cx, -cy)

        r = self._ellipse_rect()
        c = QColor(self.color)

        if self.action_name == "dig_reward":
            glow = QColor(c)
            glow.setAlpha(int(30 + math.sin(self._pulse) * 8))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(r.adjusted(-2, -2, 2, 2))
            p.setBrush(QColor(111, 66, 48, 32))
            p.drawEllipse(r.translated(1.5, 3))
            grad = QLinearGradient(r.topLeft(), r.bottomRight())
            grad.setColorAt(0.0, QColor("#fffaf0"))
            grad.setColorAt(0.55, QColor("#ffe6bd"))
            grad.setColorAt(1.0, QColor("#f6bd8d"))
            p.setBrush(grad)
            p.setPen(QPen(QColor("#e59b73"), 1.5))
            p.drawEllipse(r)
            # A tiny cream highlight keeps the badge soft instead of metallic.
            p.setBrush(QColor(255, 255, 255, 105))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(r.left() + 12, r.top() + 8, 24, 10))
            icon_center = QPointF(r.center().x(), r.top() + 27)
            self._draw_action_icon(p, icon_center, QColor("#a65f43"))
            p.setFont(pixel_font(9, QFont.Bold))
            p.setPen(QColor("#844e3b"))
            p.drawText(
                QRectF(r.left() + 7, r.center().y() + 4, r.width() - 14, 22),
                Qt.AlignCenter | Qt.TextSingleLine,
                "宝藏",
            )
            return

        glow = QColor(c)
        glow.setAlpha(int(28 + math.sin(self._pulse) * 8))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 25, 25)

        shadow = r.translated(2, 3)
        p.setBrush(QColor(91, 59, 44, 42))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(shadow, 24, 24)

        tail_y = r.center().y()
        if self._tail_on_left:
            tail = QPolygonF([
                QPointF(r.left() + 2, tail_y - 7),
                QPointF(2, tail_y),
                QPointF(r.left() + 2, tail_y + 7),
            ])
        else:
            tail = QPolygonF([
                QPointF(r.right() - 2, tail_y - 7),
                QPointF(self.width() - 2, tail_y),
                QPointF(r.right() - 2, tail_y + 7),
            ])
        p.setBrush(c.lighter(150))
        p.drawPolygon(tail)

        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, c.lighter(190))
        grad.setColorAt(0.48, c.lighter(165))
        grad.setColorAt(1.0, c.lighter(130))
        p.setBrush(grad)
        p.setPen(QPen(c.darker(112), 1.25))
        p.drawRoundedRect(r, 24, 24)

        gloss = QRectF(
            r.x() + 12, r.y() + 4,
            r.width() - 24, r.height() * 0.38,
        )
        gloss_grad = QLinearGradient(gloss.topLeft(), gloss.bottomLeft())
        gloss_grad.setColorAt(0.0, QColor(255, 255, 255, 125))
        gloss_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(gloss_grad)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(gloss, 16, 16)

        icon_center = QPointF(r.left() + 27, r.center().y())
        p.setBrush(QColor(255, 252, 246, 230))
        p.setPen(QPen(QColor(255, 255, 255, 190), 1))
        p.drawEllipse(icon_center, 17, 17)
        self._draw_action_icon(p, icon_center, c.darker(105))

        text_rect = QRectF(
            r.left() + 49, r.top(),
            r.width() - 57, r.height(),
        )
        p.setFont(self.font())
        p.setPen(QColor(92, 63, 52, 220))
        p.drawText(
            text_rect.translated(0, 1),
            Qt.AlignCenter | Qt.TextSingleLine,
            self.label,
        )
        p.setPen(QColor("#70483d"))
        p.drawText(
            text_rect,
            Qt.AlignCenter | Qt.TextSingleLine,
            self.label,
        )

    def _draw_action_icon(self, painter, center, color):
        painter.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        if self.action_name == "feed":
            bone = QRectF(
                center.x() - 7, center.y() - 3,
                14, 6,
            )
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bone, 3, 3)
            for dx in (-7, 7):
                painter.drawEllipse(
                    QPointF(center.x() + dx, center.y() - 4), 3.5, 3.5
                )
                painter.drawEllipse(
                    QPointF(center.x() + dx, center.y() + 4), 3.5, 3.5
                )
        elif self.action_name == "play":
            ball = QRectF(
                center.x() - 9, center.y() - 9,
                18, 18,
            )
            painter.drawEllipse(ball)
            painter.drawArc(ball.adjusted(4, -1, 4, 1), 80 * 16, 95 * 16)
            painter.drawArc(ball.adjusted(-4, -1, -4, 1), 260 * 16, 95 * 16)
        elif self.action_name == "dig_reward":
            # Rounded toy treasure chest with a heart-shaped latch.
            lid = QRectF(center.x() - 11, center.y() - 8, 22, 9)
            body = QRectF(center.x() - 12, center.y() - 1, 24, 13)
            painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(QColor("#f6a96f"))
            painter.drawRoundedRect(lid, 5, 5)
            painter.setBrush(QColor("#ef8d64"))
            painter.drawRoundedRect(body, 4, 4)
            painter.setPen(QPen(QColor("#ffe6a8"), 2.2))
            painter.drawLine(
                QPointF(body.left() + 2, body.top() + 4),
                QPointF(body.right() - 2, body.top() + 4),
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#fff0a9"))
            painter.drawEllipse(QPointF(center.x(), center.y() + 4), 3, 3)
            # Two asymmetric sparkles make the icon feel lively and handmade.
            painter.setPen(QPen(QColor("#e59b73"), 1.5, Qt.SolidLine, Qt.RoundCap))
            for sparkle, radius in (
                (QPointF(center.x() - 16, center.y() - 8), 3.0),
                (QPointF(center.x() + 16, center.y() - 4), 2.4),
            ):
                painter.drawLine(
                    QPointF(sparkle.x() - radius, sparkle.y()),
                    QPointF(sparkle.x() + radius, sparkle.y()),
                )
                painter.drawLine(
                    QPointF(sparkle.x(), sparkle.y() - radius),
                    QPointF(sparkle.x(), sparkle.y() + radius),
                )
        else:
            painter.setFont(pixel_font(14, QFont.Bold))
            painter.drawText(
                QRectF(
                    center.x() - 14, center.y() - 14,
                    28, 28,
                ),
                Qt.AlignCenter,
                "Z",
            )

    def enterEvent(self, e):
        self._hovered = True
        self.setCursor(Qt.PointingHandCursor)
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        super().leaveEvent(e)


def _esc(text):
    """HTML-escape user content for safe bubble rendering."""
    return (text.replace("&","&amp;").replace("<","&lt;")
                .replace(">","&gt;").replace("\n","<br>"))


class SpeechBubble(QWidget):
    """A complete, queued speech bubble that wraps long messages."""
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.text = ""
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFont(pixel_font(11, QFont.Bold))
        self._pending_messages = []
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._show_next_or_hide)

    def show_text(self, text, ms):
        text = " ".join(str(text).replace("\r", "\n").splitlines()).strip()
        duration = max(1, int(ms))
        if not text:
            return
        # Never cut off a message that is already being read. Interactions,
        # autonomous reminders and level-up lines can arrive in the same event
        # loop, so subsequent lines wait their turn instead of resizing and
        # repainting the visible translucent window underneath the reader.
        if self.isVisible() and self._hide_timer.isActive():
            if text == self.text:
                self._hide_timer.start(
                    max(duration, self._hide_timer.remainingTime())
                )
            elif not self._pending_messages or (
                self._pending_messages[-1][0] != text
            ):
                self._pending_messages.append((text, duration))
            return
        self._display_text(text, duration)

    def _display_text(self, text, duration):
        self._hide_timer.stop()
        screen = self._available_screen_rect()
        fm = self.fontMetrics()
        padding_x = 18
        max_bubble_width = max(126, min(520, screen.width() - 8))
        max_text_width = max(80, max_bubble_width - padding_x * 2 - 10)
        natural_width = max(1, fm.horizontalAdvance(text) + 2)
        text_width = min(natural_width, max_text_width)
        text_bounds = fm.boundingRect(
            QRect(0, 0, int(text_width), 10000),
            Qt.AlignCenter | Qt.TextWordWrap,
            text,
        )
        self.text = text
        width = text_width + padding_x * 2 + 10
        height = max(fm.height(), text_bounds.height()) + 28
        # Hiding first forces Windows to allocate a correctly sized backing
        # surface for this translucent top-level window. Resizing it while
        # visible can leave the newly exposed right/bottom area unpainted.
        if self.isVisible():
            self.hide()
        self.setGeometry(self._bubble_geometry(width, height))
        self.show()
        self.raise_()
        self.repaint()
        self._hide_timer.start(duration)

    def _show_next_or_hide(self):
        if not pet_interface_anchor_visible(self.pet):
            self.clear_messages()
            return
        if self._pending_messages:
            text, duration = self._pending_messages.pop(0)
            # A brand-new top-level widget gets a fresh native translucent
            # surface. Reusing a previously shown window can leave its right
            # side permanently clipped on Windows after the width changes.
            replacement = SpeechBubble(self.pet)
            replacement._pending_messages = self._pending_messages
            self._pending_messages = []
            if getattr(self.pet, "_speech_bubble", None) is self:
                self.pet._speech_bubble = replacement
            self._hide_timer.stop()
            self.close()
            replacement._display_text(text, duration)
            return
        self.hide()

    def clear_messages(self):
        self._hide_timer.stop()
        self._pending_messages.clear()
        self.hide()

    def follow_pet(self):
        if not pet_interface_anchor_visible(self.pet):
            self.clear_messages()
            return
        rect = self._bubble_geometry(self.width(), self.height())
        move_window_if_needed(self, rect.x(), rect.y())

    def _bubble_geometry(self, width, height):
        """Return one complete on-screen geometry for an atomic update."""
        g = pet_interface_anchor_rect(self.pet)
        screen = pet_interface_screen_rect(self.pet)
        x = g.center().x() - width // 2
        # Keep the tail close to the dog's head even when long text wraps.
        y = g.top() + 3 - max(0, height - 56)
        if SpeechBubble._pet_uses_home_theme(self.pet):
            y -= 72
        x = max(screen.left() + 4, min(x, screen.right() - width - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - height - 4))
        return QRect(int(x), int(y), int(width), int(height))

    def _tail_x(self):
        """Return a local tail position that follows the current pet head."""
        anchor_x = pet_interface_anchor_rect(self.pet).center().x()
        return max(16.0, min(self.width() - 16.0, anchor_x - self.x()))

    def _uses_home_theme(self):
        """Return whether the bubble is anchored to the in-home pet."""

        return self._pet_uses_home_theme(self.pet)

    @staticmethod
    def _pet_uses_home_theme(pet):
        """Return whether a pet-like host currently exposes its home scene."""

        active_home = getattr(pet, "_active_home_interface", None)
        if not callable(active_home):
            return False
        try:
            return active_home() is not None
        except RuntimeError:
            return False

    def _available_screen_rect(self):
        """Resolve the pet's screen without using its one-second movement cache."""
        return pet_interface_screen_rect(self.pet)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Explicitly clear the complete translucent surface.  This matters
        # when a visible bubble changes from short to long several times in
        # quick succession on Windows.
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        body = QRectF(4, 3, self.width() - 8, self.height() - 12)

        home_theme = self._uses_home_theme()
        radius = 15 if home_theme else 13
        shadow = QColor(105, 72, 52, 30) if home_theme else QColor(0, 0, 0, 38)
        gradient_start = QColor("#fff8ee") if home_theme else QColor(255, 250, 232)
        gradient_end = QColor("#f8dec5") if home_theme else QColor(255, 236, 180)
        border = QColor("#d79b7b") if home_theme else QColor(230, 180, 80)
        tail = QColor("#f9e2cb") if home_theme else QColor(255, 241, 198)
        text_color = QColor("#694534") if home_theme else QColor(80, 50, 20)

        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        p.drawRoundedRect(body.adjusted(2, 3, 2, 3), radius, radius)

        grad = QLinearGradient(body.topLeft(), body.bottomRight())
        grad.setColorAt(0.0, gradient_start)
        grad.setColorAt(1.0, gradient_end)
        p.setBrush(grad)
        p.setPen(QPen(border, 1.2))
        p.drawRoundedRect(body, radius, radius)

        tail_x = self._tail_x()
        p.setBrush(tail)
        p.drawPolygon([
            QPointF(tail_x - 6, body.bottom() - 1),
            QPointF(tail_x + 6, body.bottom() - 1),
            QPointF(tail_x, body.bottom() + 8),
        ])

        p.setFont(self.font())
        p.setPen(text_color)
        p.drawText(body.adjusted(18, 0, -18, 0),
                   Qt.AlignCenter | Qt.TextWordWrap,
                   self.text)
