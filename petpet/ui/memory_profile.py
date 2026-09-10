"""聊天长期记忆档案面板（2026-09-11）：查看/编辑六栏 profile_facts。

数据契约在 ``petpet/chat/memory.py``（六栏 + 条数上限 + 单条 ≤60 字）；
本模块只做呈现与编辑，保存前统一过 ``sanitize_edited_facts`` 清洗网。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from petpet.app.fonts import APP_FONT_FAMILY
from petpet.app.paths import SHOP_UI_DIR
from petpet.chat.memory import (
    PROFILE_BUCKETS,
    PROFILE_BUCKET_CAPS,
    sanitize_edited_facts,
)
from petpet.progression.ui import FeedbackButton

_DIALOG_W, _DIALOG_H = 620, 760
_BUCKET_HINTS = {
    "称呼": "你希望 TA 怎么称呼你",
    "作息": "起床、睡觉、上下班时间",
    "喜欢": "喜欢的事物",
    "讨厌": "讨厌的事物",
    "重要的事": "纪念日、大事记",
    "其他": "别的想让 TA 记住的",
}

_PANEL_QSS = f"""
QWidget#profileRoot {{ background: transparent; }}
QLabel#profileTitle {{ color:#8c5a3c; font-size:24px; font-weight:700;
    font-family:'{APP_FONT_FAMILY}'; }}
QLabel#profileHint {{ color:#b08a72; font-size:13px;
    font-family:'{APP_FONT_FAMILY}'; }}
QLabel#bucketName {{ color:#a8643e; font-size:17px; font-weight:700;
    font-family:'{APP_FONT_FAMILY}'; }}
QLabel#bucketCount {{ color:#c4a48e; font-size:13px;
    font-family:'{APP_FONT_FAMILY}'; }}
QLabel#bucketHint {{ color:#c9ab94; font-size:12px;
    font-family:'{APP_FONT_FAMILY}'; }}
QLineEdit#factEdit {{ background:#fffaf4; color:#6b4632;
    border:1px solid #ecd9c8; border-radius:14px; padding:6px 14px;
    font-size:15px; font-family:'{APP_FONT_FAMILY}'; }}
QLineEdit#factEdit:focus {{ border:1px solid #f28f76; background:#fff; }}
QPushButton#profileClose {{ background:transparent; border:0;
    color:#a47b69; font-size:24px; font-weight:700; padding:0; }}
QPushButton#profileClose:hover {{ background:#ffcfc5; color:#bf5c52;
    border-radius:14px; }}
QPushButton#addFact {{ background:#fffaf6; color:#c07a52;
    border:1px solid #eccdb9; border-radius:12px; padding:3px 12px;
    font-size:13px; font-weight:700;
    font-family:'{APP_FONT_FAMILY}'; }}
QPushButton#addFact:hover {{ background:#ffe8dc; border-color:#dda993; }}
QPushButton#addFact:disabled {{ color:#d8c4b4; border-color:#eee0d3;
    background:#faf3ec; }}
QPushButton#delFact {{ background:transparent; border:0; color:#c9a48e;
    font-size:18px; font-weight:700; padding:0; }}
QPushButton#delFact:hover {{ background:#ffcfc5; color:#bf5c52;
    border-radius:11px; }}
QPushButton#saveProfile {{ background:#f28f76; color:#ffffff;
    border:0; border-radius:18px; padding:9px 34px; font-size:16px;
    font-weight:700; font-family:'{APP_FONT_FAMILY}'; }}
QPushButton#saveProfile:hover {{ background:#e19179; }}
QPushButton#saveProfile:pressed {{ background:#c66e5b; }}
QPushButton#cancelProfile {{ background:#fffaf6; color:#8c6252;
    border:1px solid #e6cfc2; border-radius:18px; padding:9px 30px;
    font-size:16px; font-weight:700; font-family:'{APP_FONT_FAMILY}'; }}
QPushButton#cancelProfile:hover {{ background:#ffe8dc;
    border-color:#dda993; }}
QPushButton#cancelProfile:pressed {{ background:#ffdcd0; }}
QScrollArea#profileScroll {{ background:transparent; border:0; }}
QWidget#profileScrollBody {{ background:transparent; }}
QFrame#bucketCard {{ background:#fffdf7; border:1px solid #f0e0d0;
    border-radius:16px; }}
