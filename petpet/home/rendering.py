"""Pure visual constants and rendering helpers for the home scene."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from PyQt5.QtCore import QPointF, QRect, QRectF, Qt
from PyQt5.QtGui import (
    QBitmap,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRegion,
)

from petpet.app.paths import (
    HOME_BUTTONS_DIR,
    HOME_FURNITURE_DIR,
    HOME_POSES_DIR,
    HOME_SCENES_DIR,
)
from petpet.progression import core as progression
from petpet.home.geometry import (
    HOME_VIEWPORT_SIZE,
    HOME_WORLD_SIZE,
    scene_rect_for_screen,
)


SCENES_DIR = HOME_SCENES_DIR
HOME_BACKGROUND_PATH = os.path.join(SCENES_DIR, "home_background.png")
HOME_BACKGROUND_MODE = "flattened_midground"
HOME_PET_WALK_DOWN_PATH = os.path.join(HOME_POSES_DIR, "home_pet_walk_down.png")
HOME_PET_WALK_BACK_RIGHT_PATH = os.path.join(
    HOME_POSES_DIR, "home_pet_walk_back_right.png"
)
HOME_PET_IDLE_PATH = os.path.join(HOME_POSES_DIR, "home_pet_idle_sit.png")
HOME_PET_SLEEP_PATH = os.path.join(HOME_POSES_DIR, "home_pet_sleep.png")
HOME_NAV_PAW_PATH = os.path.join(SCENES_DIR, "home_nav_paw.png")
HOME_NAV_TARGET_PATH = os.path.join(SCENES_DIR, "home_nav_target.png")
HOME_NAV_ARROW_PATH = os.path.join(SCENES_DIR, "home_nav_arrow.png")
HOME_TOGGLE_SIZE = (46, 46)
HOME_BUTTON_SIZE = (130, 52)
HOME_BUTTON_PATHS = {
    name: os.path.join(HOME_BUTTONS_DIR, f"{name}.png")
    for name in (
        "interaction_toggle",
        "menu_toggle",
        "pet",
        "feed",
        "play",
        "sleep",
        "shop",
        "pets",
        "decorate",
        "exit",
    )
}
HOME_PET_WALK_FRAME_SIZE = 640
HOME_PET_WALK_FRAME_COUNT = 8
HOME_PET_WALK_FPS = 8.0
HOME_PET_SLEEP_FRAME_SIZE = 640
HOME_PET_SLEEP_FRAME_COUNT = 8
HOME_PET_SLEEP_FPS = 3.0
HOME_PET_SLEEP_VISUAL_SCALE = 0.60
# Furniture whose placed footprint blocks the pet's movement.
HOME_SOLID_OBSTACLES = ("home_sofa", "home_plant")
# Fraction of the sprite frame that actually blocks movement:
# horizontal half-extent ratio and the solid vertical band (top/bottom
# ratios of the half-height around the center).
HOME_SOLID_OBSTACLE_INSETS = {
    "home_sofa": (0.34, 0.05, 0.92),
    "home_plant": (0.18, 0.25, 0.95),
}
HOME_PET_DEFAULT_SLEEP_VISUAL_SCALE = 0.50
HOME_PET_FIXED_DEPTH_SCALE = 1.08
HOME_DESTINATION_FADE_SECONDS = 0.35
HOME_PET_WALK_CONTENT_RECT = QRect(64, 80, 512, 464)
HOME_PET_IDLE_CONTENT_RECT = QRect(202, 166, 765, 909)
HOME_PET_SLEEP_CONTENT_RECT = QRect(24, 176, 592, 288)
HOME_NAV_PAW_CONTENT_RECT = QRect(118, 166, 1019, 943)
HOME_NAV_TARGET_CONTENT_RECT = QRect(218, 113, 1379, 636)
HOME_NAV_ARROW_CONTENT_RECT = QRect(178, 169, 668, 1144)
HOME_STATUS_CARD_SIZE = (420, 278)
HOME_STATUS_CARD_RENDER_SCALE = 2
# 状态卡新底板（2026-09-13 用户定稿素材：暖木挂牌 + 三条凹槽）。
_STATUS_CARD_ART_PATH = os.path.join(SCENES_DIR, "status_card.png")
# 凹槽区（按 status_card.png 420×278 实测，y 区间 × 横向布局）：
# 三槽 y 95-135 / 147-186 / 199-238，左侧圆图标 cx≈70，槽内右缘 x≈378。
STATUS_CARD_GROOVES = (
    QRectF(52, 95, 328, 40),
    QRectF(52, 147, 328, 40),
    QRectF(52, 199, 328, 40),
)
STATUS_CARD_GROOVE_ICON_CX = 71
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
    "home_wall_art": os.path.join(HOME_FURNITURE_DIR, "wall_art.png"),
    # 家具扩充（2026-09-10）。
    "home_lamp": os.path.join(HOME_FURNITURE_DIR, "lamp.png"),
    "home_bookshelf": os.path.join(HOME_FURNITURE_DIR, "bookshelf.png"),
    "home_round_table": os.path.join(
        HOME_FURNITURE_DIR, "round_table.png"),
    "home_toy_basket": os.path.join(
        HOME_FURNITURE_DIR, "toy_basket.png"),
    # 家具第二批（2026-09-12）。
    "home_wall_clock": os.path.join(HOME_FURNITURE_DIR, "clock.png"),
    "home_cat_tree": os.path.join(HOME_FURNITURE_DIR, "cat_tree.png"),
    "home_pet_bed": os.path.join(HOME_FURNITURE_DIR, "pet_bed.png"),
    "home_rocking_chair": os.path.join(
        HOME_FURNITURE_DIR, "rocking_chair.png"),
}
# 分栏合并（2026-09-10）：7 类归并为 家具/装饰/玩具。
HOME_DECORATION_CATEGORIES = (
    ("all", "全部"),
    ("furniture", "家具"),
    ("decor", "装饰"),
    ("toy", "玩具"),
)
HOME_DECORATION_CATEGORY_BY_ID = {
    "home_rug": "decor",
    "home_sofa": "furniture",
    "home_plant": "decor",
    "home_wall_art": "decor",
    "home_status_card": "decor",
    "home_lamp": "furniture",
    "home_bookshelf": "furniture",
    "home_round_table": "furniture",
    "home_toy_basket": "toy",
    # 家具第二批（2026-09-12）：挂钟归装饰（墙面）、猫爬架归玩具，
    # 软垫小床与摇椅归家具。
    "home_wall_clock": "decor",
    "home_cat_tree": "toy",
    "home_pet_bed": "furniture",
    "home_rocking_chair": "furniture",
}


_STATUS_CARD_CACHE: dict[str, object] = {}


def render_home_status_card(state, size=HOME_STATUS_CARD_SIZE):
    """Render a crisp, live wall card; cached until its content changes."""

    profile = None
    pets = state.get("pets")
    if isinstance(pets, dict):
        profile = pets.get(state.get("active_pet_id"))
    values = profile if isinstance(profile, dict) else state
    signature = (
        values.get("pet_name", state.get("pet_name", "")),
        int(values.get("hunger", 0) or 0),
        int(values.get("mood", 0) or 0),
        int(values.get("energy", 0) or 0),
        size,
    )
    cached = _STATUS_CARD_CACHE.get("pixmap")
    if cached is not None and _STATUS_CARD_CACHE.get("signature") == signature:
        return cached
    pixmap = _render_status_card_uncached(state, size)
    _STATUS_CARD_CACHE["signature"] = signature
    _STATUS_CARD_CACHE["pixmap"] = pixmap
    return pixmap


_STATUS_CARD_ART_CACHE = {}


def render_status_card_art(size=HOME_STATUS_CARD_SIZE):
    """状态卡底板图（用户定稿素材，无任何文字）。

    家园场景按显示尺寸取图后**以场景画笔实时叠画状态内容**——
    文字按最终显示分辨率栅格化，不经过位图缩放，任何缩放下都清晰
    （2026-09-14 模糊修复核心）。
    """
    key = (int(size[0]), int(size[1]))
    art = _STATUS_CARD_ART_CACHE.get(key)
    if art is None:
        art = QPixmap(_STATUS_CARD_ART_PATH)
        if not art.isNull() and (art.width(), art.height()) != key:
            art = art.scaled(
                key[0], key[1], Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
        _STATUS_CARD_ART_CACHE[key] = art
    return art


def draw_status_card_overlay(painter, state, size=HOME_STATUS_CARD_SIZE):
    """在已画好的状态卡底板上实时绘制状态内容（圆点/标签/进度条）。

    由家园场景以场景画笔直接调用：文字按最终显示分辨率栅格化。
    无名字、无百分比（2026-09-14 用户修订）。
    """
    painter.save()
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = painter.font()
    font.setFamily("Microsoft YaHei")
    stats = (
        ("饱腹", state.get("hunger", 0), QColor("#f2a166")),
        ("心情", state.get("mood", 0), QColor("#ef91a2")),
        ("精力", state.get("energy", 0), QColor("#9a8bd5")),
    )
    for index, (label, raw_value, color) in enumerate(stats):
        try:
            value = max(0.0, min(100.0, float(raw_value)))
        except (TypeError, ValueError, OverflowError):
            value = 0.0
        groove = STATUS_CARD_GROOVES[index]
        center_y = groove.center().y()
        # 槽内左圆是图里自带的图标位：点一颗状态色圆点。
        painter.setPen(QPen(QColor(255, 252, 246, 220), 1.5))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(
            STATUS_CARD_GROOVE_ICON_CX - 9, center_y - 9, 18, 18))
        # 2026-09-14 模糊二修（用户方向）：去加粗（小字号粗体中文
        # 笔画粘连发糊）+ 21px + 像素网格对齐（半像素偏移会让小字
        # 发虚——y 取整，文字矩形贴整数栅格）。
        font.setPixelSize(21)
        font.setBold(False)
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#5a3d28"))
        text_y = round(center_y) - 11
        painter.drawText(
            QRectF(88, text_y, 60, 22), Qt.AlignVCenter, label)
        track = QRectF(152, center_y - 7, 216, 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(120, 82, 60, 40))
        painter.drawRoundedRect(track, 7, 7)
        fill = QRectF(
            track.left(), track.top(),
            track.width() * value / 100.0, track.height(),
        )
        painter.setBrush(color)
        painter.drawRoundedRect(fill, 7, 7)
    painter.restore()


def _render_status_card_uncached(state, size=HOME_STATUS_CARD_SIZE):

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

    art = render_status_card_art((width, height))
    if not art.isNull():
        painter.drawPixmap(
            QRectF(0, 0, width, height), art,
            QRectF(0, 0, art.width(), art.height()),
        )
    draw_status_card_overlay(painter, state, size)
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


def home_pet_animation_source_rect(frames) -> QRect:
    """Return one thresholded alpha crop shared by an animation sequence."""

    visible_union = QRect()
    fallback = QRect()
    for pixmap in frames or ():
        if pixmap is None or pixmap.isNull():
            continue
        if fallback.isEmpty():
            fallback = home_pet_static_source_rect(pixmap)
        alpha_mask = pixmap.toImage().createAlphaMask(Qt.ThresholdDither)
        visible = QRegion(QBitmap.fromImage(alpha_mask)).boundingRect()
        if visible.isEmpty():
            continue
        visible_union = (
            visible
            if visible_union.isEmpty()
            else visible_union.united(visible)
        )
    return visible_union if not visible_union.isEmpty() else fallback


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
        if direction in {"front", "front_left", "front_right", "left", "right"}
        else HOME_PET_BACK_CONTACTS
    )
    center_x, width, foot_y = contacts[index]
    if direction in {"front_left", "back_left", "left"}:
        center_x = round(1.0 - center_x, 4)
    return center_x, width, foot_y


def home_pet_shadow_rect(body: QRectF, contact) -> QRectF:
    """Return a shallow contact shadow aligned with the sprite's visible paws."""

    center_ratio, width_ratio, foot_ratio = contact
    width = max(
        body.width() * 0.32,
        min(body.width() * 0.85, body.width() * width_ratio * 1.15),
    )
    height = body.height() * 0.115
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


def decoration_scene_window_geometry(screen_rect: QRect) -> QRect:
    """全景装修窗口（2026-09-10）：左栏 + 整幅世界 1:1 展示，无需平移。"""
    board = board_geometry(screen_rect)
    width = HOME_DECORATION_SIDEBAR_WIDTH + HOME_WORLD_SIZE[0]
    x = max(screen_rect.left(), board.right() + 1 - width)
    return QRect(x, board.y(), width, board.height())
