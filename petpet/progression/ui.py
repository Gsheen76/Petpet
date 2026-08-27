"""Warm Qt panels for records, achievements, Pet coins, and upgrades."""

from __future__ import annotations

import os
import time
import copy

from PyQt5.QtCore import Qt, QPoint, QRect, QRectF, QSize, QTimer
from PyQt5.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWIDGETSIZE_MAX,
)

from petpet.progression import core as progression
from petpet.ui import decorations as decoration_renderer
from petpet.app.paths import DECORATIONS_DIR, OUTFITS_DIR, POSES_DIR, SHOP_UI_DIR
from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app.pets import (
    load_pet_registry,
    pet_asset_path,
    pet_avatar_path,
    pet_definition,
)
from petpet.home.rendering import HOME_FURNITURE_PATHS, render_home_status_card


def _shop_asset(name):
    return os.path.join(SHOP_UI_DIR, name)


def _shop_pixmap(name, height):
    pixmap = QPixmap(_shop_asset(name))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaledToHeight(
        height, Qt.SmoothTransformation
    )


_CROPPED_PIXMAP_CACHE = {}


def _alpha_bounds(img):
    """Exact opaque bounding box via numpy; None when fully transparent."""
    try:
        import numpy as np
    except ImportError:
        return None
    stride = img.bytesPerLine() // 4
    raw = img.constBits().asarray(img.bytesPerLine() * img.height())
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(
        img.height(), stride, 4
    )[:, :img.width(), 3]
    mask = arr > 8
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0:
        return None
    return (
        int(cols[0]), int(rows[0]),
        int(cols[-1]), int(rows[-1]),
    )


def _shop_pixmap_cropped(name, height):
    """Asset cropped to its opaque bounding box, then scaled to height."""
    key = (name, int(height))
    cached = _CROPPED_PIXMAP_CACHE.get(key)
    if cached is not None:
        return cached
    pixmap = QPixmap(_shop_asset(name))
    if pixmap.isNull():
        _CROPPED_PIXMAP_CACHE[key] = pixmap
        return pixmap
    img = pixmap.toImage()
    bounds = _alpha_bounds(img)
    if bounds is None:
        result = pixmap
    else:
        left, top, right, bottom = bounds
        result = pixmap.copy(QRect(
            left, top, right - left + 1, bottom - top + 1,
        )).scaledToHeight(int(height), Qt.SmoothTransformation)
    _CROPPED_PIXMAP_CACHE[key] = result
    return result


def _status_badge_label(text, kind):
    """Baked 使用中/已拥有 pill when available, styled text otherwise."""
    label = PreservedTextLabel(text)
    if kind == "active":
        pixmap = _shop_pixmap_cropped("status_in_use.png", 47)
    elif kind == "owned":
        pixmap = _shop_pixmap_cropped("status_owned.png", 47)
    else:
        pixmap = QPixmap()
    if not pixmap.isNull():
        label.setPixmap(pixmap)
        label.setContentsMargins(4, 2, 0, 2)
        label.setStyleSheet(
            "background: transparent; border: 0; border-image: none;"
        )
    elif kind == "active":
        label.setProperty("petStatusRole", "active")
    elif kind == "owned":
        label.setProperty("petStatusRole", "owned")
    else:
        label.setProperty("levelBadge", True)
    return label


SHOP_THEME_STYLE = """
    QWidget {
        font-size: 21px;
        font-weight: 600;
    }
    QLabel[cardTitle="true"] {
        font-size: 24px;
    }
    QFrame#tabBar {
        background: transparent;
        border: 0;
        border-image: url("%(tab_bar)s");
    }
    QPushButton#tabButton {
        background: transparent;
        color: #8a5a3c;
        border: 0;
        border-radius: 16px;
        padding: 12px 18px;
        font-size: 21px;
    }
    QPushButton#tabButton:hover { color: #7a4a34; }
    QPushButton#tabButton:checked {
        background: transparent;
        border-image: url("%(active_tab)s") 20 32 20 32 stretch;
        color: #ffffff;
    }
    QFrame#petTabBar {
        background: #f7e8d8;
        border: 1px solid #eed3ba;
        border-radius: 22px;
    }
    QPushButton#petTabButton {
        background: transparent;
        color: #9c6b58;
        border: 0;
        border-radius: 23px;
        padding: 6px 3px;
        font-size: 19px;
        font-weight: 800;
    }
    QPushButton#petTabButton:hover {
        background: #ffece1;
        color: #8c5948;
    }
    QPushButton#petTabButton:checked {
        background: #f28f76;
        color: #ffffff;
    }
    QFrame#filterBar {
        background: #f7e8d8;
        border: 1px solid #eed3ba;
        border-radius: 16px;
    }
    QPushButton#filterTabButton {
        background: transparent;
        color: #9c6b58;
        border: 0;
        border-radius: 12px;
        padding: 7px 3px;
        font-size: 14px;
        font-weight: 800;
    }
    QPushButton#filterTabButton:hover {
        background: #ffece1;
        color: #8c5948;
    }
    QPushButton#filterTabButton:checked {
        background: #f28f76;
        color: #ffffff;
    }
    QPushButton[coralPill="true"] {
        background: transparent;
        border: 0;
        border-image: url("%(active_tab)s") 20 32 20 32 stretch;
        color: #ffffff;
        padding: 0;
        min-width: 110px;
        max-width: 110px;
        min-height: 48px;
        max-height: 48px;
        font-size: 19px;
        font-weight: 800;
    }
    QPushButton[coralPill="true"]:disabled {
        background: #ead8ca;
        border-image: none;
        color: #a98b7b;
    }
    QPushButton#closeButton {
        background: transparent;
        border: 0;
        border-image: url("%(close_button)s");
    }
    QPushButton#closeButton:hover {
        background: transparent;
    }
    QPushButton[switchPill="true"] {
        background: transparent;
        border: 0;
        border-image: url("%(switch_button)s");
        color: transparent;
        padding: 8px 16px;
    }
    QLabel[priceTagRole="gift"] {
        background: transparent;
        border: 0;
    }
    QLabel[priceTagRole="normal"] {
        background: transparent;
        border: 0;
        border-image: url("%(price_bg)s");
        color: #d29a38;
        font-size: 16px;
        font-weight: 600;
        padding: 0 8px 0 40px;
    }
    QFrame[shopCard="true"] {
        background: #fff9ee;
        border: 1px solid #f0d8ba;
        border-radius: 20px;
    }
    QFrame#dataCard, QFrame#achievementCard, QFrame#upgradeCard,
    QFrame#decorationCard,
    QFrame#placeholderCard, QFrame[placeholderCard="true"] {
        background: #fff9ee;
        border: 1px solid #f0d8ba;
        border-radius: 20px;
    }
    QFrame#heroCard {
        background: #fff3e2;
        border: 1px solid #f0d8ba;
    }
    QLabel[petStatusRole="active"] {
        color: #d2604e;
        background: #ffe3dc;
        border: 1px solid #f6bcae;
    }
    QLabel[petStatusRole="owned"] {
        color: #8a5a3c;
        background: #f7e7d2;
        border: 1px solid #e8d0b4;
    }
""" % {
    "tab_bar": _shop_asset("tab_bar_bg.png").replace("\\", "/"),
    "active_tab": _shop_asset("active_tab_bg.png").replace("\\", "/"),
    "close_button": _shop_asset("close_button.png").replace("\\", "/"),
    "switch_button": _shop_asset("switch_pet_button.png").replace("\\", "/"),
    "price_bg": _shop_asset("price_bg.png").replace("\\", "/"),
}


