"""Pure visual constants and rendering helpers for the home scene."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from PyQt5.QtCore import QPointF, QRect, QRectF, Qt
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QRegion

from petpet.app.paths import (
    HOME_FURNITURE_DIR,
    HOME_POSES_DIR,
    HOME_SCENES_DIR,
)
from petpet.progression import core as progression
from petpet.home.geometry import HOME_VIEWPORT_SIZE, scene_rect_for_screen


SCENES_DIR = HOME_SCENES_DIR
HOME_BACKGROUND_PATH = os.path.join(SCENES_DIR, "home-background.png")
HOME_BACKGROUND_MODE = "flattened_midground"
HOME_PET_WALK_DOWN_PATH = os.path.join(HOME_POSES_DIR, "home-pet-walk-down.png")
HOME_PET_WALK_BACK_RIGHT_PATH = os.path.join(
    HOME_POSES_DIR, "home-pet-walk-back-right.png"
)
HOME_PET_IDLE_PATH = os.path.join(HOME_POSES_DIR, "home-pet-idle-sit.png")
HOME_PET_SLEEP_PATH = os.path.join(HOME_POSES_DIR, "home-pet-sleep.png")
HOME_NAV_PAW_PATH = os.path.join(SCENES_DIR, "home-nav-paw.png")
HOME_NAV_TARGET_PATH = os.path.join(SCENES_DIR, "home-nav-target.png")
HOME_NAV_ARROW_PATH = os.path.join(SCENES_DIR, "home-nav-arrow.png")
HOME_PET_WALK_FRAME_SIZE = 640
HOME_PET_WALK_FRAME_COUNT = 8
HOME_PET_WALK_FPS = 8.0
HOME_PET_SLEEP_FRAME_SIZE = 640
HOME_PET_SLEEP_FRAME_COUNT = 8
HOME_PET_SLEEP_FPS = 3.0
HOME_PET_FIXED_DEPTH_SCALE = 1.08
HOME_DESTINATION_FADE_SECONDS = 0.35
HOME_PET_WALK_CONTENT_RECT = QRect(64, 80, 512, 464)
HOME_PET_IDLE_CONTENT_RECT = QRect(202, 166, 765, 909)
HOME_PET_SLEEP_CONTENT_RECT = QRect(24, 176, 592, 288)
HOME_NAV_PAW_CONTENT_RECT = QRect(118, 166, 1019, 943)
HOME_NAV_TARGET_CONTENT_RECT = QRect(218, 113, 1379, 636)
HOME_NAV_ARROW_CONTENT_RECT = QRect(178, 169, 668, 1144)
HOME_STATUS_CARD_SIZE = (420, 270)
HOME_STATUS_CARD_RENDER_SCALE = 2
HOME_PET_BACK_WALK_FRAME_TOPS = (68, 73, 79, 73, 57, 47, 47, 61)
HOME_PET_FRONT_CONTACTS = (
    (0.5547, 0.1523, 0.9784),
    (0.5410, 0.1562, 0.9763),
    (0.5098, 0.1523, 0.9720),
    (0.4844, 0.1484, 0.9612),
    (0.6348, 0.5039, 0.9526),
    (0.6309, 0.5156, 0.9591),
    (0.5527, 0.6016, 0.9547),
    (0.5078, 0.6211, 0.9440),
)
HOME_PET_BACK_CONTACTS = (
    (0.4102, 0.1250, 0.9806),
    (0.3779, 0.1230, 0.9828),
    (0.3555, 0.1211, 0.9828),
    (0.3438, 0.1055, 0.9806),
    (0.3887, 0.1211, 0.9828),
    (0.3857, 0.2988, 0.9828),
    (0.4053, 0.3965, 0.9806),
    (0.3613, 0.3633, 0.9828),
)
HOME_SCENE_CORNER_RADIUS = 24
HOME_DECORATION_SIDEBAR_WIDTH = 338
HOME_DECORATION_CARD_HEIGHT = 154
HOME_DECORATION_CARD_STEP = 162
HOME_DECORATION_THUMBNAIL_HEIGHT = 78
HOME_DECORATION_CATEGORY_TOP = 48
HOME_DECORATION_CARD_TOP = 90
HOME_SELECTION_BORDER_COLOR = "#a65f47"
HOME_SELECTION_FILL_COLOR = QColor(255, 236, 205, 88)
HOME_SELECTION_HANDLE_COLOR = "#fff8ed"
HOME_FURNITURE_PATHS = {
    "home_rug": os.path.join(HOME_FURNITURE_DIR, "rug.png"),
    "home_sofa": os.path.join(HOME_FURNITURE_DIR, "sofa.png"),
    "home_plant": os.path.join(HOME_FURNITURE_DIR, "plant.png"),
    "home_wall_art": os.path.join(HOME_FURNITURE_DIR, "wall-art.png"),
}
HOME_DECORATION_CATEGORIES = (
    ("all", "全部"),
    ("rug", "地毯"),
    ("sofa", "沙发"),
    ("plant", "绿植"),
    ("wall_art", "墙饰"),
)
HOME_DECORATION_CATEGORY_BY_ID = {
    "home_rug": "rug",
    "home_sofa": "sofa",
    "home_plant": "plant",
    "home_wall_art": "wall_art",
    "home_status_card": "wall_art",
}


def home_status_card_value_rects(size=HOME_STATUS_CARD_SIZE):
    """Return logical value columns wide enough for a full 100% label."""

    width = int(size[0])
    return tuple(
        QRectF(width - 98, 80 + index * 57, 68, 45)
        for index in range(3)
    )


def render_home_status_card(state, size=HOME_STATUS_CARD_SIZE):
    """Render a crisp, live wall card with only the pet name and three stats."""

    width, height = (int(size[0]), int(size[1]))
    pixmap = QPixmap(
        width * HOME_STATUS_CARD_RENDER_SCALE,
        height * HOME_STATUS_CARD_RENDER_SCALE,
    )
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    painter.scale(HOME_STATUS_CARD_RENDER_SCALE, HOME_STATUS_CARD_RENDER_SCALE)

    shadow = QRectF(7, 9, width - 14, height - 15)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(105, 67, 48, 42))
    painter.drawRoundedRect(shadow, 24, 24)

    card = QRectF(4, 4, width - 14, height - 15)
    background = QLinearGradient(card.topLeft(), card.bottomRight())
    background.setColorAt(0.0, QColor("#fffdf6"))
    background.setColorAt(1.0, QColor("#fff1df"))
    painter.setBrush(background)
    painter.setPen(QPen(QColor("#edc4aa"), 2.5))
    painter.drawRoundedRect(card, 24, 24)

    font = painter.font()
    font.setFamily("Microsoft YaHei")
    font.setPixelSize(26)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#7b4d3a"))
    name = str(state.get("pet_name", "小狗")).strip() or "小狗"
    painter.drawText(QRectF(28, 18, width - 56, 38), Qt.AlignVCenter, name)
    painter.setPen(QPen(QColor("#f4ba95"), 1.5))
    painter.drawLine(QPointF(28, 65), QPointF(width - 30, 65))

    stats = (
        ("饱腹", state.get("hunger", 0), QColor("#f2a166")),
        ("心情", state.get("mood", 0), QColor("#ef91a2")),
        ("精力", state.get("energy", 0), QColor("#9a8bd5")),
    )
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)
    value_rects = home_status_card_value_rects(size)
    for index, (label, raw_value, color) in enumerate(stats):
        try:
            value = max(0.0, min(100.0, float(raw_value)))
        except (TypeError, ValueError, OverflowError):
            value = 0.0
        top = 80 + index * 57
        row = QRectF(22, top, width - 44, 45)
        tint = QColor(color)
        tint.setAlpha(32)
        painter.setBrush(tint)
        painter.setPen(QPen(QColor(color).lighter(125), 1.2))
        painter.drawRoundedRect(row, 15, 15)
        icon = QRectF(32, top + 7, 31, 31)
        painter.setBrush(QColor(255, 255, 255, 210))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(icon)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(icon.center().x() - 7, icon.center().y() - 7, 14, 14))
        painter.setPen(QColor("#79584a"))
        painter.drawText(QRectF(75, top, 54, 45), Qt.AlignVCenter, label)
        value_rect = value_rects[index]
        track = QRectF(134, top + 18, value_rect.left() - 148, 11)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f4e4d9"))
        painter.drawRoundedRect(track, 5.5, 5.5)
        fill = QRectF(track.left(), track.top(), track.width() * value / 100.0, track.height())
        painter.setBrush(color)
        painter.drawRoundedRect(fill, 5.5, 5.5)
        painter.setPen(QColor("#8f6857"))
        painter.drawText(
            value_rect,
            Qt.AlignRight | Qt.AlignVCenter,
            f"{int(round(value))}%",
        )
    painter.end()
    return pixmap


@dataclass(frozen=True)
class HomePetWalkRenderSpec:
    pixmap: QPixmap
    source_rect: QRect
    mirrored: bool
    frame_index: int
    visual_scale: float
    contact_center_x: float
    contact_width: float
    contact_foot_y: float


def home_pet_static_source_rect(pixmap: QPixmap) -> QRect:
    """Return visible alpha bounds for a non-spritesheet pixmap."""

    if pixmap is None or pixmap.isNull():
        return QRect()
    full = QRect(0, 0, pixmap.width(), pixmap.height())
    visible = QRegion(pixmap.mask()).boundingRect()
    return visible if not visible.isEmpty() else full


def home_pet_walk_source_rect(frame_index: int) -> QRect:
    """Return the shared content crop for one authored walk-sheet frame."""

    index = int(frame_index) % HOME_PET_WALK_FRAME_COUNT
    column = index % 3
    row = index // 3
    return HOME_PET_WALK_CONTENT_RECT.translated(
        column * HOME_PET_WALK_FRAME_SIZE,
        row * HOME_PET_WALK_FRAME_SIZE,
    )


def home_pet_sleep_source_rect(frame_index: int) -> QRect:
    """Return the shared content crop for one authored sleep-sheet frame."""

    index = int(frame_index) % HOME_PET_SLEEP_FRAME_COUNT
    column = index % 3
    row = index // 3
    return HOME_PET_SLEEP_CONTENT_RECT.translated(
        column * HOME_PET_SLEEP_FRAME_SIZE,
        row * HOME_PET_SLEEP_FRAME_SIZE,
    )


def home_pet_back_walk_source_rect(frame_index: int) -> QRect:
    """Return a back-walk crop with every visible footline aligned."""

    index = int(frame_index) % HOME_PET_WALK_FRAME_COUNT
    column = index % 3
    row = index // 3
    return QRect(
        column * HOME_PET_WALK_FRAME_SIZE + 64,
        row * HOME_PET_WALK_FRAME_SIZE + HOME_PET_BACK_WALK_FRAME_TOPS[index],
        512,
        464,
    )


def home_pet_frame_contact(direction: str, frame_index: int):
    """Return the authored foot-contact patch for one rendered frame."""

    index = int(frame_index) % HOME_PET_WALK_FRAME_COUNT
    contacts = (
        HOME_PET_FRONT_CONTACTS
        if direction in {"front_left", "front_right"}
        else HOME_PET_BACK_CONTACTS
    )
    center_x, width, foot_y = contacts[index]
    if direction in {"front_left", "back_left"}:
        center_x = round(1.0 - center_x, 4)
    return center_x, width, foot_y


def home_pet_shadow_rect(body: QRectF, contact) -> QRectF:
    """Return a shallow contact shadow aligned with the sprite's visible paws."""

    center_ratio, width_ratio, foot_ratio = contact
    width = max(
        body.width() * 0.32,
        min(body.width() * 0.72, body.width() * width_ratio * 1.15),
    )
    height = body.height() * 0.055
    center_x = body.left() + body.width() * center_ratio
    center_y = (
        body.top() + body.height() * foot_ratio - body.height() * 0.015
    )
    return QRectF(
        center_x - width / 2.0,
        center_y - height / 2.0,
        width,
        height,
    )


def home_destination_opacity(fade_started_at, now: float) -> float:
    """Return the remaining marker opacity during its arrival fade."""

    if fade_started_at is None:
        return 1.0
    elapsed = max(0.0, float(now) - float(fade_started_at))
    if elapsed + 1e-9 >= HOME_DESTINATION_FADE_SECONDS:
        return 0.0
    return 1.0 - elapsed / HOME_DESTINATION_FADE_SECONDS


def board_geometry(screen_rect: QRect) -> QRect:
    """Return the fixed lower-right board rectangle for the active screen."""
    return scene_rect_for_screen(
        screen_rect,
        screen_rect.width() - HOME_VIEWPORT_SIZE[0],
        screen_rect.height() - HOME_VIEWPORT_SIZE[1],
    )


def scene_window_geometry(screen_rect: QRect) -> QRect:
    """Return a window that reserves a left-only sidebar beside the canvas."""
    board = board_geometry(screen_rect)
    return QRect(
        board.x() - HOME_DECORATION_SIDEBAR_WIDTH,
        board.y(),
        board.width() + HOME_DECORATION_SIDEBAR_WIDTH,
        board.height(),
    )
