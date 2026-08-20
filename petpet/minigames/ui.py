"""Small, capped Pet-coin games presented through a reusable game hub."""

from __future__ import annotations

import math
import os
import random
import time

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
)
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from petpet.progression import core as progression
from petpet.app.paths import POSES_DIR
from petpet.progression.ui import CozyProgressWindow


GAME_DEFINITIONS = {
    "coin_catch": {
        "icon": "🪙",
        "name": "金币雨",
        "description": "20 秒内点中不断移动的金币，命中越多奖励越高。",
        "accent": "#e5ad38",
    },
    "lucky_paws": {
        "icon": "🐾",
        "name": "幸运爪爪",
        "description": "看清金币放入哪只杯子，追踪左右移动后猜出位置，共 3 轮。",
        "accent": "#dd8f77",
    },
}


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        widget = item.widget()
        if child is not None:
            _clear_layout(child)
        if widget is not None:
            widget.deleteLater()


class CoinCatchCanvas(QWidget):
    """Code-drawn reaction game; no additional raster assets required."""

    score_changed = pyqtSignal(int, int, int, float)
    round_finished = pyqtSignal(int, int, int)

    DURATION_SECONDS = 20.0
    TARGET_LIFETIME = 0.9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(390)
        self.setCursor(Qt.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._dog = QPixmap(os.path.join(POSES_DIR, "idle.png"))
        self.running = False
        self.hits = 0
        self.combo = 0
        self.best_combo = 0
        self.earned_coins = 0
        self._deadline = 0.0
        self._target_deadline = 0.0
        self._target = QRectF()
        self._floating_rewards = []

    def start_round(self):
        self.running = True
        self.hits = 0
        self.combo = 0
        self.best_combo = 0
        self.earned_coins = 0
        self._floating_rewards = []
        now = time.monotonic()
        self._deadline = now + self.DURATION_SECONDS
        self._move_target(now)
        self._timer.start(33)
        self.score_changed.emit(0, 0, 0, self.DURATION_SECONDS)
        self.update()

    def stop_round(self):
        self._timer.stop()
        self.running = False

    def _move_target(self, now=None):
        now = time.monotonic() if now is None else now
        diameter = 66.0
        left = 28.0
        top = 25.0
        right = max(left, self.width() - diameter - 28.0)
        bottom = max(top, self.height() - diameter - 35.0)
        x = random.uniform(left, right)
        y = random.uniform(top, bottom)
        self._target = QRectF(x, y, diameter, diameter)
        self._target_deadline = now + self.TARGET_LIFETIME

    def _tick(self):
        if not self.running:
            return
        now = time.monotonic()
        remaining = max(0.0, self._deadline - now)
        self._floating_rewards = [
            item for item in self._floating_rewards
            if now - item[3] < 0.85
        ]
        if remaining <= 0:
            self.stop_round()
            self.score_changed.emit(
                self.hits, self.best_combo, self.earned_coins, 0.0
            )
            self.round_finished.emit(
                self.hits, self.best_combo, self.earned_coins
            )
            self.update()
            return
        if now >= self._target_deadline:
            self.combo = 0
            self._move_target(now)
        self.score_changed.emit(
            self.hits, self.best_combo, self.earned_coins, remaining
        )
        self.update()

    @staticmethod
    def coin_value_for_remaining(remaining):
        return 4 if 0.0 < float(remaining) <= 5.0 else 2

    def mousePressEvent(self, event):
        if not self.running or event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        remaining = max(0.0, self._deadline - time.monotonic())
        if self._target.contains(QPointF(event.pos())):
            reward_center = QPointF(self._target.center())
            value = self.coin_value_for_remaining(remaining)
            self.hits += 1
            self.earned_coins += value
            self.combo += 1
            self.best_combo = max(self.best_combo, self.combo)
            if value == 4:
                self._floating_rewards.append((
                    reward_center.x(), reward_center.y(), value,
                    time.monotonic(),
                ))
            self._move_target()
        else:
            self.combo = 0
        self.score_changed.emit(
            self.hits, self.best_combo, self.earned_coins, remaining
        )
        self.update()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        bounds = QRectF(self.rect()).adjusted(1, 1, -2, -2)
        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        gradient.setColorAt(0.0, QColor("#fff8dc"))
        gradient.setColorAt(1.0, QColor("#f9dfc8"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#e7c28e"), 1.5))
        painter.drawRoundedRect(bounds, 20, 20)

        if not self._dog.isNull():
            dog = self._dog.scaled(
                115, 132, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            painter.setOpacity(0.24)
            painter.drawPixmap(14, self.height() - dog.height() - 7, dog)
            painter.setOpacity(1.0)

        if self.running and not self._target.isEmpty():
            pulse = 1.0 + math.sin(time.monotonic() * 9.0) * 0.045
            target = QRectF(
                self._target.center().x() - self._target.width() * pulse / 2,
                self._target.center().y() - self._target.height() * pulse / 2,
                self._target.width() * pulse,
                self._target.height() * pulse,
            )
            shadow = target.translated(2, 4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(112, 72, 33, 45))
            painter.drawEllipse(shadow)
            coin_gradient = QLinearGradient(target.topLeft(), target.bottomRight())
            coin_gradient.setColorAt(0.0, QColor("#fff39b"))
            coin_gradient.setColorAt(0.5, QColor("#f6bd38"))
            coin_gradient.setColorAt(1.0, QColor("#d88a21"))
            painter.setBrush(coin_gradient)
            painter.setPen(QPen(QColor("#bd741d"), 2.2))
            painter.drawEllipse(target)
            inner = target.adjusted(9, 9, -9, -9)
            painter.setBrush(QColor(255, 230, 112, 95))
            painter.setPen(QPen(QColor("#d49328"), 1.5))
            painter.drawEllipse(inner)
            center = inner.center()
            painter.setBrush(QColor("#c77b20"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(center.x(), center.y() + 6), 9, 7)
            for dx, dy in ((-10, -5), (-3, -10), (5, -10), (11, -4)):
                painter.drawEllipse(
                    QPointF(center.x() + dx, center.y() + dy), 3.6, 4.3
                )

            remaining = max(0.0, self._deadline - time.monotonic())
            if 0.0 < remaining <= 5.0:
                # A real scrolling danmaku makes the double phase impossible
                # to miss without covering the clickable target area.
                progress = (5.0 - remaining) / 5.0
                message = "最后 5 秒  ·  Pet币奖励 ×4！"
                font = painter.font()
                font.setPixelSize(24)
                font.setBold(True)
                painter.setFont(font)
                text_width = painter.fontMetrics().horizontalAdvance(message)
                x = self.width() - progress * (self.width() + text_width)
                banner = QRectF(x, 16, text_width + 24, 43)
                painter.setBrush(QColor(188, 97, 32, 205))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(banner, 18, 18)
                painter.setPen(QColor("#fff7cf"))
                painter.drawText(banner, Qt.AlignCenter, message)

            now = time.monotonic()
            for x, y, value, created_at in self._floating_rewards:
                age = min(1.0, (now - created_at) / 0.85)
                color = QColor("#d87920")
                color.setAlpha(int(255 * (1.0 - age)))
                font = painter.font()
                font.setPixelSize(30)
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(color)
                painter.drawText(
                    QRectF(x - 45, y - 52 - age * 38, 90, 42),
                    Qt.AlignCenter,
                    f"+{value}",
                )
        else:
            painter.setPen(QColor("#956a51"))
            painter.drawText(
                bounds.adjusted(25, 20, -25, -20),
                Qt.AlignCenter | Qt.TextWordWrap,
                "点击开始后，尽快点中出现的金币吧！",
            )


class CoinCatchGameWindow(CozyProgressWindow):
    def __init__(self, pet, save_callback, finished_callback=None):
        self.save_callback = save_callback
        self.finished_callback = finished_callback
        super().__init__(
            pet,
            "🪙 金币雨",
            "20 秒反应挑战；点中金币可以累积本局奖励。",
            (720, 720),
        )
        self.score_label = QLabel("命中 0  ·  最佳连击 0  ·  20.0 秒")
        self.score_label.setObjectName("sectionTitle")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.score_label)
        self.canvas = CoinCatchCanvas()
        self.canvas.score_changed.connect(self._score_changed)
        self.canvas.round_finished.connect(self._finish_round)
        self.content_layout.addWidget(self.canvas, 1)
        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(self._start_round)
        self.content_layout.addWidget(self.start_button)
        self.refresh()

    def refresh(self):
        self._refresh_coin_label()
        if not self.canvas.running:
            self.status_label.setText("每局按成绩结算，没有每日奖励上限")

    def _start_round(self):
        if self.canvas.running:
            return
        self.start_button.setEnabled(False)
        self.start_button.setText("游戏进行中…")
        self.status_label.setText("看到金币就快点点击！")
        self.canvas.start_round()

    def _score_changed(self, hits, best_combo, earned_coins, remaining):
        self.score_label.setText(
            f"命中 {hits}  ·  本局 {earned_coins} Pet币  ·  "
            f"{remaining:.1f} 秒"
        )

    def _finish_round(self, hits, best_combo, earned_coins=None):
        requested = hits * 2 if earned_coins is None else earned_coins
        result = progression.award_minigame_coins(
            self.pet.state, "coin_catch", requested, score=hits
        )
        self.save_callback(self.pet.state)
        self._refresh_coin_label()
        self.start_button.setEnabled(True)
        self.start_button.setText("再玩一局")
        self.status_label.setText(
            f"本局命中 {hits} 次，获得 {requested} Pet币"
        )
        say = getattr(self.pet, "say", None)
        if callable(say):
            say(f"金币雨命中 {hits} 次，获得 {requested} 枚Pet币！", 2400)
        if callable(self.finished_callback):
            self.finished_callback()

    def closeEvent(self, event):
        self.canvas.stop_round()
        super().closeEvent(event)


class ShellShuffleCanvas(QWidget):
    """A fair shell game whose answer follows the animated cup identity."""

    phase_changed = pyqtSignal(str)
    guess_resolved = pyqtSignal(bool, int)

    DEFAULT_SWAP_DURATION = 0.58
    DEFAULT_SWAP_COUNT = 5

    def __init__(self, parent=None, rng=None):
        super().__init__(parent)
        self.rng = rng or random
        self.setMinimumHeight(335)
        self.setCursor(Qt.ArrowCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._token = 0
        self.phase = "idle"
        self.bowl_order = [0, 1, 2]
        self.coin_bowl_id = 0
        self.selected_slot = None
        self.result_correct = None
        self._swap_queue = []
        self._active_pair = None
        self._swap_started_at = 0.0
        self._swap_progress = 0.0
        self.swap_duration = self.DEFAULT_SWAP_DURATION
        self.swap_count = self.DEFAULT_SWAP_COUNT
        self.round_reward = 5

    def start_round(
        self, swap_duration=None, swap_count=None, round_reward=5
    ):
        self._token += 1
        token = self._token
        self._timer.stop()
        self.phase = "reveal"
        self.bowl_order = [0, 1, 2]
        self.coin_bowl_id = int(self.rng.randrange(3))
        self.selected_slot = None
        self.result_correct = None
        self._active_pair = None
        self._swap_progress = 0.0
        self.swap_duration = max(
            0.08,
            float(
                self.DEFAULT_SWAP_DURATION
                if swap_duration is None else swap_duration
            ),
        )
        self.swap_count = max(
            1,
            int(
                self.DEFAULT_SWAP_COUNT
                if swap_count is None else swap_count
            ),
        )
        self.round_reward = max(0, int(round_reward))
        self.setCursor(Qt.ArrowCursor)
        self.phase_changed.emit(self.phase)
        self.update()
        QTimer.singleShot(1200, lambda: self._begin_cover(token))

    def cancel(self):
        self._token += 1
        self._timer.stop()
        self.phase = "idle"
        self._active_pair = None
        self.setCursor(Qt.ArrowCursor)

    def _begin_cover(self, token):
        if token != self._token or self.phase != "reveal":
            return
        self.phase = "cover"
        self.phase_changed.emit(self.phase)
        self.update()
        QTimer.singleShot(500, lambda: self._begin_shuffle(token))

    def _begin_shuffle(self, token):
        if token != self._token or self.phase != "cover":
            return
        # Adjacent swaps keep every left/right movement readable. A direct
        # outer-cup swap would cross the stationary middle cup and obscure
        # the path at the midpoint.
        choices = [(0, 1), (1, 2)]
        self._swap_queue = []
        previous = None
        for _ in range(self.swap_count):
            available = [pair for pair in choices if pair != previous]
            pair = self.rng.choice(available)
            self._swap_queue.append(pair)
            previous = pair
        self.phase = "shuffle"
        self.phase_changed.emit(self.phase)
        self._start_next_swap()

    def _start_next_swap(self):
        if not self._swap_queue:
            self._timer.stop()
            self._active_pair = None
            self._swap_progress = 0.0
            self.phase = "guess"
            self.setCursor(Qt.PointingHandCursor)
            self.phase_changed.emit(self.phase)
            self.update()
            return
        self._active_pair = self._swap_queue.pop(0)
        self._swap_started_at = time.monotonic()
        self._swap_progress = 0.0
        self._timer.start(16)

    def _tick(self):
        if self.phase != "shuffle" or self._active_pair is None:
            self._timer.stop()
            return
        elapsed = time.monotonic() - self._swap_started_at
        self._swap_progress = min(1.0, elapsed / self.swap_duration)
        if self._swap_progress >= 1.0:
            left, right = self._active_pair
            self.bowl_order[left], self.bowl_order[right] = (
                self.bowl_order[right], self.bowl_order[left]
            )
            self._active_pair = None
            self._swap_progress = 0.0
            self._start_next_swap()
        self.update()

    def _slot_centers(self):
        width = max(420.0, float(self.width()))
        margin = min(125.0, width * 0.19)
        span = width - margin * 2.0
        y = max(155.0, self.height() * 0.56)
        return [
            QPointF(margin + span * index / 2.0, y)
            for index in range(3)
        ]

    def _bowl_positions(self):
        centers = self._slot_centers()
        positions = {
            bowl_id: QPointF(centers[slot])
            for slot, bowl_id in enumerate(self.bowl_order)
        }
        if self.phase == "shuffle" and self._active_pair is not None:
            left, right = self._active_pair
            first_id = self.bowl_order[left]
            second_id = self.bowl_order[right]
            t = self._swap_progress
            eased = 0.5 - math.cos(math.pi * t) / 2.0
            first_start, second_start = centers[left], centers[right]
            arc = math.sin(math.pi * t) * 34.0
            positions[first_id] = QPointF(
                first_start.x() + (second_start.x() - first_start.x()) * eased,
                first_start.y() - arc,
            )
            positions[second_id] = QPointF(
                second_start.x() + (first_start.x() - second_start.x()) * eased,
                second_start.y() + arc * 0.35,
            )
        return positions

    def resolve_guess(self, slot):
        """Resolve a visual slot against the cup identity after shuffling."""
        if self.phase != "guess" or slot not in (0, 1, 2):
            return None
        selected_bowl_id = self.bowl_order[slot]
        correct = selected_bowl_id == self.coin_bowl_id
        self.selected_slot = slot
        self.result_correct = correct
        self.phase = "result"
        self.setCursor(Qt.ArrowCursor)
        self.phase_changed.emit(self.phase)
        self.guess_resolved.emit(correct, slot)
        self.update()
        return correct

    def mousePressEvent(self, event):
        if self.phase != "guess" or event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        centers = self._slot_centers()
        distances = [abs(event.pos().x() - center.x()) for center in centers]
        slot = min(range(3), key=lambda index: distances[index])
        if distances[slot] <= 78 and abs(event.pos().y() - centers[slot].y()) <= 90:
            self.resolve_guess(slot)
            event.accept()
            return
        super().mousePressEvent(event)

    @staticmethod
    def _draw_coin(painter, center):
        coin = QRectF(center.x() - 25, center.y() - 25, 50, 50)
        gradient = QLinearGradient(coin.topLeft(), coin.bottomRight())
        gradient.setColorAt(0.0, QColor("#fff394"))
        gradient.setColorAt(0.55, QColor("#f4b82e"))
        gradient.setColorAt(1.0, QColor("#d7831d"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#b96e18"), 2.2))
        painter.drawEllipse(coin)
        painter.setBrush(QColor("#c77a1d"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center.x(), center.y() + 5), 7.5, 6)
        for dx, dy in ((-8, -4), (-2, -8), (5, -8), (9, -3)):
            painter.drawEllipse(QPointF(center.x() + dx, center.y() + dy), 3, 3.8)

    @staticmethod
    def _draw_bowl(painter, center, raised=False, selected=False):
        y = center.y() - (45 if raised else 0)
        shadow = QRectF(center.x() - 55, y + 42, 110, 18)
        painter.setBrush(QColor(90, 57, 38, 38))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(shadow)

        # A classic upside-down shell cup: narrow closed crown, broad bottom
        # rim, and a softly curved body. This reads as a real cover rather
        # than the former open flower-pot silhouette.
        path = QPainterPath()
        path.moveTo(center.x() - 33, y - 38)
        path.cubicTo(
            center.x() - 39, y - 18,
            center.x() - 52, y + 16,
            center.x() - 55, y + 31,
        )
        path.quadTo(center.x(), y + 48, center.x() + 55, y + 31)
        path.cubicTo(
            center.x() + 52, y + 16,
            center.x() + 39, y - 18,
            center.x() + 33, y - 38,
        )
        path.closeSubpath()
        gradient = QLinearGradient(
            center.x() - 52, y - 35, center.x() + 55, y + 38
        )
        gradient.setColorAt(0.0, QColor("#ffd5a5"))
        gradient.setColorAt(0.32, QColor("#e89a67"))
        gradient.setColorAt(0.72, QColor("#c97550"))
        gradient.setColorAt(1.0, QColor("#a95842"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#94503d"), 2.2))
        painter.drawPath(path)

        crown = QRectF(center.x() - 35, y - 48, 70, 22)
        crown_gradient = QLinearGradient(crown.topLeft(), crown.bottomLeft())
        crown_gradient.setColorAt(0.0, QColor("#ffe0b7"))
        crown_gradient.setColorAt(1.0, QColor("#d88459"))
        painter.setBrush(crown_gradient)
        painter.setPen(QPen(QColor("#99523e"), 2.0))
        painter.drawEllipse(crown)

        base_rim = QRectF(center.x() - 59, y + 24, 118, 25)
        base_gradient = QLinearGradient(
            base_rim.topLeft(), base_rim.bottomLeft()
        )
        base_gradient.setColorAt(0.0, QColor("#efaa77"))
        base_gradient.setColorAt(1.0, QColor("#a95742"))
        painter.setBrush(base_gradient)
        painter.setPen(QPen(QColor("#8e4939"), 2.2))
        painter.drawEllipse(base_rim)
        painter.setBrush(QColor("#c66f4e"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(center.x(), y + 5), 10, 8)
        for dx, dy in ((-11, -6), (-4, -12), (5, -12), (12, -6)):
            painter.drawEllipse(QPointF(center.x() + dx, y + dy), 4, 5)

        highlight = QPainterPath()
        highlight.moveTo(center.x() - 28, y - 25)
        highlight.cubicTo(
            center.x() - 35, y - 3,
            center.x() - 39, y + 10,
            center.x() - 40, y + 20,
        )
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 231, 202, 125), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawPath(highlight)
        if selected:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#f2b705"), 4, Qt.DashLine))
            painter.drawRoundedRect(
                QRectF(center.x() - 68, y - 56, 136, 118), 18, 18
            )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bounds = QRectF(self.rect()).adjusted(1, 1, -2, -2)
        gradient = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        gradient.setColorAt(0.0, QColor("#fff9e8"))
        gradient.setColorAt(1.0, QColor("#f6dfce"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#e6c39f"), 1.5))
        painter.drawRoundedRect(bounds, 20, 20)

        centers = self._slot_centers()
        positions = self._bowl_positions()
        coin_slot = self.bowl_order.index(self.coin_bowl_id)
        show_coin = self.phase in ("reveal", "result")
        if show_coin:
            coin_center = QPointF(
                centers[coin_slot].x(), centers[coin_slot].y() + 45
            )
            self._draw_coin(painter, coin_center)

        # Moving cups are drawn in vertical order so the lower arc naturally
        # passes in front of the upper one during a swap.
        for bowl_id, center in sorted(
            positions.items(), key=lambda item: item[1].y()
        ):
            slot = self.bowl_order.index(bowl_id)
            raised = show_coin and bowl_id == self.coin_bowl_id
            selected = self.phase == "result" and slot == self.selected_slot
            self._draw_bowl(painter, center, raised, selected)

        painter.setPen(QColor("#9a735f"))
        if self.phase == "idle":
            footer = "开始后先看清金币，再追踪杯子的真实移动"
        elif self.phase == "reveal":
            footer = "看仔细：金币放进了这只杯子"
        elif self.phase == "shuffle":
            footer = "盯住它，杯子正在左右交换…"
        elif self.phase == "guess":
            footer = "停止了！点击你认为藏着金币的杯子"
        elif self.result_correct:
            footer = f"猜对啦！这一轮获得 {self.round_reward} Pet币"
        else:
            footer = "金币在这里，下一轮继续追踪"
        painter.drawText(
            QRectF(20, self.height() - 38, self.width() - 40, 26),
            Qt.AlignCenter,
            footer,
        )


class LuckyPawsGameWindow(CozyProgressWindow):
    TOTAL_ROUNDS = 3
    ROUND_CONFIG = {
        1: {"reward": 10, "swap_count": 5, "swap_duration": 0.58,
            "difficulty": "入门速度"},
        2: {"reward": 20, "swap_count": 7, "swap_duration": 0.32,
            "difficulty": "快速移动"},
        3: {"reward": 30, "swap_count": 11, "swap_duration": 0.13,
            "difficulty": "极速挑战"},
    }

    def __init__(self, pet, save_callback, finished_callback=None, rng=None):
        self.save_callback = save_callback
        self.finished_callback = finished_callback
        self.rng = rng or random
        self.round_number = 0
        self.successes = 0
        self.earned_reward = 0
        self.running = False
        self._game_token = 0
        super().__init__(
            pet,
            "🐾 幸运爪爪",
            "先看金币放进杯子，再追踪三只杯子的左右移动。",
            (760, 720),
        )
        self.round_label = QLabel("准备开始 · 共 3 轮")
        self.round_label.setObjectName("sectionTitle")
        self.round_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.round_label)

        self.hint_label = QLabel("金币会先展示位置，然后杯子开始移动")
        self.hint_label.setObjectName("cardTitle")
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.content_layout.addWidget(self.hint_label)
        self.canvas = ShellShuffleCanvas(rng=self.rng)
        self.canvas.phase_changed.connect(self._phase_changed)
        self.canvas.guess_resolved.connect(self._guess_resolved)
        self.content_layout.addWidget(self.canvas, 1)

        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(self._start_game)
        self.content_layout.addWidget(self.start_button)
        self.refresh()

    def refresh(self):
        self._refresh_coin_label()
        if not self.running:
            self.status_label.setText("每局按成绩结算，没有每日奖励上限")

    def _start_game(self):
        if self.running:
            return
        self.running = True
        self._game_token += 1
        self.round_number = 0
        self.successes = 0
        self.earned_reward = 0
        self.start_button.setEnabled(False)
        self.start_button.setText("游戏进行中…")
        self._next_round(self._game_token)

    def _next_round(self, token=None):
        if not self.running or (token is not None and token != self._game_token):
            return
        if self.round_number >= self.TOTAL_ROUNDS:
            self._finish_game()
            return
        self.round_number += 1
        config = self.ROUND_CONFIG[self.round_number]
        self.round_label.setText(
            f"第 {self.round_number} / {self.TOTAL_ROUNDS} 轮"
            f"  ·  猜对 +{config['reward']} Pet币"
            f"  ·  {config['difficulty']}"
        )
        self.canvas.start_round(
            swap_duration=config["swap_duration"],
            swap_count=config["swap_count"],
            round_reward=config["reward"],
        )

    def _phase_changed(self, phase):
        messages = {
            "reveal": "看清金币放进了哪只杯子",
            "cover": "杯子盖好啦，准备开始移动",
            "shuffle": "杯子正在左右交换，盯住藏金币的那只",
            "guess": "移动结束，点击你追踪的杯子",
        }
        if phase in messages:
            self.hint_label.setText(messages[phase])

    def _guess_resolved(self, correct, selected_slot):
        if not self.running:
            return
        if correct:
            self.successes += 1
            self.earned_reward += self.ROUND_CONFIG[
                self.round_number
            ]["reward"]
        self.hint_label.setText(
            "找到了！小狗开心地摇尾巴～"
            if correct else "差一点，金币的位置已经揭晓啦"
        )
        token = self._game_token
        QTimer.singleShot(1400, lambda: self._next_round(token))

    def _finish_game(self):
        self.running = False
        requested = self.earned_reward
        result = progression.award_minigame_coins(
            self.pet.state,
            "lucky_paws",
            requested,
            score=self.successes,
        )
        self.save_callback(self.pet.state)
        self._refresh_coin_label()
        self.round_label.setText(
            f"完成 3 轮 · 猜对 {self.successes} 轮"
            f" · 获得 {requested} Pet币"
        )
        self.hint_label.setText("本局结束，休息一下再来挑战吧。")
        self.start_button.setEnabled(True)
        self.start_button.setText("再玩一局")
        self.status_label.setText(
            result["message"]
        )
        say = getattr(self.pet, "say", None)
        if callable(say):
            say(f"幸运爪爪猜对 {self.successes} 轮，{result['message']}！", 2400)
        if callable(self.finished_callback):
            self.finished_callback()

    def closeEvent(self, event):
        self.running = False
        self._game_token += 1
        self.canvas.cancel()
        super().closeEvent(event)


class MiniGameHubWindow(CozyProgressWindow):
    """Game picker for an extensible collection of Pet-coin games."""

    def __init__(self, pet, save_callback):
        self.save_callback = save_callback
        self.game_window = None
        super().__init__(
            pet,
            "🎮 小游戏中心",
            "选择一款小游戏放松一下，还能赚取 Pet币。",
            (760, 760),
        )

    def refresh(self):
        progression.ensure_progression(self.pet.state)
        self._refresh_coin_label()
        _clear_layout(self.content_layout)
        daily = QFrame()
        daily.setObjectName("heroCard")
        daily_layout = QVBoxLayout(daily)
        daily_layout.setContentsMargins(20, 16, 20, 16)
        daily_title = QLabel(
            "完成小游戏即可获得 Pet币"
        )
        daily_title.setObjectName("cardTitle")
        daily_note = QLabel(
            "奖励没有每日上限，每局会根据成绩单独结算。"
        )
        daily_note.setObjectName("muted")
        daily_note.setWordWrap(True)
        daily_layout.addWidget(daily_title)
        daily_layout.addWidget(daily_note)
        self.content_layout.addWidget(daily)

        section = QLabel("选择小游戏")
        section.setObjectName("sectionTitle")
        self.content_layout.addWidget(section)
        for game_id, definition in GAME_DEFINITIONS.items():
            self.content_layout.addWidget(
                self._game_card(game_id, definition)
            )

        upcoming = QFrame()
        upcoming.setObjectName("placeholderCard")
        upcoming_layout = QVBoxLayout(upcoming)
        upcoming_layout.setContentsMargins(18, 14, 18, 14)
        upcoming_title = QLabel("🌷 更多小游戏正在准备")
        upcoming_title.setObjectName("cardTitle")
        upcoming_note = QLabel("后续小游戏会继续加入这里，共用同一套奖励记录。")
        upcoming_note.setObjectName("muted")
        upcoming_layout.addWidget(upcoming_title)
        upcoming_layout.addWidget(upcoming_note)
        self.content_layout.addWidget(upcoming)
        self.content_layout.addStretch(1)
        self.status_label.setText(
            "选择喜欢的小游戏开始赚取 Pet币吧"
        )

    def _game_card(self, game_id, definition):
        card = QFrame()
        card.setObjectName("upgradeCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(16)
        icon = QLabel(definition["icon"])
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(64, 64)
        icon.setStyleSheet(
            f"background:{definition['accent']}33; border-radius:20px;"
            "font-size:34px;"
        )
        layout.addWidget(icon)
        text_layout = QVBoxLayout()
        title = QLabel(definition["name"])
        title.setObjectName("cardTitle")
        description = QLabel(definition["description"])
        description.setObjectName("muted")
        description.setWordWrap(True)
        best = progression.ensure_progression(
            self.pet.state
        )["minigame_best_scores"].get(game_id, 0)
        best_label = QLabel(f"最佳成绩：{best}")
        best_label.setObjectName("reward")
        text_layout.addWidget(title)
        text_layout.addWidget(description)
        text_layout.addWidget(best_label, 0, Qt.AlignLeft)
        layout.addLayout(text_layout, 1)
        button = QPushButton("开始")
        button.clicked.connect(
            lambda _checked=False, selected=game_id:
            self._open_game(selected)
        )
        layout.addWidget(button)
        return card

    def _open_game(self, game_id):
        if self.game_window is not None:
            try:
                self.game_window.close()
            except RuntimeError:
                pass
        window_type = {
            "coin_catch": CoinCatchGameWindow,
            "lucky_paws": LuckyPawsGameWindow,
        }.get(game_id)
        if window_type is None:
            return
        self.game_window = window_type(
            self.pet,
            self.save_callback,
            finished_callback=self.refresh,
        )
        self.game_window.show_near_pet()

    def closeEvent(self, event):
        if self.game_window is not None:
            try:
                self.game_window.close()
            except RuntimeError:
                pass
            self.game_window = None
        super().closeEvent(event)