PANEL_STYLE = """
    QWidget {
        background: transparent;
        color: #65483b;
        font-family: '%(app_font)s', 'Microsoft YaHei', sans-serif;
        font-size: 20px;
    }
    QWidget#cozyProgressWindow {
        background: #fff8ec;
        border: 1px solid #e7c4ad;
        border-radius: 22px;
    }
    QLabel#panelTitle {
        color: #754b3a;
        font-size: 33px;
        font-weight: 900;
    }
    QLabel#panelSubtitle {
        color: #a27a68;
        font-size: 19px;
    }
    QLabel#coinPill {
        background: #fff0c8;
        color: #a66a26;
        border: 1px solid #efc979;
        border-radius: 12px;
        padding: 3px 7px;
        font-size: 15px;
        font-weight: 900;
    }
    QLabel#sectionTitle {
        color: #8b5744;
        font-size: 28px;
        font-weight: 900;
        padding: 5px 2px;
    }
    QLabel#muted, QLabel[mutedText="true"] {
        color: #a98270;
        font-size: 18px;
    }
    QLabel#status {
        color: #c96f59;
        font-size: 17px;
        font-weight: 800;
        padding: 4px;
    }
    QFrame#heroCard {
        background: #fff1df;
        border: 1px solid #efcfad;
        border-radius: 18px;
    }
    QFrame#dataCard, QFrame#achievementCard, QFrame#upgradeCard,
    QFrame#decorationCard,
    QFrame#placeholderCard, QFrame[shopCard="true"],
    QFrame[placeholderCard="true"] {
        background: #fffdf8;
        border: 1px solid #edd2bd;
        border-radius: 16px;
    }
    QLabel#cardTitle, QLabel[cardTitle="true"] {
        color: #7a5040;
        font-size: 22px;
        font-weight: 900;
    }
    QLabel#cardValue {
        color: #ef886f;
        font-size: 27px;
        font-weight: 900;
    }
    QLabel#reward, QLabel[rewardLabel="true"] {
        background: #fff1c9;
        color: #a96e27;
        border-radius: 11px;
        padding: 4px 9px;
        font-size: 18px;
        font-weight: 800;
    }
    QLabel#levelBadge, QLabel[levelBadge="true"] {
        background: #ffe4d8;
        color: #a8604e;
        border-radius: 12px;
        padding: 5px 10px;
        font-size: 18px;
        font-weight: 900;
    }
    QLabel[discountBubble="true"] {
        background: #ffe4d8;
        color: #c85f4b;
        border: 1px solid #f2bca9;
        border-radius: 10px;
        padding: 4px 9px;
        font-size: 14px;
        font-weight: 900;
    }
    QLabel[priceRole="original"] {
        color: #7a5040;
        font-size: 18px;
    }
    QLabel[priceRole="discounted"] {
        color: #7a5040;
        font-size: 18px;
        font-weight: 400;
    }
    QLabel#popupTitle {
        color: #a8604e;
        font-size: 27px;
        font-weight: 900;
        background: transparent;
        border: 0;
        border-image: none;
    }
    QLabel#popupDetail {
        color: #8a5a3c;
        font-size: 20px;
        font-weight: 600;
        background: transparent;
        border: 0;
        border-image: none;
    }
    QPushButton {
        background: #f28f76;
        color: white;
        border: 0;
        border-radius: 12px;
        padding: 9px 9px;
        font-size: 18px;
        font-weight: 800;
    }
    QPushButton:hover { background: #f5a08a; }
    QPushButton:pressed { background: #de7a64; }
    QPushButton:disabled {
        background: #ead8ca;
        color: #a98b7b;
    }
    QPushButton#closeButton {
        background: #ffe5dc;
        color: #a96254;
        border: 1px solid #efc6b8;
        border-radius: 17px;
        padding: 0;
        font-size: 27px;
        font-weight: 700;
    }
    QPushButton#closeButton:hover {
        background: #f49a84;
        color: white;
    }
    QPushButton#softButton {
        background: #fff0e4;
        color: #af6955;
        border: 1px solid #ecc7b3;
    }
    QPushButton#softButton:hover { background: #ffe2d4; }
    QFrame#tabBar {
        background: #f4e2d2;
        border: 1px solid #e9c9b1;
        border-radius: 18px;
    }
    QPushButton#tabButton {
        background: transparent;
        color: #9c6b58;
        border: 0;
        border-radius: 14px;
        padding: 10px 24px;
        font-size: 19px;
        font-weight: 900;
    }
    QPushButton#tabButton:hover {
        background: #ffece1;
        color: #8c5948;
    }
    QPushButton#tabButton:checked {
        background: #f28f76;
        color: #ffffff;
    }
    QFrame#categoryTabBar {
        background: #fff7eb;
        border: 1px solid #edcfb8;
        border-radius: 15px;
    }
    QFrame[outfitPetSelector="true"] {
        background: #f4e2d2;
        border: 1px solid #e9c9b1;
        border-radius: 18px;
    }
    QPushButton[outfitPetTab="true"] {
        background: transparent;
        color: #9c6b58;
        border: 0;
        border-radius: 14px;
        padding: 9px 22px;
        min-width: 76px;
        font-size: 19px;
        font-weight: 900;
    }
    QPushButton[outfitPetTab="true"]:hover {
        background: #ffece1;
        color: #8c5948;
    }
    QPushButton[outfitPetTab="true"]:checked {
        background: #f28f76;
        color: #ffffff;
    }
    QPushButton#categoryTabButton {
        background: transparent;
        color: #966451;
        border: 0;
        border-radius: 11px;
        padding: 9px 22px;
        font-size: 19px;
        font-weight: 900;
    }
    QPushButton#categoryTabButton:hover {
        background: #fff0df;
    }
    QPushButton#categoryTabButton:checked {
        background: #f7c86e;
        color: #704532;
    }
    QLabel#upgradeSummary {
        color: #8f6b5c;
        font-size: 18px;
        padding: 2px 0 5px 0;
    }
    QLabel#effectCurrent, QLabel[effectCurrent="true"] {
        background: #f8eee5;
        color: #6e4b3e;
        border: 1px solid #ead1bf;
        border-radius: 12px;
        padding: 10px 13px;
        font-size: 19px;
        font-weight: 700;
    }
    QLabel#effectNext {
        background: #fff4cf;
        color: #8a5b22;
        border: 1px solid #efcf79;
        border-radius: 12px;
        padding: 10px 13px;
        font-size: 19px;
        font-weight: 800;
    }
    QProgressBar {
        background: #f2e3d6;
        border: 0;
        border-radius: 7px;
        height: 14px;
        color: transparent;
    }
    QProgressBar::chunk {
        background: #f3a285;
        border-radius: 7px;
    }
    QScrollArea, QScrollArea > QWidget > QWidget {
        background: transparent;
        border: 0;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 11px;
        margin: 4px 0;
    }
    QScrollBar::handle:vertical {
        background: #e8bfa8;
        border-radius: 5px;
        min-height: 38px;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical { height: 0; }
""" % {"app_font": APP_FONT_FAMILY}

PANEL_STYLE += """
    QLabel[priceTagRole="normal"],
    QLabel[priceTagRole="sale"],
    QLabel[priceTagRole="discount"],
    QLabel[priceTagRole="gift"] {
        border-radius: 11px;
        padding: 0;
    }
    QLabel[priceTagRole="normal"] {
        background: #fff8e8;
        border: 1px solid #e8c789;
        color: #7a5040;
        font-size: 16px;
    }
    QLabel[priceTagRole="sale"] {
        background: #fff0e8;
        border: 1px solid #f19a7b;
        color: #a34b3c;
        font-size: 17px;
        font-weight: 800;
    }
    QLabel[priceTagRole="discount"] {
        background: #ffe5dd;
        border: 1px solid #ef9279;
        color: #a74439;
        font-size: 14px;
        font-weight: 800;
    }
    QLabel[priceTagRole="gift"] {
        background: #fff2c9;
        border: 1px solid #e9c573;
        color: #966821;
        font-size: 16px;
        font-weight: 800;
    }
    QFrame[shopCard="true"] {
        background: #fffdf6;
        border: 2px dashed #e9c8a6;
        border-radius: 20px;
    }
    QFrame#tabBar {
        background: #f9ead6;
        border: 1px solid #efd3ba;
        border-radius: 20px;
    }
"""


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        widget = item.widget()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.deleteLater()


def _coin_balance(state):
    player = state.get("player")
    return (
        player.get("pet_coins", 0)
        if isinstance(player, dict)
        else state.get("pet_coins", 0)
    )


class RoundedPixmapLabel(QLabel):
    """QLabel whose pixmap is clipped to rounded corners."""

    def __init__(self, radius=22):
        super().__init__()
        self._radius = radius

    def paintEvent(self, event):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rounded = QPainterPath()
        rounded.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        painter.setClipPath(rounded)
        painter.drawPixmap(
            0, 0, pixmap.width(), pixmap.height(), pixmap
        )
        painter.end()


class PreservedTextLabel(QLabel):
    """QLabel that keeps text() readable while showing a baked asset."""

    def __init__(self, text=""):
        super().__init__()
        self._stored_text = text
        QLabel.setText(self, text)

    def setText(self, text):
        self._stored_text = text
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            QLabel.setText(self, text)

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)

    def text(self):
        return self._stored_text