"""


class MemoryProfileDialog(QDialog):
    """查看并编辑「TA 记住的我」六栏档案；accept 后读 result_facts。"""

    def __init__(self, facts, pet_name="", parent=None):
        super().__init__(
            parent,
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(_DIALOG_W, _DIALOG_H)
        self.result_facts = None
        self._facts = {
            bucket: [str(item) for item in ((facts or {}).get(bucket) or [])]
            for bucket in PROFILE_BUCKETS
        }
        self._rows = {}       # bucket -> [(QLineEdit, QPushButton), ...]
        self._add_buttons = {}
        self._cards = {}
        self._counts = {}

        root = QWidget(self)
        root.setObjectName("profileRoot")
        root.setGeometry(0, 0, _DIALOG_W, _DIALOG_H)
        root.setStyleSheet(_PANEL_QSS)
        self._root = root
        self._background = QPixmap(
            os.path.join(SHOP_UI_DIR, "background.png"))

        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 20)
        outer.setSpacing(10)
        outer.addLayout(self._build_title_row(pet_name))

        scroll = QScrollArea()
        scroll.setObjectName("profileScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("profileScrollBody")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(4, 2, 4, 2)
        self._body_layout.setSpacing(10)
        for bucket in PROFILE_BUCKETS:
            self._body_layout.addWidget(self._build_bucket_card(bucket))
        self._body_layout.addStretch(1)
        for bucket in PROFILE_BUCKETS:
            self._refresh_bucket_chrome(bucket)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        outer.addLayout(self._build_action_row())

    # ---------------------------------------------------------------- build

    def _build_title_row(self, pet_name):
        title = QLabel(f"{pet_name} 记住的我" if pet_name else "TA 记住的我")
        title.setObjectName("profileTitle")
        hint = QLabel("改错了直接编辑，删掉 TA 就忘；保存后下次聊天生效")
        hint.setObjectName("profileHint")
        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("profileClose")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.reject)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(title)
        title_col.addWidget(hint)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 4, 0)
        row.setSpacing(8)
        row.addLayout(title_col, 1)
        row.addWidget(self._close_btn)
        return row

    def _build_action_row(self):
        save = FeedbackButton("保存")
        save.setObjectName("saveProfile")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._on_save)
        cancel = FeedbackButton("取消")
        cancel.setObjectName("cancelProfile")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.setContentsMargins(6, 4, 6, 0)
        row.setSpacing(12)
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(save)
        return row

    def _build_bucket_card(self, bucket):
        card = QFrame()
        card.setObjectName("bucketCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        name = QLabel(bucket)
        name.setObjectName("bucketName")
        count = QLabel()
        count.setObjectName("bucketCount")
        hint = QLabel(_BUCKET_HINTS.get(bucket, ""))
        hint.setObjectName("bucketHint")
        add = QPushButton("＋添加")
        add.setObjectName("addFact")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda _=False, b=bucket: self._add_row(b))
        head.addWidget(name)
        head.addSpacing(2)
        head.addWidget(count)
        head.addStretch(1)
        head.addWidget(hint)
        head.addSpacing(6)
        head.addWidget(add)
        layout.addLayout(head)

        self._rows[bucket] = []
        for fact in self._facts.get(bucket) or []:
            layout.addLayout(self._make_fact_row(bucket, fact))
        self._add_buttons[bucket] = add
        self._counts[bucket] = count
        self._cards[bucket] = card
        return card

    def _make_fact_row(self, bucket, text=""):
        edit = QLineEdit(text)
        edit.setObjectName("factEdit")
        edit.setMaxLength(60)
        delete = QPushButton("×")
        delete.setObjectName("delFact")
        delete.setFixedSize(22, 22)
        delete.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(edit, 1)
        row.addWidget(delete)

        def remove(_checked=False, b=bucket, e=edit):
            for entry in list(self._rows[b]):
                if entry[0] is e:
                    entry[0].deleteLater()
                    entry[1].deleteLater()
                    self._rows[b].remove(entry)
            self._refresh_bucket_chrome(b)

        delete.clicked.connect(remove)
        self._rows[bucket].append((edit, delete))
        return row

    # ---------------------------------------------------------------- state

    def _add_row(self, bucket):
        if len(self._rows[bucket]) >= PROFILE_BUCKET_CAPS[bucket]:
            return
        self._cards[bucket].layout().addLayout(
            self._make_fact_row(bucket))
        self._refresh_bucket_chrome(bucket)
        self._rows[bucket][-1][0].setFocus()

    def _refresh_bucket_chrome(self, bucket):
        count = self._counts.get(bucket)
        n = len(self._rows.get(bucket) or [])
        cap = PROFILE_BUCKET_CAPS[bucket]
        if count is not None:
            count.setText(f"{n}/{cap}")
        add = self._add_buttons.get(bucket)
        if add is not None:
            add.setEnabled(n < cap)

    def collect_edits(self):
        """读 UI 当前内容 → 原始 facts dict（未清洗）。"""
        return {
            bucket: [
                edit.text()
                for edit, _delete in self._rows.get(bucket) or []
            ]
            for bucket in PROFILE_BUCKETS
        }

    def _on_save(self):
        self.result_facts = sanitize_edited_facts(self.collect_edits())
        self.accept()

    # ---------------------------------------------------------------- paint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 24, 24)
        painter.setClipPath(path)
        if not self._background.isNull():
            painter.drawPixmap(0, 0, self.width(), self.height(),
                               self._background)
        else:
            painter.fillRect(self.rect(), Qt.white)
        painter.end()
