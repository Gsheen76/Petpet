"""Boundary tests for the shop purchase confirmation popup."""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import QApplication, QDialog

import progression

from petpet.progression import ui


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def popup(qapp):
    pet = SimpleNamespace(
        state=progression.ensure_progression({}),
        say=lambda *_: None,
        update=lambda: None,
    )
    from unittest.mock import Mock
    # PurchasePopup builds its own card art; no parent window is needed.
    dialog = ui.PurchasePopup("确认", ["购买该套装？"])
    yield dialog
    dialog.close()
    qapp.processEvents()


def test_purchase_popup_escape_key_accepts_dialog(popup):
    popup.keyPressEvent(
        QKeyEvent(
            QEvent.KeyPress, Qt.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert popup.result() == QDialog.Accepted


def test_purchase_popup_click_outside_card_accepts_dialog(popup):
    accepted = []
    popup.accept = lambda: accepted.append(True)
    # A pixel near the corner lies outside the 22px rounded card silhouette.
    popup.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress, QPoint(2, 2), Qt.LeftButton,
            Qt.LeftButton, Qt.KeyboardModifier.NoModifier,
        )
    )
    assert accepted == [True]


def test_purchase_popup_click_inside_card_keeps_dialog_open(popup):
    accepted = []
    popup.accept = lambda: accepted.append(True)
    popup.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPoint(popup.width() // 2, popup.height() // 2),
            Qt.LeftButton, Qt.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert accepted == []


def test_escape_rejects_double_confirm_popup(qapp):
    """双键确认弹窗（cancel_text 非空）：Esc=取消而非确认（2026-09-18）。

    送礼弹窗以 Accepted 判定送出，Esc 误确认会真实消耗礼物。
    """
    from unittest.mock import patch

    dialog = ui.PurchasePopup(
        "送出礼物", ["确认送出？"],
        confirm_text="送出", cancel_text="再想想",
    )
    try:
        with patch.object(dialog, "reject") as reject:
            dialog.keyPressEvent(QKeyEvent(
                QEvent.KeyPress, Qt.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            ))
        reject.assert_called_once()
    finally:
        dialog.close()


def test_outside_click_rejects_double_confirm_popup(qapp):
    """双键确认弹窗：点卡片外=取消而非确认。"""
    from unittest.mock import patch

    dialog = ui.PurchasePopup(
        "送出礼物", ["确认送出？"],
        confirm_text="送出", cancel_text="再想想",
    )
    dialog.resize(360, 250)
    try:
        with patch.object(dialog, "reject") as reject:
            dialog.mousePressEvent(QMouseEvent(
                QEvent.MouseButtonPress, QPointF(-5, -5),
                Qt.LeftButton, Qt.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ))
        reject.assert_called_once()
    finally:
        dialog.close()
