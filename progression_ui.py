"""Warm Qt panels for records, achievements, Pet coins, and upgrades."""

from __future__ import annotations

import os
import time
import copy

from PyQt5.QtCore import Qt, QPoint, QRectF
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import progression
import decoration_renderer
from app_paths import DECORATIONS_DIR, POSES_DIR


PANEL_STYLE = """
    QWidget {
        background: transparent;
        color: #65483b;
        font-family: 'Microsoft YaHei', sans-serif;
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
        border-radius: 16px;
        padding: 7px 14px;
        font-size: 19px;
        font-weight: 900;
    }
    QLabel#sectionTitle {
        color: #8b5744;
        font-size: 25px;
        font-weight: 900;
        padding: 5px 2px;
    }
    QLabel#muted {
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
    QFrame#placeholderCard {
        background: #fffdf8;
        border: 1px solid #edd2bd;
        border-radius: 16px;
    }
    QLabel#cardTitle {
        color: #7a5040;
        font-size: 22px;
        font-weight: 900;
    }
    QLabel#cardValue {
        color: #ef886f;
        font-size: 27px;
        font-weight: 900;
    }
    QLabel#reward {
        background: #fff1c9;
        color: #a96e27;
        border-radius: 11px;
        padding: 4px 9px;
        font-size: 18px;
        font-weight: 800;
    }
    QLabel#levelBadge {
        background: #ffe4d8;
        color: #a8604e;
        border-radius: 12px;
        padding: 5px 10px;
        font-size: 18px;
        font-weight: 900;
    }
    QPushButton {
        background: #f28f76;
        color: white;
        border: 0;
        border-radius: 12px;
        padding: 9px 17px;
        font-size: 19px;
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
    QLabel#effectCurrent {
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


class CozyProgressWindow(QWidget):
    """Shared frameless shell with warm styling and draggable title bar."""

    def __init__(self, pet, title, subtitle, preferred_size):
        super().__init__()
        self.pet = pet
        self._drag_offset = None
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # A translucent top-level window does not automatically paint its
        # stylesheet background on every Qt backend. StyledBackground makes
        # the warm cream base real instead of exposing the desktop beneath.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("cozyProgressWindow")
        self.setStyleSheet(PANEL_STYLE)

        screen = QApplication.primaryScreen().availableGeometry()
        width = max(520, min(preferred_size[0], screen.width() - 60))
        height = max(560, min(preferred_size[1], screen.height() - 70))
        self.setFixedSize(width, height)

        root = QVBoxLayout(self)
        root.setContentsMargins(25, 18, 25, 20)
        root.setSpacing(9)

        title_bar = QFrame()
        title_bar.setCursor(Qt.ArrowCursor)
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.coin_label = QLabel()
        self.coin_label.setObjectName("coinPill")
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setFixedSize(38, 38)
        close_button.clicked.connect(self.close)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.coin_label)
        title_row.addWidget(close_button)
        title_bar.mousePressEvent = self._title_bar_press
        title_bar.mouseMoveEvent = self._title_bar_move
        title_bar.mouseReleaseEvent = self._title_bar_release
        root.addWidget(title_bar)

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
        root.addWidget(self.scroll, 1)
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
        outer = self.rect().adjusted(1, 1, -2, -2)
        gradient = QLinearGradient(outer.topLeft(), outer.bottomRight())
        gradient.setColorAt(0.0, QColor("#fffaf1"))
        gradient.setColorAt(1.0, QColor("#fff0df"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#e7c4ad"), 1.4))
        painter.drawRoundedRect(outer, 22, 22)

    def _refresh_coin_label(self):
        progression.ensure_progression(self.pet.state)
        self.coin_label.setText(
            f"Pet币  {self.pet.state.get('pet_coins', 0)}"
        )

    def show_near_pet(self):
        self.refresh()
        screen = self.pet.current_screen_rect()
        pet_rect = self.pet.geometry()
        gap = 20
        right_x = pet_rect.right() + gap
        left_x = pet_rect.left() - self.width() - gap
        if right_x + self.width() <= screen.right():
            x = right_x
        elif left_x >= screen.left():
            x = left_x
        else:
            x = screen.center().x() - self.width() // 2
        y = pet_rect.center().y() - self.height() // 2
        x = max(screen.left(), min(x, screen.right() - self.width() + 1))
        y = max(screen.top(), min(y, screen.bottom() - self.height() + 1))
        self.move(int(x), int(y))
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self):
        raise NotImplementedError


class RecordsWindow(CozyProgressWindow):
    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        super().__init__(
            pet,
            "📒 温馨记录",
            "每一次摸摸、饭饭和陪伴，都被认真记在这里。",
            (700, 760),
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
            self._hero_label(
                "当前好感",
                f"Lv.{state.get('affection_level', 1)}",
            ),
            0, 2,
        )
        hero_layout.addWidget(
            self._hero_label("当前等级", f"Lv.{state.get('level', 1)}"),
            1, 0,
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
        self.content_layout.addWidget(hero)

        section = QLabel("🐾 我们一起做过的事")
        section.setObjectName("sectionTitle")
        self.content_layout.addWidget(section)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        cards = [
            ("♡ 抚摸", records["pettings"], "轻轻摸过小狗的头"),
            ("◇ 喂食", records["feedings"], "一起吃过的饭饭"),
            ("○ 玩耍", records["play_sessions"], "开启过的玩耍时光"),
            ("☾ 睡觉", records["sleep_sessions"], "进入过香甜梦乡"),
            ("🎾 接住小球", records["fetch_catches"], "成功完成的飞扑接球"),
            ("💬 聊天", records["chats_opened"], "认真发送过的聊天消息"),
            ("☀ 摇醒", records["wake_shakes"], "被主人温柔摇醒"),
            ("✦ 总互动", records["interactions_total"], "四种基础互动合计"),
        ]
        for index, item in enumerate(cards):
            grid.addWidget(self._data_card(*item), index // 2, index % 2)
        self.content_layout.addWidget(grid_host)

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


class AchievementsWindow(CozyProgressWindow):
    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        super().__init__(
            pet,
            "🏅 暖心成就",
            "亮起的成就可以领取 Pet币；每升一级也会有一份奖励。",
            (760, 800),
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
        claim_all = QPushButton(
            f"一键领取（{len(claimable)}）"
            if claimable else "暂无待领取奖励"
        )
        claim_all.setObjectName("softButton")
        claim_all.setEnabled(bool(claimable))
        claim_all.clicked.connect(self._claim_all)
        row.addWidget(info)
        row.addStretch(1)
        row.addWidget(claim_all)
        self.content_layout.addWidget(summary)

        ordered = sorted(
            items,
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
        button = QPushButton()
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
            button = QPushButton(text)
            button.setObjectName("softButton")
            button.clicked.connect(
                lambda _checked=False, s=scale, r=rotation:
                self._change(scale=s, rotation=r)
            )
            shape_row.addWidget(button)
        self.content_layout.addLayout(shape_row)

        reset_button = QPushButton("恢复这件装饰的默认位置")
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
        self.page = "decorations"
        self.decoration_category = "neck"
        self.adjust_window = None
        self.preview_window = None
        super().__init__(
            pet,
            "🛍 Pet币商店",
            "挑选可爱装扮，或用成就奖励强化日常互动。",
            (850, 960),
        )

    def refresh(self):
        progression.ensure_progression(self.pet.state)
        self._refresh_coin_label()
        _clear_layout(self.content_layout)

        tab_bar = QFrame()
        tab_bar.setObjectName("tabBar")
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(5, 5, 5, 5)
        tab_layout.setSpacing(7)
        for page, text in (
            ("decorations", "🎀 装饰"),
            ("upgrades", "✨ 强化"),
        ):
            button = QPushButton(text)
            button.setObjectName("tabButton")
            button.setCheckable(True)
            button.setChecked(self.page == page)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, selected=page:
                self._set_page(selected)
            )
            tab_layout.addWidget(button)
        self.content_layout.addWidget(tab_bar)

        if self.page == "decorations":
            self._build_decorations_page()
        else:
            self._build_upgrades_page()
        self.content_layout.addStretch(1)

    def _set_page(self, page):
        if page not in ("decorations", "upgrades") or page == self.page:
            return
        self.page = page
        self.status_label.clear()
        self.scroll.verticalScrollBar().setValue(0)
        self.refresh()

    def _build_decorations_page(self):
        products_title = QLabel("🎁 装饰小铺")
        products_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(products_title)
        tip = QLabel(
            "同一分类同时只能装备一件。领取后可以随时装备或卸下，"
            "装饰只显示在待机姿势，并且可以自由微调位置、大小和角度。"
        )
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        self.content_layout.addWidget(tip)

        category_bar = QFrame()
        category_bar.setObjectName("categoryTabBar")
        category_layout = QHBoxLayout(category_bar)
        category_layout.setContentsMargins(5, 5, 5, 5)
        category_layout.setSpacing(7)
        for category, label in self.DECORATION_TABS:
            button = QPushButton(label)
            button.setObjectName("categoryTabButton")
            button.setCheckable(True)
            button.setChecked(self.decoration_category == category)
            button.clicked.connect(
                lambda _checked=False, selected=category:
                self._set_decoration_category(selected)
            )
            category_layout.addWidget(button)
        self.content_layout.addWidget(category_bar)

        category_label = dict(self.DECORATION_TABS)[
            self.decoration_category
        ]
        category_title = QLabel(f"当前分类 · {category_label}")
        category_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(category_title)

        for decoration_id, definition in (
            progression.DECORATION_DEFINITIONS.items()
        ):
            if definition["category"] != self.decoration_category:
                continue
            self.content_layout.addWidget(
                self._decoration_card(decoration_id, definition)
            )

        upcoming = QFrame()
        upcoming.setObjectName("placeholderCard")
        upcoming_layout = QVBoxLayout(upcoming)
        upcoming_layout.setContentsMargins(18, 14, 18, 14)
        upcoming_title = QLabel(f"🌷 更多{category_label}正在准备")
        upcoming_title.setObjectName("cardTitle")
        upcoming_note = QLabel(
            f"后续会继续补充新的{category_label}，已购买的装饰可以随时更换。"
        )
        upcoming_note.setObjectName("muted")
        upcoming_layout.addWidget(upcoming_title)
        upcoming_layout.addWidget(upcoming_note)
        self.content_layout.addWidget(upcoming)

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
        badge_text = (
            "佩戴中"
            if equipped
            else ("已拥有" if owned else definition["category_name"])
        )
        badge = QLabel(badge_text)
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
            if price == 0 else f"售价：{price} Pet币"
        )
        price_text.setObjectName("reward")
        if not owned:
            button = QPushButton(
                "免费领取" if price == 0 else f"{price} Pet币 · 购买"
            )
            button.setEnabled(state.get("pet_coins", 0) >= price)
            button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._purchase_decoration(selected)
            )
        elif equipped:
            button = QPushButton("卸下")
            button.setObjectName("softButton")
            button.clicked.connect(
                lambda _checked=False, category=definition["category"]:
                self._unequip_decoration(category)
            )
        else:
            button = QPushButton("装备")
            button.clicked.connect(
                lambda _checked=False, selected=decoration_id:
                self._equip_decoration(selected)
            )
        action_row.addWidget(price_text)
        action_row.addStretch(1)
        preview_button = QPushButton("预览")
        preview_button.setObjectName("softButton")
        preview_button.clicked.connect(
            lambda _checked=False, selected=decoration_id:
            self._open_decoration_preview(selected)
        )
        action_row.addWidget(preview_button)
        if equipped:
            adjust_button = QPushButton("微调位置")
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
        self.pet.say(message, 2100)
        self.refresh()
        self.status_label.setText(message)

    def _purchase_decoration(self, decoration_id):
        self._finish_decoration_action(
            progression.purchase_decoration(
                self.pet.state, decoration_id
            )
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
        upgrades_title = QLabel("✨ 成长强化")
        upgrades_title.setObjectName("sectionTitle")
        self.content_layout.addWidget(upgrades_title)
        tip = QLabel(
            "每项最多强化 5 次。价格逐级提高，效果会立即作用于真实互动。"
        )
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        self.content_layout.addWidget(tip)

        for upgrade_id, definition in progression.UPGRADE_DEFINITIONS.items():
            self.content_layout.addWidget(
                self._upgrade_card(upgrade_id, definition)
            )

    def _upgrade_card(self, upgrade_id, definition):
        state = self.pet.state
        level = progression.upgrade_level(state, upgrade_id)
        maximum = definition["max_level"]
        card = QFrame()
        card.setObjectName("upgradeCard")
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
        layout.addWidget(summary)

        current = QLabel(
            "当前效果\n" + progression.upgrade_description(
                state,
                upgrade_id,
                next_level=False,
                decay_rates=getattr(self.pet, "settings", None),
            )
        )
        current.setObjectName("effectCurrent")
        current.setWordWrap(True)
        layout.addWidget(current)

        if level >= maximum:
            next_text = QLabel("已达到满级，以上效果已经全部生效。")
            next_text.setObjectName("reward")
            button = QPushButton("已满级")
            button.setEnabled(False)
        else:
            next_text = QLabel(
                "升级后效果\n" + progression.upgrade_description(
                    state,
                    upgrade_id,
                    next_level=True,
                    decay_rates=getattr(self.pet, "settings", None),
                )
            )
            next_text.setObjectName("effectNext")
            next_text.setWordWrap(True)
            price = definition["prices"][level]
            button = QPushButton(f"{price} Pet币 · 强化")
            button.setEnabled(state.get("pet_coins", 0) >= price)
            button.clicked.connect(
                lambda _checked=False, selected=upgrade_id:
                self._purchase(selected)
            )
        layout.addWidget(next_text)

        bottom = QHBoxLayout()
        if level < maximum:
            price_label = QLabel(
                f"本次强化费用：{definition['prices'][level]} Pet币"
            )
            price_label.setObjectName("reward")
            bottom.addWidget(price_label)
        bottom.addStretch(1)
        bottom.addWidget(button)
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
        else:
            message = result.get("message", "暂时无法强化。")
            self.pet.say(message, 1900)
        self.refresh()
        self.status_label.setText(message)