class FeedbackButton(QPushButton):
    """Push button with hover brightening and pressed tint feedback.

    Asset-backed pills (border-image QSS) hide plain background swaps, so
    the feedback is painted as a translucent overlay above the skin.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isEnabled():
            return
        if self.isDown():
            tint = QColor(150, 60, 40, 70)
        elif self.underMouse():
            tint = QColor(255, 255, 255, 55)
        else:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()).adjusted(2, 2, -2, -2), 16, 16
        )
        painter.fillPath(path, tint)
        painter.end()


class CoinPillLabel(QLabel):
    """Compact Pet币 counter painted on the clean price_bg asset."""

    def __init__(self):
        super().__init__()
        self._asset = QPixmap(_shop_asset("price_bg.png"))
        self._balance = 0
        if not self._asset.isNull():
            self._asset = self._asset.scaledToHeight(
                46, Qt.SmoothTransformation
            )
            self.setFixedSize(self._asset.size())
        else:
            self.setFixedSize(158, 44)
        # Suppress themed background layers behind the custom painting.
        self.setStyleSheet(
            "background: transparent; border: 0; border-image: none;"
        )

    def set_balance(self, value):
        self._balance = int(value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._asset.isNull():
            painter.drawPixmap(self.rect(), self._asset)
        font = QFont(APP_FONT_FAMILY)
        font.setPixelSize(22)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#d29a38"), 1.0))
        rect = QRect(
            int(self.width() * 0.26), 0,
            int(self.width() * 0.68), self.height(),
        )
        painter.drawText(rect, Qt.AlignVCenter, f"Pet币 {self._balance}")
        painter.end()


class PurchasePopup(QDialog):
    """Cute shop-themed popup confirming a transaction."""

    def __init__(self, title, lines, parent=None):
        super().__init__(
            parent,
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(360, 250)

        sheet = QPixmap(_shop_asset("background.png"))
        rounded = QPixmap(self.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 22, 22)
        painter.setClipPath(path)
        if not sheet.isNull():
            crop_height = max(1, int(sheet.height() * 0.45))
            cropped = sheet.copy(
                0, sheet.height() - crop_height, sheet.width(), crop_height
            )
            scaled = cropped.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - scaled.width()) // 2,
                self.height() - scaled.height(),
                scaled,
            )
        painter.end()

        background = QLabel(self)
        background.setGeometry(self.rect())
        background.setPixmap(rounded)

        overlay = QLabel(self)
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet(
            "background: rgba(255, 247, 238, 196);"
            "border: 2px solid #f2c9a8;"
            "border-radius: 22px;"
        )
        overlay.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("popupTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addSpacing(18)
        for line in lines:
            detail = QLabel(line)
            detail.setObjectName("popupDetail")
            detail.setAlignment(Qt.AlignCenter)
            detail.setWordWrap(True)
            layout.addWidget(detail)
        layout.addStretch(1)
        button = FeedbackButton("好的")
        button.setProperty("coralPill", True)
        button.clicked.connect(self.accept)
        layout.addWidget(button, 0, Qt.AlignCenter)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        # Clicks landing on the translucent frame outside the rounded card
        # count as dismissing the dialog.
        if not self._card_path().contains(event.pos()):
            self.accept()
            return
        super().mousePressEvent(event)

    def _card_path(self):
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 22, 22)
        return path


class PriceTagLabel(QLabel):
    """Price tag painted from the frame asset with the price fitted inside."""

    TEXT_LEFT = 0.26
    TEXT_RIGHT = 0.94

    def __init__(self, text):
        super().__init__()
        self._stored_text = str(text)
        # Crop to the opaque bounding box so the visible pill — not the
        # transparent canvas — defines size and left alignment.
        self._asset = _shop_pixmap_cropped("price_frame.png", 44)
        if not self._asset.isNull():
            self.setFixedSize(self._asset.size())
        else:
            self.setFixedSize(180, 52)
        self.setContentsMargins(12, 5, 12, 5)
        # The themed priceTagRole QSS paints a background/border-image box
        # behind the custom painting; suppress every painted layer.
        self.setStyleSheet(
            "background: transparent; border: 0; border-image: none;"
        )

    def text(self):
        return self._stored_text

    def setText(self, text):
        self._stored_text = str(text)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._asset.isNull():
            painter.drawPixmap(self.rect(), self._asset)
        rect = QRect(
            int(self.width() * self.TEXT_LEFT), 0,
            int(self.width() * (self.TEXT_RIGHT - self.TEXT_LEFT)),
            self.height(),
        )
        font = QFont(APP_FONT_FAMILY)
        font.setBold(True)
        size = 22
        while size > 12:
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(
                self._stored_text
            ) <= rect.width():
                break
            size -= 1
        painter.setFont(font)
        painter.setPen(QPen(QColor("#a8742c"), 1.0))
        painter.drawText(rect, Qt.AlignCenter, self._stored_text)
        painter.end()


class CozyProgressWindow(QWidget):
    """Shared frameless shell with warm styling and draggable title bar."""

    def __init__(
        self, pet, title, subtitle, preferred_size, shop_theme=False,
        title_image=True,
    ):
        super().__init__()
        self.pet = pet
        self._drag_offset = None
        self.shop_theme = bool(shop_theme)
        self._background_pixmap = (
            QPixmap(_shop_asset("background.png"))
            if self.shop_theme else QPixmap()
        )
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # A translucent top-level window does not automatically paint its
        # stylesheet background on every Qt backend. StyledBackground makes
        # the warm cream base real instead of exposing the desktop beneath.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("cozyProgressWindow")
        style = PANEL_STYLE + (SHOP_THEME_STYLE if self.shop_theme else "")
        self.setStyleSheet(style)

        screen = QApplication.primaryScreen().availableGeometry()
        width = max(520, min(preferred_size[0], screen.width() - 60))
        height = max(560, min(preferred_size[1], screen.height() - 70))
        self.setFixedSize(width, height)

        root = QVBoxLayout(self)
        root.setContentsMargins(25, 18, 25, 20)
        root.setSpacing(9)
        self.root_layout = root
        if self.shop_theme:
            root.setContentsMargins(25, 18, 25, 0)

        title_bar = QFrame()
        title_bar.setCursor(Qt.ArrowCursor)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        if self.shop_theme and title_image:
            title_label = QLabel()
            title_label.setPixmap(_shop_pixmap("shop_title_icon.png", 76))
            title_label.setFixedSize(404, 76)
            title_label.setScaledContents(True)
        else:
            title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        if self.shop_theme:
            self.coin_label = CoinPillLabel()
        else:
            self.coin_label = QLabel()
            self.coin_label.setObjectName("coinPill")
        close_button = FeedbackButton("" if self.shop_theme else "×")
        close_button.setObjectName("closeButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setFixedSize(38, 38)
        close_button.clicked.connect(self.close)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        if self.coin_label is not None:
            title_row.addWidget(self.coin_label)
        title_row.addWidget(close_button)
        title_bar.mousePressEvent = self._title_bar_press
        title_bar.mouseMoveEvent = self._title_bar_move
        title_bar.mouseReleaseEvent = self._title_bar_release
        if self.shop_theme:
            title_bar.setFixedHeight(78)
        root.addWidget(title_bar)

        if not self.shop_theme:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("panelSubtitle")
            subtitle_label.setWordWrap(True)
            root.addWidget(subtitle_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(1, 5, 10, 5)
        self.content_layout.setSpacing(11)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.content)
        if self.shop_theme:
            # Fixed page body: scroll region ends 30px above window bottom.
            page_body = QWidget()
            body_layout = QVBoxLayout(page_body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(0)
            body_layout.addWidget(self.scroll, 1)
            self.status_label.setFixedHeight(30)
            body_layout.addWidget(self.status_label)
            root.addWidget(page_body, 1)
            self._page_header = QWidget()
            self._page_header_layout = QVBoxLayout(self._page_header)
            self._page_header_layout.setContentsMargins(0, 2, 0, 4)
            self._page_header_layout.setSpacing(3)
            root.insertWidget(1, self._page_header)
        else:
            root.addWidget(self.scroll, 1)
            # Absorbs leftover space when the scroll area is height-capped so
            # the fixed header and tab bar never shift between pages.
            root.addStretch(0)
            root.addWidget(self.status_label)

    def _title_bar_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def _title_bar_move(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def _title_bar_release(self, event):
        self._drag_offset = None
        event.accept()

    def paintEvent(self, event):
        """Paint a real warm base behind every child on translucent windows."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.shop_theme and not self._background_pixmap.isNull():
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            rounded = QPainterPath()
            rounded.addRoundedRect(QRectF(self.rect()), 24, 24)
            painter.setClipPath(rounded)
            painter.drawPixmap(
                self.rect(),
                self._background_pixmap.scaled(
                    self.size(),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                ),
            )
            painter.setClipping(False)
            return
        outer = self.rect().adjusted(1, 1, -2, -2)
        gradient = QLinearGradient(outer.topLeft(), outer.bottomRight())
        gradient.setColorAt(0.0, QColor("#fffaf1"))
        gradient.setColorAt(1.0, QColor("#fff0df"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#e7c4ad"), 1.4))
        painter.drawRoundedRect(outer, 22, 22)

    def _refresh_coin_label(self):
        if self.coin_label is None:
            return
        progression.ensure_progression(self.pet.state)
        balance = _coin_balance(self.pet.state)
        if isinstance(self.coin_label, CoinPillLabel):
            self.coin_label.set_balance(balance)
        else:
            self.coin_label.setText(f"Pet币 {balance}")

    def show_near_pet(self):
        self.refresh()
        # Panel pages open centred on the screen and always start from the
        # top of their content — no remembered drag position or scroll.
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )
        self.scroll.verticalScrollBar().setValue(0)
        self.show()
        self.raise_()
        self.activateWindow()

    def _add_page_header(self, *widgets):
        """Page title and intro stay fixed above the shared scroll region."""
        if not hasattr(self, "_page_header_layout"):
            for widget in widgets:
                self.content_layout.addWidget(widget)
            return
        _clear_layout(self._page_header_layout)
        for widget in widgets:
            self._page_header_layout.addWidget(widget)

    def refresh(self):
        raise NotImplementedError


class RecordsWindow(CozyProgressWindow):
    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        self.record_pet_id = None
        super().__init__(
            pet,
            "温馨记录",
            "每一次摸摸、饭饭和陪伴，都被认真记在这里。",
            (850, 960),
            shop_theme=True,
            title_image=False,
        )

    @staticmethod
    def _data_card(title, value, note=""):
        card = QFrame()
        card.setObjectName("dataCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 13, 17, 13)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        value_label = QLabel(str(value))
        value_label.setObjectName("cardValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        if note:
            note_label = QLabel(note)
            note_label.setObjectName("muted")
            layout.addWidget(note_label)
        return card

    def refresh(self):
        progression.ensure_progression(self.pet.state)
        self._refresh_coin_label()
        self.status_label.clear()
        _clear_layout(self.content_layout)
        state = self.pet.state
        records = state["records"]
        now = time.time()

        pets = state.get("pets") or {}
        if not isinstance(pets, dict) or not pets:
            pets = {}
        if self.record_pet_id is not None and self.record_pet_id not in pets:
            self.record_pet_id = None
        if self.record_pet_id is not None:
            # A specific pet tab: only that pet's own mirrored numbers.
            pet_records = progression.pet_interaction_records(
                state, self.record_pet_id
            )
            pet_state = pets.get(self.record_pet_id) or {}
            pet_name = str(
                pet_state.get("pet_name")
                or pet_definition(self.record_pet_id)["default_name"]
            )
            affection_level = pet_state.get(
                "affection_level", state.get("affection_level", 1)
            )
        else:
            # 总计 tab: the shared player-wide numbers.
            pet_records = {
                key: records[key] for key in progression.PET_RECORD_KEYS
            }
            pet_name = ""
            affection_level = state.get("affection_level", 1)

        if pets:
            self._add_page_header(self._build_pet_switch_bar(pets))

        if self.record_pet_id is not None:
            # Pet tabs only show what belongs to this pet; shared panels
            # (hero, growth, exploration) live exclusively in 总计.
            self._add_pet_interaction_section(pet_records)
            self.content_layout.addStretch(1)
            return

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QGridLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.setHorizontalSpacing(24)
        hero_layout.setVerticalSpacing(5)
        born = float(state.get("born", now) or now)
        total_time = progression.format_duration(now - born)
        active_time = progression.format_duration(records["active_seconds"])
        hero_layout.addWidget(self._hero_label("相识时长", total_time), 0, 0)
        hero_layout.addWidget(
            self._hero_label("桌面陪伴", active_time), 0, 1
        )
        hero_layout.addWidget(
            self._hero_label("当前等级", f"Lv.{state.get('level', 1)}"),
            0, 2,
        )
        hero_layout.addWidget(
            self._hero_label(
                "每分钟经验",
                f"+{progression.passive_xp_per_minute(state):.1f} EXP/min",
            ),
            1, 1,
        )
        hero_layout.addWidget(
            self._hero_label("历史获得", f"{records['coins_earned']} Pet币"),
            1, 2,
        )
        del affection_level  # per-pet stat, never shown in 总计
        self.content_layout.addWidget(hero)

        self._add_interaction_section(pet_records, pet_name)

        section = QLabel("🌿 成长足迹")
        section.setObjectName("sectionTitle")
        self.content_layout.addWidget(section)
        growth_host = QWidget()
        growth_grid = QGridLayout(growth_host)
        growth_grid.setContentsMargins(0, 0, 0, 0)
        growth_grid.setSpacing(10)
        growth_cards = [
            ("启动陪伴", records["app_sessions"], "打开 Pet陪它的次数"),
            ("累计经验", records["xp_earned"], "新系统启用后获得的经验"),
            ("升级次数", records["level_ups"], "新系统启用后的升级次数"),
            (
                "累计好感",
                records["affection_earned"],
                "互动和小游戏积累的好感",
            ),
            (
                "好感升级",
                records["affection_level_ups"],
                "好感等级提升的次数",
            ),
            ("消费 Pet币", records["coins_spent"], "用于成长强化的总额"),
            ("主动入睡", records["manual_sleeps"], "主人安排的睡眠"),
            ("自己入睡", records["auto_sleeps"], "精力不足时主动休息"),
        ]
        for index, item in enumerate(growth_cards):
            growth_grid.addWidget(
                self._data_card(*item), index // 2, index % 2
            )
        self.content_layout.addWidget(growth_host)
        section = QLabel("🎀 收藏与探索")
        section.setObjectName("sectionTitle")
        self.content_layout.addWidget(section)
        explore_host = QWidget()
        explore_grid = QGridLayout(explore_host)
        explore_grid.setContentsMargins(0, 0, 0, 0)
        explore_grid.setSpacing(10)
        explore_cards = [
            ("AI 回复", records["ai_replies"], "小狗认真回复消息的次数"),
            ("自主散步", records["autonomous_walks"], "自己在桌面散步的次数"),
            ("收集装扮", records["decorations_collected"], "已经拥有的装扮数量"),
            ("更换装扮", records["outfit_changes"], "穿上或收好装扮的次数"),
            ("购买强化", records["upgrades_purchased"], "累计完成的强化次数"),
            ("领取成就", records["achievements_claimed"], "已经领取奖励的成就"),
            ("小游戏局数", records["minigame_rounds"], "完成小游戏的累计局数"),
            ("游戏收入", records["coins_minigames"], "小游戏累计获得的Pet币"),
        ]
        for index, item in enumerate(explore_cards):
            explore_grid.addWidget(
                self._data_card(*item), index // 2, index % 2
            )
        self.content_layout.addWidget(explore_host)
        self.content_layout.addStretch(1)

    def _add_interaction_section(self, pet_records, pet_name):
        section = QLabel(
            f"🐾 我们和{pet_name}做过的事" if pet_name
            else "🐾 我们一起做过的事（总计）"
        )
        section.setObjectName("sectionTitle")
        self.content_layout.addWidget(section)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        cards = [
            ("♡ 抚摸", pet_records["pettings"], "轻轻摸过小狗的头"),
            ("◇ 喂食", pet_records["feedings"], "一起吃过的饭饭"),
            ("○ 玩耍", pet_records["play_sessions"], "开启过的玩耍时光"),
            ("☾ 睡觉", pet_records["sleep_sessions"], "进入过香甜梦乡"),
            ("🎾 接住小球", pet_records["fetch_catches"], "成功完成的飞扑接球"),
            ("💬 聊天", pet_records["chats_opened"], "认真发送过的聊天消息"),
            ("☀ 摇醒", pet_records["wake_shakes"], "被主人温柔摇醒"),
            ("✦ 总互动", pet_records["interactions_total"], "四种基础互动合计"),
        ]
        for index, item in enumerate(cards):
            grid.addWidget(self._data_card(*item), index // 2, index % 2)
        self.content_layout.addWidget(grid_host)

    def _add_pet_interaction_section(self, pet_records):
        pet_state = (
            self.pet.state.get("pets", {}).get(self.record_pet_id) or {}
        )
        pet_name = str(
            pet_state.get("pet_name")
            or pet_definition(self.record_pet_id)["default_name"]
        )
        self._add_interaction_section(pet_records, pet_name)

    def _build_pet_switch_bar(self, pets):
        bar = QFrame()
        bar.setObjectName("petTabBar")
        bar.setFixedHeight(58)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(6, 6, 6, 6)
        bar_layout.setSpacing(4)
        entries = [(None, "总计")]
        for pet_id, pet_state in pets.items():
            if isinstance(pet_state, dict):
                name = str(
                    pet_state.get("pet_name")
                    or pet_definition(pet_id)["default_name"]
                )
                entries.append((pet_id, name))
        for pet_id, name in entries:
            button = FeedbackButton(name)
            button.setObjectName("petTabButton")
            button.setCheckable(True)
            button.setChecked(self.record_pet_id == pet_id)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda _checked=False, selected=pet_id:
                self._set_record_pet(selected)
            )
            bar_layout.addWidget(button)
        return bar

    def _set_record_pet(self, pet_id):
        if pet_id == self.record_pet_id:
            return
        self.record_pet_id = pet_id
        self.scroll.verticalScrollBar().setValue(0)
        self.refresh()

    @staticmethod
    def _hero_label(title, value):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        value_label = QLabel(value)
        value_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return box


# Achievement id prefixes are consolidated into a handful of filter groups so
# the tab bar stays readable; unknown future prefixes fall into "other".
ACHIEVEMENT_FILTER_GROUPS = (
    ("all", "全部", None),
    ("interact", "互动",
     {"pet", "feed", "play", "sleep", "interaction", "catch", "wake"}),
    ("chat", "聊天", {"chat", "reply"}),
    ("games", "游戏", {"minigame", "coins", "stroll"}),
    ("dressup", "换装强化", {"collect", "outfit", "upgrade"}),
    ("growth", "成长", {"days", "level", "claim"}),
)
ACHIEVEMENT_OTHER_GROUP = ("other", "其它")


class AchievementsWindow(CozyProgressWindow):
    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        self.achievement_filter = "all"
        super().__init__(
            pet,
            "暖心成就",
            "亮起的成就可以领取 Pet币；每升一级也会有一份奖励。",
            (850, 960),
            shop_theme=True,
            title_image=False,
        )

    def refresh(self):
        progression.ensure_progression(self.pet.state)
        self._refresh_coin_label()
        _clear_layout(self.content_layout)
        items = progression.achievement_catalog(self.pet.state)
        claimable = [item for item in items if item["claimable"]]
        completed_count = sum(1 for item in items if item["completed"])
        claimed_count = sum(1 for item in items if item["claimed"])

        summary = QFrame()
        summary.setObjectName("heroCard")
        row = QHBoxLayout(summary)
        row.setContentsMargins(18, 13, 18, 13)
        info = QLabel(
            f"已领取 {claimed_count} 项  ·  "
            f"待领取 {len(claimable)} 项"
        )
        info.setObjectName("cardTitle")
        info.setText(
            f"已完成 {completed_count}/{len(items)}  ·  "
            f"已领取 {claimed_count} 项  ·  "
            f"待领取 {len(claimable)} 项"
        )
        claim_all = FeedbackButton(
            f"一键领取（{len(claimable)}）"
            if claimable else "暂无待领取奖励"
        )
        claim_all.setObjectName("softButton")
        claim_all.setEnabled(bool(claimable))
        claim_all.clicked.connect(self._claim_all)
        row.addWidget(info)
        row.addStretch(1)
        row.addWidget(claim_all)
        if hasattr(self, "_page_header_layout"):
            filter_bar = self._build_filter_bar(items)
            # _add_page_header clears the header first; adding widgets
            # directly would stack a new summary/bar on every refresh.
            self._add_page_header(summary, filter_bar)
        else:
            self.content_layout.addWidget(summary)

        if self.achievement_filter == "all":
            ordered = list(items)
        else:
            group = dict(
                (key, prefixes)
                for key, _label, prefixes in ACHIEVEMENT_FILTER_GROUPS
                if prefixes is not None
            ).get(self.achievement_filter, set())
            if group:
                ordered = [
                    item for item in items
                    if item["id"].split("_", 1)[0] in group
                ]
            else:
                known = {
                    prefix
                    for _k, _l, prefixes in ACHIEVEMENT_FILTER_GROUPS
                    if prefixes
                    for prefix in prefixes
                }
                ordered = [
                    item for item in items
                    if item["id"].split("_", 1)[0] not in known
                ]
        ordered = sorted(
            ordered,
            key=lambda item: (
                0 if item["claimable"] else 1,
                1 if item["claimed"] else 0,
                item["category"],
                item["target"],
            ),
        )
        for item in ordered:
            self.content_layout.addWidget(self._achievement_card(item))
        self.content_layout.addStretch(1)

    def _build_filter_bar(self, items):
        prefix_groups = {
            key: prefixes
            for key, _label, prefixes in ACHIEVEMENT_FILTER_GROUPS
            if prefixes is not None
        }
        known = {
            prefix
            for prefixes in prefix_groups.values()
            for prefix in prefixes
        }
        available = [
            (key, label)
            for key, label, prefixes in ACHIEVEMENT_FILTER_GROUPS
            if prefixes is None
            or any(
                item["id"].split("_", 1)[0] in prefixes
                for item in items
            )
        ]
        uncovered = [
            item for item in items
            if item["id"].split("_", 1)[0] not in known
        ]
        if uncovered:
            available.append(ACHIEVEMENT_OTHER_GROUP)
        bar = QFrame()
        # Adaptive warm panel: the shared four-slot tab_bar asset cannot
        # stretch to a different button count.
        bar.setObjectName("filterBar")
        bar.setFixedHeight(46)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 4, 4, 4)
        bar_layout.setSpacing(3)
        for prefix, label in available:
            button = FeedbackButton(label)
            button.setObjectName("filterTabButton")
            button.setCheckable(True)
            button.setChecked(self.achievement_filter == prefix)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda _checked=False, selected=prefix:
                self._set_achievement_filter(selected)
            )
            bar_layout.addWidget(button)
        return bar

    def _set_achievement_filter(self, prefix):
        if prefix == self.achievement_filter:
            return
        self.achievement_filter = prefix
        self.status_label.clear()
        self.scroll.verticalScrollBar().setValue(0)
        self.refresh()

    def _achievement_card(self, item):
        card = QFrame()
        card.setObjectName("achievementCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 13, 17, 13)
        layout.setSpacing(7)

        top = QHBoxLayout()
        title = QLabel(f"{item['category']} · {item['title']}")
        title.setObjectName("cardTitle")
        reward = QLabel(f"+{item['reward']} Pet币")
        reward.setObjectName("reward")
        button = FeedbackButton()
        button.setFixedWidth(92)
        if item["claimed"]:
            button.setText("已领取")
            button.setEnabled(False)
        elif item["claimable"]:
            button.setText("领取")
            button.clicked.connect(
                lambda _checked=False, achievement_id=item["id"]:
                self._claim(achievement_id)
            )
        else:
            button.setText("未完成")
            button.setEnabled(False)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(reward)
        top.addWidget(button)
        layout.addLayout(top)

        description = QLabel(item["description"])
        description.setObjectName("muted")
        layout.addWidget(description)

        progress = QProgressBar()
        progress.setRange(0, 1000)
        ratio = min(1.0, item["progress"] / item["target"])
        progress.setValue(int(round(ratio * 1000)))
        progress.setTextVisible(False)
        layout.addWidget(progress)
        shown = min(item["progress"], item["target"])
        if item["category"] == "陪伴":
            progress_text = f"{shown:.1f} / {int(item['target'])} 天"
        else:
            progress_text = (
                f"{int(shown)} / {int(item['target'])}"
            )
        progress_label = QLabel(progress_text)
        progress_label.setObjectName("muted")
        progress_label.setAlignment(Qt.AlignRight)
        layout.addWidget(progress_label)
        return card

    def _claim(self, achievement_id):
        result = progression.claim_achievement(
            self.pet.state, achievement_id
        )
        if result.get("ok"):
            self.save_callback(self.pet.state)
            self.status_label.setText(
                f"✓ {result['title']}：Pet币 +{result['reward']}"
            )
            self.pet.say(
                f"成就奖励领到啦！Pet币 +{result['reward']} ✨", 2200
            )
        else:
            self.status_label.setText(result.get("message", "暂时不能领取"))
        self.refresh()

    def _claim_all(self):
        result = progression.claim_all_achievements(self.pet.state)
        if result["count"]:
            self.save_callback(self.pet.state)
            self.pet.say(
                f"一口气领了 {result['count']} 个成就，"
                f"Pet币 +{result['reward']}！", 2600
            )
            message = (
                f"✓ 已领取 {result['count']} 项，Pet币 +{result['reward']}"
            )
        else:
            message = "现在还没有可以领取的成就。"
        self.refresh()
        self.status_label.setText(message)


class DecorationPreview(QWidget):
    """Large idle-pose preview whose selected decoration can be dragged."""

    SELECTION_COLOR = "#f2b705"

    def __init__(
        self,
        pet,
        decoration_id,
        on_drag_finished=None,
        preview_state=None,
        allow_drag=True,
    ):
        super().__init__()
        self.pet = pet
        self.decoration_id = decoration_id
        self.on_drag_finished = on_drag_finished
        self.preview_state = preview_state
        self.allow_drag = bool(allow_drag)
        self.base_pixmap = QPixmap(os.path.join(POSES_DIR, "idle.png"))
        self.decoration_pixmaps = (
            decoration_renderer.load_decoration_pixmaps()
        )
        self._dog_bounds = QRectF()
        self._selected_bounds = QRectF()
        self._last_drag_pos = None
        self.setMinimumHeight(370)
        self.setCursor(
            Qt.OpenHandCursor if self.allow_drag else Qt.ArrowCursor
        )

    def _state(self):
        return self.preview_state or self.pet.state

    def _preview_bounds(self):
        available_width = max(1.0, self.width() - 36.0)
        available_height = max(1.0, self.height() - 48.0)
        width = min(available_width, available_height * 190.0 / 160.0)
        height = width * 160.0 / 190.0
        return QRectF(
            (self.width() - width) / 2.0,
            16.0 + (available_height - height) / 2.0,
            width,
            height,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        card = QRectF(self.rect()).adjusted(1, 1, -2, -2)
        gradient = QLinearGradient(card.topLeft(), card.bottomRight())
        gradient.setColorAt(0.0, QColor("#fffdf8"))
        gradient.setColorAt(1.0, QColor("#f9e7d8"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#e9c9b1"), 1.4))
        painter.drawRoundedRect(card, 18, 18)

        self._dog_bounds = self._preview_bounds()
        dog_rect = decoration_renderer.fit_pixmap_rect(
            self.base_pixmap, self._dog_bounds
        )
        if not dog_rect.isEmpty():
            painter.drawPixmap(
                dog_rect,
                self.base_pixmap,
                QRectF(
                    0,
                    0,
                    self.base_pixmap.width(),
                    self.base_pixmap.height(),
                ),
            )
        geometries = decoration_renderer.draw_equipped_idle(
            painter,
            self._state(),
            self._dog_bounds,
            self.decoration_pixmaps,
            selected_id=(self.decoration_id if self.allow_drag else None),
        )
        self._selected_bounds = geometries.get(
            self.decoration_id, QRectF()
        )
        if self.allow_drag and not self._selected_bounds.isEmpty():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(
                QColor(self.SELECTION_COLOR), 3.0, Qt.DashLine
            ))
            painter.drawRoundedRect(
                self._selected_bounds.adjusted(-5, -5, 5, 5),
                8,
                8,
            )

        painter.setPen(QColor("#9b7565"))
        painter.drawText(
            QRectF(14, self.height() - 31, self.width() - 28, 22),
            Qt.AlignCenter,
            "按住装饰拖动位置" if self.allow_drag else "待机姿势试戴效果",
        )

    def mousePressEvent(self, event):
        if (
            self.allow_drag
            and
            event.button() == Qt.LeftButton
            and self._selected_bounds.adjusted(
                -10, -10, 10, 10
            ).contains(event.pos())
        ):
            self._last_drag_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._last_drag_pos is None
            or not (event.buttons() & Qt.LeftButton)
            or self._dog_bounds.isEmpty()
        ):
            super().mouseMoveEvent(event)
            return
        delta = event.pos() - self._last_drag_pos
        self._last_drag_pos = event.pos()
        current = progression.decoration_transform(
            self._state(), self.decoration_id
        )
        progression.set_decoration_transform(
            self._state(),
            self.decoration_id,
            x=current["x"] + delta.x() / self._dog_bounds.width(),
            y=current["y"] + delta.y() / self._dog_bounds.height(),
        )
        self.pet.update()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._last_drag_pos is not None:
            self._last_drag_pos = None
            self.setCursor(Qt.OpenHandCursor)
            if callable(self.on_drag_finished):
                self.on_drag_finished()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DecorationPreviewWindow(CozyProgressWindow):
    """Non-destructive try-on for decorations before purchase."""

    def __init__(self, pet, decoration_id, closed_callback=None):
        self.decoration_id = decoration_id
        self.closed_callback = closed_callback
        definition = progression.DECORATION_DEFINITIONS[decoration_id]
        self.preview_state = copy.deepcopy(pet.state)
        progression.ensure_progression(self.preview_state)
        if decoration_id not in self.preview_state["owned_decorations"]:
            self.preview_state["owned_decorations"].append(decoration_id)
        self.preview_state["equipped_decorations"][
            definition["category"]
        ] = decoration_id
        super().__init__(
            pet,
            f"👀 试戴 · {definition['name']}",
            "购买前预览，不会改变当前装扮。",
            (620, 610),
        )
        self.preview = DecorationPreview(
            pet,
            decoration_id,
            preview_state=self.preview_state,
            allow_drag=False,
        )
        self.content_layout.addWidget(self.preview)
        self.content_layout.addStretch(1)
        self.refresh()

    def refresh(self):
        self._refresh_coin_label()
        self.status_label.setText("仅供预览 · 购买后可自由微调")
        if hasattr(self, "preview"):
            self.preview.update()

    def closeEvent(self, event):
        if callable(self.closed_callback):
            self.closed_callback(self)
        super().closeEvent(event)


class DecorationAdjustWindow(CozyProgressWindow):
    """Player-facing idle decoration transform editor."""

    def __init__(
        self,
        pet,
        decoration_id,
        save_callback,
        closed_callback=None,
    ):
        self.decoration_id = decoration_id
        self.save_callback = save_callback
        self.closed_callback = closed_callback
        definition = progression.DECORATION_DEFINITIONS[decoration_id]
        super().__init__(
            pet,
            f"🎀 微调 · {definition['name']}",
            "只调整待机姿势。拖动装饰改变位置，也可以精细调整大小和角度。",
            (690, 650),
        )
        self.preview = DecorationPreview(
            pet, decoration_id, self._finish_drag
        )
        self.content_layout.addWidget(self.preview)

        shape_title = QLabel("大小与角度")
        shape_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(shape_title)
        shape_row = QHBoxLayout()
        for text, scale, rotation in (
            ("缩小", -0.035, 0.0),
            ("放大", 0.035, 0.0),
            ("左转", 0.0, -2.0),
            ("右转", 0.0, 2.0),
        ):
            button = FeedbackButton(text)
            button.setObjectName("softButton")
            button.clicked.connect(
                lambda _checked=False, s=scale, r=rotation:
                self._change(scale=s, rotation=r)
            )
            shape_row.addWidget(button)
        self.content_layout.addLayout(shape_row)

        reset_button = FeedbackButton("恢复这件装饰的默认位置")
        reset_button.setObjectName("softButton")
        reset_button.clicked.connect(self._reset)
        self.content_layout.addWidget(reset_button)
        self.content_layout.addStretch(1)
        self.refresh()

    def _save_and_repaint(self):
        self.save_callback(self.pet.state)
        self.pet.update()
        self.preview.update()
        self.refresh()

    def _change(
        self,
        *,
        x=0.0,
        y=0.0,
        scale=0.0,
        rotation=0.0,
    ):
        current = progression.decoration_transform(
            self.pet.state, self.decoration_id
        )
        progression.set_decoration_transform(
            self.pet.state,
            self.decoration_id,
            x=current["x"] + x,
            y=current["y"] + y,
            scale=current["scale"] + scale,
            rotation=current["rotation"] + rotation,
        )
        self._save_and_repaint()

    def _finish_drag(self):
        self._save_and_repaint()

    def _reset(self):
        progression.reset_decoration_transform(
            self.pet.state, self.decoration_id
        )
        self._save_and_repaint()
        self.status_label.setText("已经恢复默认位置。")

    def refresh(self):
        self._refresh_coin_label()
        transform = progression.decoration_transform(
            self.pet.state, self.decoration_id
        )
        self.status_label.setText(
            "位置 "
            f"{transform['x']:.3f}, {transform['y']:.3f}"
            f"  ·  大小 {transform['scale']:.2f}"
            f"  ·  角度 {transform['rotation']:+.0f}°"
        )
        if hasattr(self, "preview"):
            self.preview.update()

    def closeEvent(self, event):
        if callable(self.closed_callback):
            self.closed_callback(self)
        super().closeEvent(event)


class ShopWindow(CozyProgressWindow):
    DECORATION_TABS = (
        ("neck", "颈饰"),
        ("head", "帽子"),
        ("eyes", "眼镜"),
    )

    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        self.page = "pets" if isinstance(pet.state.get("pets"), dict) else "outfits"
        self.decoration_category = "neck"
        self.outfit_pet_id = "lunch_meat"
        self.adjust_window = None
        self.preview_window = None
        super().__init__(
            pet,
            "🏪 Pet币商店",
            "挑选可爱装扮，或用成就奖励强化日常互动。",
            (850, 960),
            shop_theme=True,
        )
        self._tab_icons = {
            "pets": _shop_asset("pet_tab_icon.png"),
            "outfits": _shop_asset("gift_icon.png"),
            "home": _shop_asset("furniture_tab_icon.png"),
            "upgrades": _shop_asset("upgrade_tab_icon.png"),
        }
        self._tab_buttons = {}
        self._build_tab_bar()

    def _build_tab_bar(self):
        """Fixed tab bar above the scroll area so paging never moves it."""
        tab_bar = QFrame()
        tab_bar.setObjectName("tabBar")
        if self.shop_theme:
            tab_bar.setFixedHeight(58)
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(6, 6, 6, 6)
        tab_layout.setSpacing(7)
        for page, text in (
            ("pets", "宠物"),
            ("outfits", "套装"),
            ("home", "家居"),
            ("upgrades", "强化"),
        ):
            button = FeedbackButton(text)
            button.setObjectName("tabButton")
            icon_path = self._tab_icons.get(page)
            if icon_path and os.path.exists(icon_path):
                button.setIcon(QIcon(icon_path))
                button.setIconSize(QSize(26, 26))
            button.setCheckable(True)
            button.setChecked(self.page == page)
            button.setCursor(Qt.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(
                lambda _checked=False, selected=page:
                self._set_page(selected)
            )
            tab_layout.addWidget(button)
            self._tab_buttons[page] = button
        self.root_layout.insertWidget(1, tab_bar)

    def _sync_tab_bar(self):
        has_pets = isinstance(self.pet.state.get("pets"), dict)
        for page, button in self._tab_buttons.items():
            button.setVisible(page != "pets" or has_pets)
            button.setChecked(self.page == page)

    def refresh(self):
        progression.ensure_progression(self.pet.state)
        self._refresh_coin_label()
        self._sync_tab_bar()
        _clear_layout(self.content_layout)

        if self.page == "pets":
            self._build_pets_page()
        elif self.page == "outfits":
            self._build_outfits_page()
        elif self.page == "home":
            self._build_home_page()
        else:
            self._build_upgrades_page()
        self.content_layout.addStretch(1)

    def _set_page(self, page):
        if page not in self.page_ids() or page == self.page:
            return
        self.page = page
        self.status_label.clear()
        self.scroll.verticalScrollBar().setValue(0)
        self.refresh()

    @staticmethod
    def page_ids():
        return ("pets", "outfits", "home", "upgrades")

    def _build_pets_page(self):
        title = QLabel("宠物商店")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        tip = QLabel("挑选可爱的小狗，用 Pet币 带回家。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignCenter)
        self._add_page_header(title, tip)
        registry = load_pet_registry()
        pet_ids = sorted(
            progression.available_pet_ids(),
            key=lambda pet_id: int(registry[pet_id].get("price", 0)) != 0,
        )
        for pet_id in pet_ids:
            self.content_layout.addWidget(self._pet_card(pet_id))

    def _pet_card(self, pet_id):
        state = self.pet.state
        owned = progression.pet_owned(state, pet_id)
        active = state.get("active_pet_id") == pet_id
        definition = load_pet_registry()[pet_id]
        card = QFrame()
        card.setObjectName(f"petCard_{pet_id}")
        card.setProperty("shopCard", True)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(14)

        preview = RoundedPixmapLabel(radius=26)
        preview.setObjectName(f"petPreview_{pet_id}")
        preview.setFixedSize(135, 135)
        preview.setAlignment(Qt.AlignCenter)
        preview_path = pet_avatar_path(pet_id)
        pixmap = QPixmap(preview_path) if preview_path else QPixmap()
        if pixmap.isNull():
            preview.setStyleSheet("background: #f4d6b5; border-radius: 8px;")
        else:
            preview.setPixmap(pixmap.scaled(
                preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation,
            ))
        layout.addWidget(preview)

        info = QVBoxLayout()
        info.setSpacing(7)
        title_row = QHBoxLayout()
        title = QLabel(self._pet_shop_name(pet_id, state))
        title.setObjectName(f"petName_{pet_id}")
        title.setProperty("cardTitle", True)
        title_row.addWidget(title)
        title_row.addStretch(1)
        info.addLayout(title_row)

        description = QLabel(definition.get("description", ""))
        description.setObjectName(f"petDescription_{pet_id}")
        description.setProperty("mutedText", True)
        description.setWordWrap(False)
        info.addWidget(description)

        price_row_container = QWidget()
        price_row_container.setFixedHeight(54)
        price_row = QHBoxLayout(price_row_container)
        price_row.setContentsMargins(0, 0, 5, 0)
        price = int(definition.get("price", 0))
        pricing = progression.first_purchase_price(
            state, "pets", definition.get("original_price", price)
        )
        displayed_price = price if owned else pricing["price"]
        price_label = self._price_tag(
            "免费赠送" if displayed_price == 0 else f"{displayed_price} Pet币",
            "gift" if displayed_price == 0 else "normal",
            f"petPrice_{pet_id}",
        )
        button = None
        if not owned:
            button = FeedbackButton(
                "免费领取" if pricing["price"] == 0 else "购买"
            )
            button.setEnabled(_coin_balance(state) >= pricing["price"])
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, selected=pet_id: self._purchase_pet(selected)
            )
        elif not active:
            button = FeedbackButton("切换宠物")
            button.setProperty("switchPill", True)
            button.setFixedSize(115, 50)
            button.clicked.connect(
                lambda _checked=False, selected=pet_id: self._switch_pet(selected)
            )
        if button is not None:
            button.setObjectName(f"petAction_{pet_id}")
        discount_badge = None
        if not owned and pricing["eligible"]:
            original, discounted, discount_badge = self._price_labels(
                state, "pets", pricing["original_price"], pet_id
            )
            price_row.addWidget(original)
            price_row.addWidget(discounted)
        else:
            price_row.addWidget(price_label)
        price_row.addStretch(1)
        if button is not None:
            price_row.addWidget(button)
        info.addWidget(price_row_container)
        layout.addLayout(info, 1)

        if discount_badge is not None:
            title_row.addWidget(discount_badge, 0, Qt.AlignRight)
        if active:
            status_badge = _status_badge_label("🐾 使用中", "active")
        elif owned:
            status_badge = _status_badge_label("🐾 已拥有", "owned")
        else:
            status_badge = _status_badge_label("🔒 待解锁", None)
        status_pixmap = status_badge.pixmap()
        if status_pixmap is None or status_pixmap.isNull():
            status_badge.setProperty("levelBadge", True)
        status_badge.setObjectName(f"petStatus_{pet_id}")
        status_slot = QWidget()
        status_slot.setFixedSize(132, 48)
        status_slot_layout = QHBoxLayout(status_slot)
        status_slot_layout.setContentsMargins(0, 0, 0, 0)
        status_slot_layout.addWidget(status_badge, 0, Qt.AlignCenter)
        title_row.addWidget(status_slot, 0, Qt.AlignRight)
        return card

    @staticmethod
    def _pet_shop_name(pet_id, state):
        definition = pet_definition(pet_id)
        profile = state.get("pets", {}).get(pet_id, {})
        nickname = profile.get("name") or profile.get("pet_name") if isinstance(profile, dict) else ""
        nickname = str(nickname).strip() if nickname else ""
        default = definition["default_name"]
        return f"{nickname}（{default}）" if nickname and nickname != default else default

    @staticmethod
    def _price_tag(text, role, object_name):
        if role == "gift":
            gift_pixmap = _shop_pixmap_cropped("free_gift_button.png", 50)
            if not gift_pixmap.isNull():
                label = PreservedTextLabel(text)
                label.setObjectName(object_name)
                label.setProperty("priceTagRole", role)
                label.setPixmap(gift_pixmap)
                label.setContentsMargins(12, 4, 12, 4)
                label.setMinimumHeight(54)
                label.setStyleSheet(
                    "background: transparent; border: 0; border-image: none;"
                )
                return label
        label = PriceTagLabel(text)
        label.setObjectName(object_name)
        label.setProperty("priceTagRole", role)
        return label

    @classmethod
    def _price_labels(cls, state, category, original_price, prefix):
        pricing = progression.first_purchase_price(state, category, original_price)
        original = cls._price_tag(
            f"原价：{pricing['original_price']} Pet币",
            "normal", f"originalPrice_{prefix}",
        )
        original.setProperty("priceRole", "original")
        font = original.font()
        font.setStrikeOut(True)
        original.setFont(font)
        discounted = cls._price_tag(
            f"现价：{pricing['price']} Pet币",
            "sale", f"discountPrice_{prefix}",
        )
        discounted.setProperty("priceRole", "discounted")
        discount = round(
            (1 - pricing["price"] / pricing["original_price"]) * 100
        )
        badge = cls._price_tag(
            f"-{discount}%", "discount", f"discountBadge_{prefix}"
        )
        badge.setProperty("discountBubble", True)
        return original, discounted, badge

    def _finish_pet_action(self, result, *, save=True):
        message = result.get("message", "宠物状态没有改变。")
        if result.get("ok"):
            if save:
                self.save_callback(self.pet.state)
            self.pet.update()
        self.pet.say(message, 2100)
        self.refresh()
        self.status_label.setText(message)

    def _show_purchase_popup(self, title, lines):
        previous = getattr(self, "_purchase_popup", None)
        if previous is not None:
            try:
                previous.close()
            except RuntimeError:
                pass
        popup = PurchasePopup(title, lines, self)
        self._purchase_popup = popup
        geometry = self.frameGeometry()
        popup.move(
            geometry.center().x() - popup.width() // 2,
            geometry.center().y() - popup.height() // 2,
        )
        popup.show()
        QApplication.processEvents()

    def _purchase_pet(self, pet_id):
        result = progression.purchase_pet(self.pet.state, pet_id)
        save_purchase = True
        if result.get("ok"):
            registry = load_pet_registry().get(pet_id, {})
            pet_name = registry.get("name", pet_id)
            price = int(result.get("price", 0))
            self._show_purchase_popup(
                "欢迎新伙伴",
                [f"{pet_name} 已加入你的家庭！"]
                + ([f"消耗 {price} Pet币"] if price > 0 else ["免费带回家"]),
            )
            switch_result = self._set_active_pet_result(pet_id)
            if switch_result.get("ok"):
                save_purchase = False
            else:
                result["message"] = (
                    f"购买成功，但切换失败："
                    f"{switch_result.get('message', '暂时无法切换宠物。')}"
                )
        self._finish_pet_action(result, save=save_purchase)

    def _set_active_pet_result(self, pet_id):
        callback = getattr(self.pet, "set_active_pet", None)
        if not callable(callback):
            return {
                "ok": False,
                "message": "暂时无法切换宠物。",
            }
        result = callback(pet_id)
        if result is True or result is None:
            return {"ok": True, "message": "已切换宠物。"}
        elif result is False:
            return {"ok": False, "message": "暂时无法切换宠物。"}
        elif not isinstance(result, dict):
            return {"ok": True, "message": "已切换宠物。"}
        return result

    def _switch_pet(self, pet_id):
        self.status_label.setText("正在切换宠物…")
        self.status_label.repaint()
        QApplication.processEvents()
        QTimer.singleShot(
            10,
            lambda: self._finish_pet_action(
                self._set_active_pet_result(pet_id),
                save=False,
            ),
        )

    def _build_outfits_page(self):
        products_title = QLabel("套装商店")
        products_title.setObjectName("sectionTitle")
        products_title.setAlignment(Qt.AlignCenter)
        tip = QLabel(
            "购买完整套装后直接装备，待机时会替换为套装专属动画。"
        )
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignCenter)
        self._add_page_header(products_title, tip)

        selector = QFrame()
        selector.setObjectName("outfitPetSelector")
        selector.setProperty("outfitPetSelector", True)
        selector_layout = QHBoxLayout(selector)
        selector_layout.setContentsMargins(5, 5, 5, 5)
        selector_layout.setSpacing(7)
        selector_group = QButtonGroup(selector)
        selector_group.setExclusive(True)
        for pet_id, text in (("lunch_meat", "午餐肉"), ("ice_cream", "冰淇淋")):
            button = FeedbackButton(text)
            button.setObjectName(f"outfitPet_{pet_id}")
            button.setProperty("outfitPetTab", True)
            button.setCheckable(True)
            button.setChecked(self.outfit_pet_id == pet_id)
            button.setCursor(Qt.PointingHandCursor)
            selector_group.addButton(button)
            button.clicked.connect(lambda _checked=False, selected=pet_id: self._set_outfit_pet(selected))
            selector_layout.addWidget(button)
        selector_layout.addStretch(1)
        self.content_layout.addWidget(selector)

        outfits = [
            (outfit_id, definition)
            for outfit_id, definition in progression.OUTFIT_DEFINITIONS.items()
            if definition.get("pet_id", "lunch_meat") == self.outfit_pet_id
        ]
        outfits.sort(key=lambda item: int(item[1].get("price", 0)) != 0)
        if not outfits:
            empty = QFrame()
            empty.setObjectName("outfitEmptyCard")
            empty.setProperty("placeholderCard", True)
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(18, 14, 18, 14)
            empty_title = QLabel("🌷 冰淇淋套装正在准备")
            empty_title.setObjectName("cardTitle")
            empty_note = QLabel(
                "后续会继续补充新的完整套装，已购买的套装可以随时切换。"
            )
            empty_note.setObjectName("muted")
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_note)
            self.content_layout.addWidget(empty)
            return
        for outfit_id, definition in outfits:
            self.content_layout.addWidget(
                self._outfit_card(outfit_id, definition)
            )

        upcoming = QFrame()
        upcoming.setObjectName("placeholderCard")
        upcoming_layout = QVBoxLayout(upcoming)
        upcoming_layout.setContentsMargins(18, 14, 18, 14)
        upcoming_title = QLabel("🌷 更多套装正在准备")
        upcoming_title.setObjectName("cardTitle")
        upcoming_note = QLabel(
            "后续会继续补充新的完整套装，已购买的套装可以随时切换。"
        )
        upcoming_note.setObjectName("muted")
        upcoming_layout.addWidget(upcoming_title)
        upcoming_layout.addWidget(upcoming_note)
        self.content_layout.addWidget(upcoming)

    def _set_outfit_pet(self, pet_id):
        if pet_id == self.outfit_pet_id:
            return
        self.outfit_pet_id = pet_id
        self.refresh()

    def _outfit_card(self, outfit_id, definition):
        state = self.pet.state
        owned = progression.outfit_owned(state, outfit_id)
        equipped = progression.equipped_outfit(state) == outfit_id
        card = QFrame()
        card.setObjectName("decorationCard")
        card.setFixedHeight(200)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(18)

        preview = QLabel()
        preview.setObjectName(f"outfitPreview_{outfit_id}")
        preview.setFixedSize(210, 150)
        preview.setAlignment(Qt.AlignCenter)
        asset_folder = definition.get("asset_folder", outfit_id)
        pixmap = QPixmap(os.path.join(
            OUTFITS_DIR, asset_folder, definition["preview_asset"]
        ))
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(
                preview.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))
        layout.addWidget(preview)

        info = QVBoxLayout()
        info.setSpacing(7)
        title_row = QHBoxLayout()
        title = QLabel(f"{definition['icon']} {definition['name']}")
        title.setObjectName("cardTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        if equipped:
            badge = _status_badge_label("🐾 使用中", "active")
        else:
            badge = _status_badge_label("🐾 已拥有", "owned")
            if not badge.pixmap().isNull():
                placeholder = QPixmap(badge.pixmap().size())
                placeholder.fill(Qt.transparent)
                badge.setPixmap(placeholder)
        if badge.pixmap().isNull():
            badge.setObjectName("levelBadge")
        title_row.addWidget(badge)
        info.addLayout(title_row)

        description = QLabel(definition["description"])
        description.setObjectName("muted")
        description.setWordWrap(True)
        description.setMinimumHeight(46)
        info.addWidget(description)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 13, 0)
        price = int(definition.get("price", 0))
        price_text = self._price_tag(
            "免费赠送" if price == 0 else f"{price} Pet币",
            "gift" if price == 0 else "normal",
            f"outfitPrice_{outfit_id}",
        )
        if not owned:
            button = FeedbackButton("购买")
            button.setEnabled(_coin_balance(state) >= price)
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, selected=outfit_id:
                self._purchase_outfit(selected)
            )
        elif equipped:
            button = FeedbackButton("卸下套装")
            button.setProperty("coralPill", True)
            button.clicked.connect(self._unequip_outfit)
        else:
            button = FeedbackButton("装备套装")
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, selected=outfit_id:
                self._equip_outfit(selected)
            )
        action_row.addWidget(price_text)
        action_row.addStretch(1)
        action_row.addWidget(button)
        info.addStretch(1)
        info.addLayout(action_row)
        layout.addLayout(info, 1)
        return card

    def _set_decoration_category(self, category):
        valid = {item[0] for item in self.DECORATION_TABS}
        if category not in valid or category == self.decoration_category:
            return
        self.decoration_category = category
        self.status_label.clear()
        self.scroll.verticalScrollBar().setValue(0)
        self.refresh()

    def _decoration_card(self, decoration_id, definition):
        state = self.pet.state
        owned = progression.decoration_owned(state, decoration_id)
        equipped = (
            progression.equipped_decoration(
                state, definition["category"]
            ) == decoration_id
        )
        card = QFrame()
        card.setObjectName("decorationCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(18)

        preview = QLabel()
        preview.setFixedSize(210, 112)
        preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(os.path.join(
            DECORATIONS_DIR, definition["asset"]
        ))
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(
                preview.size(), Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ))
        layout.addWidget(preview)

        info = QVBoxLayout()
        info.setSpacing(7)
        title_row = QHBoxLayout()
        title = QLabel(
            f"{definition['icon']} {definition['name']}"
        )
        title.setObjectName("cardTitle")
        if equipped:
            badge = _status_badge_label("🐾 使用中", "active")
        elif owned:
            badge = _status_badge_label("🐾 已拥有", "owned")
        else:
            badge = _status_badge_label(definition["category_name"], None)
        if badge.pixmap().isNull():
            badge.setObjectName("levelBadge")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(badge)
        info.addLayout(title_row)

        description = QLabel(definition["description"])
        description.setObjectName("muted")
        description.setWordWrap(True)
        info.addWidget(description)

        action_row = QHBoxLayout()
        price = int(definition.get("price", 0))
        price_text = QLabel(
            "第一件装扮免费赠送"
            if price == 0 else f"{price} Pet币"
        )
        price_text.setObjectName("reward")
        if not owned:
            button = FeedbackButton(
                "免费领取" if price == 0 else f"{price} Pet币 · 购买"
            )
            button.setEnabled(state.get("pet_coins", 0) >= price)
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._purchase_decoration(selected)
            )
        elif equipped:
            button = FeedbackButton("卸下")
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, category=definition["category"]:
                self._unequip_decoration(category)
            )
        else:
            button = FeedbackButton("装备")
            button.setProperty("coralPill", True)
            button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._equip_decoration(selected)
            )
        action_row.addWidget(price_text)
        action_row.addStretch(1)
        preview_button = FeedbackButton("预览")
        preview_button.setObjectName("softButton")
        preview_button.clicked.connect(
            lambda _checked=False, selected=decoration_id:
            self._open_decoration_preview(selected)
        )
        action_row.addWidget(preview_button)
        if equipped:
            adjust_button = FeedbackButton("微调位置")
            adjust_button.setObjectName("softButton")
            adjust_button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._open_decoration_adjuster(selected)
            )
            action_row.addWidget(adjust_button)
        action_row.addWidget(button)
        info.addLayout(action_row)
        layout.addLayout(info, 1)
        return card

    def _finish_decoration_action(self, result):
        message = result.get("message", "装扮状态没有改变。")
        if result.get("ok"):
            self.save_callback(self.pet.state)
            self.pet.update()
            home = getattr(self.pet, "home_scene_window", None)
            refresh_home = getattr(home, "refresh_pet_assets", None)
            if callable(refresh_home):
                refresh_home()
        self.pet.say(message, 2100)
        self.refresh()
        self.status_label.setText(message)

    def _purchase_decoration(self, decoration_id):
        self._finish_decoration_action(
            progression.purchase_decoration(
                self.pet.state, decoration_id
            )
        )

    def _purchase_outfit(self, outfit_id):
        result = progression.purchase_outfit(self.pet.state, outfit_id)
        if result.get("ok"):
            definition = progression.OUTFIT_DEFINITIONS.get(outfit_id, {})
            name = definition.get("name", outfit_id)
            price = int(result.get("price", 0))
            self._show_purchase_popup(
                "套装入手",
                [f"{name} 已放入衣柜"]
                + ([f"消耗 {price} Pet币"] if price > 0 else ["免费获得"]),
            )
        self._finish_decoration_action(result)

    def _equip_outfit(self, outfit_id):
        self._finish_decoration_action(
            progression.equip_outfit(self.pet.state, outfit_id)
        )

    def _unequip_outfit(self):
        self._finish_decoration_action(
            progression.unequip_outfit(self.pet.state)
        )

    def _equip_decoration(self, decoration_id):
        self._finish_decoration_action(
            progression.equip_decoration(
                self.pet.state, decoration_id
            )
        )

    def _unequip_decoration(self, category):
        self._finish_decoration_action(
            progression.unequip_decoration(
                self.pet.state, category
            )
        )

    def _open_decoration_adjuster(self, decoration_id):
        definition = progression.DECORATION_DEFINITIONS.get(decoration_id)
        if definition is None:
            return
        if (
            progression.equipped_decoration(
                self.pet.state, definition["category"]
            ) != decoration_id
        ):
            self.status_label.setText("请先装备这件装饰，再调整位置。")
            return
        if self.adjust_window is not None:
            try:
                self.adjust_window.close()
            except RuntimeError:
                pass
        self.adjust_window = DecorationAdjustWindow(
            self.pet,
            decoration_id,
            self.save_callback,
            closed_callback=self._adjuster_closed,
        )
        self.adjust_window.show_near_pet()

    def _open_decoration_preview(self, decoration_id):
        if decoration_id not in progression.DECORATION_DEFINITIONS:
            return
        if self.preview_window is not None:
            try:
                self.preview_window.close()
            except RuntimeError:
                pass
        self.preview_window = DecorationPreviewWindow(
            self.pet,
            decoration_id,
            closed_callback=self._preview_closed,
        )
        self.preview_window.show_near_pet()

    def _preview_closed(self, window):
        if self.preview_window is window:
            self.preview_window = None

    def _adjuster_closed(self, window):
        if self.adjust_window is window:
            self.adjust_window = None

    def _build_home_page(self):
        title = QLabel("家居小铺")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        tip = QLabel(
            "购买后的家具会放入家场景。打开家场景后，可直接拖动家具调整位置。"
        )
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignCenter)
        self._add_page_header(title, tip)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setObjectName("homeDecorationGrid")
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        items = sorted(
            progression.HOME_DECORATION_DEFINITIONS.items(),
            key=lambda item: int(item[1].get("price", 0)) != 0,
        )
        for index, (decoration_id, definition) in enumerate(items):
            grid.addWidget(
                self._home_decoration_card(decoration_id, definition),
                index // 2,
                index % 2,
            )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.content_layout.addWidget(grid_host)

    def _home_decoration_card(self, decoration_id, definition):
        state = self.pet.state
        owned = decoration_id in state.get("owned_home_decorations", [])
        card = QFrame()
        card.setObjectName(f"homeDecorationCard_{decoration_id}")
        card.setProperty("shopCard", True)
        card.setFixedHeight(310)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(12)

        preview = QLabel()
        preview.setObjectName(f"homePreview_{decoration_id}")
        preview.setFixedSize(150, 112)
        preview.setAlignment(Qt.AlignCenter)
        if decoration_id == "home_status_card":
            pixmap = render_home_status_card(state)
        else:
            pixmap = QPixmap(HOME_FURNITURE_PATHS[decoration_id])
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(
                preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        layout.addWidget(preview, 0, Qt.AlignCenter)

        info = QVBoxLayout()
        info.setSpacing(6)
        title_row = QHBoxLayout()
        title = QLabel(definition["name"])
        title.setObjectName("cardTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        info.addLayout(title_row)

        description = QLabel(definition["description"])
        description.setObjectName("muted")
        description.setWordWrap(True)
        description.setMinimumHeight(46)
        info.addWidget(description)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 13, 0)
        price = int(definition["price"])
        price_label = self._price_tag(
            "免费赠送" if price == 0 else f"{price} Pet币",
            "gift" if price == 0 else "normal",
            f"homePrice_{decoration_id}",
        )
        action_row.addWidget(price_label)
        action_row.addStretch(1)
        slot = QWidget()
        slot.setFixedSize(132, 48)
        slot_layout = QHBoxLayout(slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        if owned:
            owned_label = _status_badge_label("🐾 已拥有", "owned")
            slot_layout.addWidget(owned_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        else:
            button = FeedbackButton("免费领取" if price == 0 else "购买")
            button.setProperty("coralPill", True)
            button.setEnabled(_coin_balance(state) >= price)
            button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._purchase_home_decoration(selected)
            )
            slot_layout.addWidget(button, 0, Qt.AlignRight | Qt.AlignVCenter)
        action_row.addWidget(slot)
        info.addLayout(action_row)
        layout.addLayout(info, 1)
        return card

    def _purchase_home_decoration(self, decoration_id):
        result = progression.purchase_home_decoration(
            self.pet.state, decoration_id
        )
        message = result.get("message", "家居状态没有改变。")
        if result.get("ok"):
            definition = progression.HOME_DECORATION_DEFINITIONS.get(
                decoration_id, {}
            )
            name = definition.get("name", decoration_id)
            price = int(result.get("price", 0))
            self._show_purchase_popup(
                "家具到手",
                [f"{name} 已放入你的小家"]
                + ([f"消耗 {price} Pet币"] if price > 0 else ["免费领取"]),
            )
            self.save_callback(self.pet.state)
            self.pet.update()
        self.pet.say(message, 2100)
        self.refresh()
        self.status_label.setText(message)

    def closeEvent(self, event):
        if self.adjust_window is not None:
            try:
                self.adjust_window.close()
            except RuntimeError:
                pass
            self.adjust_window = None
        if self.preview_window is not None:
            try:
                self.preview_window.close()
            except RuntimeError:
                pass
            self.preview_window = None
        super().closeEvent(event)

    def _build_upgrades_page(self):
        upgrades_title = QLabel("成长强化")
        upgrades_title.setObjectName("sectionTitle")
        upgrades_title.setAlignment(Qt.AlignCenter)
        tip = QLabel("每项最多 5 级，强化后立即生效。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignCenter)
        self._add_page_header(upgrades_title, tip)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setObjectName("upgradeGrid")
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, (upgrade_id, definition) in enumerate(
                progression.UPGRADE_DEFINITIONS.items()):
            grid.addWidget(
                self._upgrade_card(upgrade_id, definition),
                index // 2,
                index % 2,
            )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.content_layout.addWidget(grid_host)

    def _upgrade_card(self, upgrade_id, definition):
        state = self.pet.state
        level = progression.upgrade_level(state, upgrade_id)
        maximum = definition["max_level"]
        card = QFrame()
        card.setObjectName("upgradeCard")
        card.setFixedHeight(230)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel(f"{definition['icon']} {definition['name']}")
        title.setObjectName("cardTitle")
        level_badge = QLabel(f"Lv.{level} / {maximum}")
        level_badge.setObjectName("levelBadge")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(level_badge)
        layout.addLayout(top)

        summary = QLabel(definition.get("summary", "强化对应的互动效果。"))
        summary.setObjectName("upgradeSummary")
        summary.setWordWrap(True)
        summary.setMinimumHeight(46)
        layout.addWidget(summary)

        effect = QLabel(progression.upgrade_description(state, upgrade_id))
        effect.setObjectName(f"upgradeEffect_{upgrade_id}")
        effect.setProperty("effectCurrent", True)
        effect.setWordWrap(True)
        layout.addWidget(effect)

        price = definition["prices"][level] if level < maximum else None
        if level >= maximum:
            button = FeedbackButton("已满级")
            button.setProperty("coralPill", True)
            button.setEnabled(False)
        else:
            button = FeedbackButton("强化")
            button.setProperty("coralPill", True)
            button.setEnabled(_coin_balance(state) >= price)
            button.clicked.connect(
                lambda _checked=False, selected=upgrade_id:
                self._purchase(selected)
            )
        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        bottom.addStretch(1)
        if price is not None:
            bottom.addWidget(self._price_tag(
                f"{price} Pet币", "normal", f"upgradePrice_{upgrade_id}"
            ))
            bottom.addSpacing(30)
        bottom.addWidget(button)
        layout.addStretch(1)
        layout.addLayout(bottom)
        return card

    def _purchase(self, upgrade_id):
        result = progression.purchase_upgrade(self.pet.state, upgrade_id)
        if result.get("ok"):
            self.save_callback(self.pet.state)
            self.pet.say(result["message"], 2200)
            message = (
                f"✓ {result['message']}  消耗 {result['price']} Pet币"
            )
            definition = progression.UPGRADE_DEFINITIONS.get(upgrade_id, {})
            name = definition.get("name", upgrade_id)
            level = int(self.pet.state.get("upgrades", {}).get(upgrade_id, 0))
            self._show_purchase_popup(
                "强化成功",
                [
                    f"{name} 提升至 Lv.{level} / 5",
                    f"消耗 {result['price']} Pet币",
                ],
            )
        else:
            message = result.get("message", "暂时无法强化。")
            self.pet.say(message, 1900)
        self.refresh()
        self.status_label.setText(message)
