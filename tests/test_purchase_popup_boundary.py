"""Boundary tests for the shop purchase confirmation popup."""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PyQt5.QtCore import QEvent, QPoint, Qt
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
