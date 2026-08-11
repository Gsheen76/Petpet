"""Home scene board, furniture rendering, and viewport coordination."""

from __future__ import annotations

import os
import math
import time
from dataclasses import dataclass

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from app_paths import ASSETS_DIR
import progression
from home_pet import (
    HOME_DEFAULT_SLEEP_POINT,
    HomePetController,
    clamp_to_walkable,
    load_home_pet_position,
    route_footprints,
    serialize_home_pet_position,
)
from scene_system import (
    HOME_CAMERA_PAN_STEP,
    HOME_CAMERA_REPEAT_STEP,
    HOME_VIEWPORT_SIZE,
    camera_x_for_dog,
    home_decoration_bounds,
    home_decoration_handles,
    pan_viewport_x,
    rotation_from_pointer,
    scene_rect_for_screen,
    scale_from_handle,
)


SCENES_DIR = os.path.join(ASSETS_DIR, "scenes", "home")
HOME_BACKGROUND_PATH = os.path.join(SCENES_DIR, "home-background.png")
HOME_BACKGROUND_MODE = "flattened_midground"
HOME_PET_WALK_DOWN_PATH = os.path.join(SCENES_DIR, "home-pet-walk-down.png")
HOME_PET_WALK_BACK_RIGHT_PATH = os.path.join(
    SCENES_DIR, "home-pet-walk-back-right.png"
)
HOME_PET_IDLE_PATH = os.path.join(SCENES_DIR, "home-pet-idle-sit.png")
HOME_PET_SLEEP_PATH = os.path.join(SCENES_DIR, "home-pet-sleep.png")
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
    "home_rug": os.path.join(SCENES_DIR, "rug.png"),
    "home_sofa": os.path.join(SCENES_DIR, "sofa.png"),
    "home_plant": os.path.join(SCENES_DIR, "plant.png"),
    "home_wall_art": os.path.join(SCENES_DIR, "wall-art.png"),
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
}


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


class HomeSceneWindow(QWidget):
    """Fixed home board rendered behind the independent PetWindow."""

    def __init__(self, pet, save_state):
        super().__init__()
        self.pet = pet
        self.state = pet.state
        self.save_state = save_state
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedHeight(HOME_VIEWPORT_SIZE[1])
        self.background = QPixmap(HOME_BACKGROUND_PATH)
        self.home_pet_walk_down = QPixmap(HOME_PET_WALK_DOWN_PATH)
        self.home_pet_walk_back_right = QPixmap(HOME_PET_WALK_BACK_RIGHT_PATH)
        self.home_pet_idle = QPixmap(HOME_PET_IDLE_PATH)
        self.home_pet_sleep = QPixmap(HOME_PET_SLEEP_PATH)
        self.home_nav_paw = QPixmap(HOME_NAV_PAW_PATH)
        self.home_nav_target = QPixmap(HOME_NAV_TARGET_PATH)
        self.home_nav_arrow = QPixmap(HOME_NAV_ARROW_PATH)
        self.furniture = {
            item_id: QPixmap(path)
            for item_id, path in HOME_FURNITURE_PATHS.items()
        }
        self._manual_destination = None
        self._manual_route = None
        self._destination_fade_started_at = None
        self._reset_home_pet_controller()
        self._dragging_item = None
        self._drag_offset = QPoint()
        self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        self._manual_camera = False
        self._pan_direction = None
        self._selected_furniture = None
        self._editing_gesture = None
        self._decoration_category = "all"
        self._last_pet_tick = time.monotonic()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sync_scene)
        self._timer.start(33)
        self._pan_timer = QTimer(self)
        self._pan_timer.setInterval(55)
        self._pan_timer.timeout.connect(self._repeat_pan)
        self._sync_scene()

    def _screen_rect(self):
        try:
            return self.pet.current_screen_rect()
        except (AttributeError, RuntimeError):
            return self.screen().availableGeometry()

    def _sync_scene(self):
        if not self.isVisible():
            return
        rect = scene_window_geometry(self._screen_rect())
        if self.geometry() != rect:
            self.setGeometry(rect)
        self._advance_home_pet(time.monotonic())
        if not self.is_decorating() or not self._manual_camera:
            self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        follow = getattr(self.pet, "follow_interface_overlays", None)
        if callable(follow):
            follow()
        self.update()

    def scene_canvas_rect(self):
        """Return the right-hand scene canvas in this window's local coordinates."""
        return QRect(
            max(0, self.width() - HOME_VIEWPORT_SIZE[0]),
            0,
            HOME_VIEWPORT_SIZE[0],
            self.height(),
        )

    def _scene_content_offset(self):
        return self.scene_canvas_rect().x()

    def home_pet_visible(self):
        """Return whether the in-scene pet should be rendered."""

        return self.isVisible() and not self.is_decorating()

    def _reset_home_pet_controller(self):
        position = load_home_pet_position(
            self.state.get("home_scene"),
            self.state.get("home_scene_dog_world_x"),
        )
        self.home_pet = HomePetController(position)
        if self.state.get("sleeping"):
            self.home_pet.set_sleeping()

    def _save_home_pet_position(self):
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["pet_position"] = serialize_home_pet_position(
            self.home_pet.position
        )
        self.save_state(self.state)

    def _clear_manual_destination(self):
        self._manual_destination = None
        self._manual_route = None
        self._destination_fade_started_at = None

    def _set_manual_destination(self, target):
        """Capture one immutable world-space route for a manual command."""

        if target is None:
            self._clear_manual_destination()
            return
        start = tuple(float(value) for value in self.home_pet.position)
        end = tuple(float(value) for value in target)
        self._manual_destination = end
        self._manual_route = {
            "start": start,
            "end": end,
            "footprints": route_footprints(start, end),
        }
        self._destination_fade_started_at = None

    def _expire_manual_destination(self, now):
        if (
            self._manual_destination is not None
            and home_destination_opacity(
                self._destination_fade_started_at,
                now,
            ) <= 0.0
        ):
            self._clear_manual_destination()

    def _home_pet_energy(self):
        try:
            energy = float(self.state.get("energy", 100.0))
        except (TypeError, ValueError, OverflowError):
            return 100.0
        return energy if math.isfinite(energy) else 100.0

    def home_sleep_target(self):
        """Return the current rug center or the authored fallback sleep point."""

        if (
            "home_rug" not in self.state.get("owned_home_decorations", [])
            or "home_rug" in self.state.get("home_stored_decorations", [])
        ):
            return HOME_DEFAULT_SLEEP_POINT
        pixmap = self.furniture.get("home_rug")
        if pixmap is None or pixmap.isNull():
            return HOME_DEFAULT_SLEEP_POINT
        try:
            position = progression.home_decoration_position(
                self.state, "home_rug"
            )
            target = (
                float(position["x"]) + pixmap.width() / 2.0,
                float(position["y"]) + pixmap.height() / 2.0,
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return HOME_DEFAULT_SLEEP_POINT
        if not all(math.isfinite(value) for value in target):
            return HOME_DEFAULT_SLEEP_POINT
        return clamp_to_walkable(target)

    def toggle_home_sleep(self, now=None):
        """Wake in place or walk to the current home sleep target."""

        if not self.home_pet_visible() or self.is_decorating():
            return False
        current = time.monotonic() if now is None else float(now)
        if self.home_pet.state == "sleeping" or self.state.get("sleeping"):
            self.home_pet.target = None
            self.home_pet.state = "idle"
            self.home_pet.sleep_retry_until = current + 45.0
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self._clear_manual_destination()
            self._save_home_pet_position()
            say = getattr(self.pet, "say", None)
            if callable(say):
                say("醒来啦！又可以陪主人了～", 2000)
            sound = getattr(self.pet, "play_sound", None)
            if callable(sound):
                sound("bark")
            self.update()
            return True

        self.home_pet.cancel_target()
        target = self.home_sleep_target()
        if not self.home_pet.request_manual_sleep(target, current):
            return False
        self.state["sleeping"] = False
        self.state["sleep_mode"] = None
        self._set_manual_destination(target)
        say = getattr(self.pet, "say", None)
        if callable(say):
            say("去小垫子上睡觉啦～", 2200)
        self.update()
        return True

    def _advance_home_pet(self, now=None):
        """Advance the in-scene pet and synchronize shared sleep transitions."""

        current = time.monotonic() if now is None else float(now)
        self._expire_manual_destination(current)
        elapsed = max(0.0, current - self._last_pet_tick)
        self._last_pet_tick = current
        if self.is_decorating():
            return ()

        energy = self._home_pet_energy()
        wake_threshold = float(
            getattr(self.pet, "auto_wake_energy_threshold", 80.0)
        )
        if (
            self.state.get("sleep_mode") == "auto"
            and self.home_pet.wake_if_recovered(energy, wake_threshold)
        ):
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self._save_home_pet_position()
            return ()

        sleep_threshold = float(
            getattr(self.pet, "auto_sleep_energy_threshold", 30.0)
        )
        if self.home_pet.state == "idle" and energy < sleep_threshold:
            self.home_pet.request_auto_sleep(
                self.home_sleep_target(), current
            )

        events = self.home_pet.advance(elapsed)
        if "manual_sleep_started" in events:
            self.state["sleeping"] = True
            self.state["sleep_mode"] = "manual"
            progression.record_sleep(self.state, "manual")
            if self._manual_destination is not None:
                self._destination_fade_started_at = current
            self._save_home_pet_position()
            sound = getattr(self.pet, "play_sound", None)
            if callable(sound):
                sound("sleep")
        elif "sleep_started" in events:
            self.state["sleeping"] = True
            self.state["sleep_mode"] = "auto"
            progression.record_sleep(self.state, "auto")
            self._save_home_pet_position()
        elif "arrived" in events:
            if self._manual_destination is not None:
                self._destination_fade_started_at = current
            self._save_home_pet_position()
        return events

    def pan_view(self, direction, step=HOME_CAMERA_PAN_STEP):
        """Pan the authored world viewport and persist the new camera position."""
        if not self.view_pan_enabled():
            return self._camera_x
        self._camera_x = pan_viewport_x(self._camera_x, direction, step)
        self._manual_camera = True
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["viewport_x"] = self._camera_x
        home_scene["viewport_pinned"] = True
        self.save_state(self.state)
        self.update()
        return self._camera_x

    def begin_pan(self, direction):
        if direction not in ("left", "right") or not self.view_pan_enabled():
            return
        self._pan_direction = direction
        self.pan_view(direction)
        self._pan_timer.start()

    def _repeat_pan(self):
        if self._pan_direction is not None:
            self.pan_view(self._pan_direction, HOME_CAMERA_REPEAT_STEP)

    def end_pan(self):
        self._pan_direction = None
        self._pan_timer.stop()

    def _set_pet_visible(self, visible):
        action = getattr(self.pet, "show" if visible else "hide", None)
        if callable(action):
            action()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        canvas = self.scene_canvas_rect()
        clip = QPainterPath()
        clip.addRoundedRect(
            QRectF(canvas), HOME_SCENE_CORNER_RADIUS, HOME_SCENE_CORNER_RADIUS
        )
        painter.setClipPath(clip)
        painter.fillRect(canvas, QColor("#f3dfc4"))
        if not self.background.isNull():
            source = QRect(self._camera_x, 0, canvas.width(), canvas.height())
            painter.drawPixmap(canvas, self.background, source)
        for _depth, kind, item_id in self._scene_render_entries():
            if kind == "pet":
                self._draw_home_pet(painter)
                continue
            if kind == "navigation":
                self._draw_navigation_feedback(painter)
                continue
            position = self.state.get("home_decoration_positions", {}).get(
                item_id, {}
            )
            self._draw_furniture(painter, item_id, position)
        if self.is_decorating() and self._selected_furniture is not None:
            self._draw_selection(painter, self._selected_furniture)
        if self.view_pan_enabled():
            self._draw_scene_button(painter, self.left_view_button_rect(), "左移")
            self._draw_scene_button(painter, self.right_view_button_rect(), "右移")
        self._draw_scene_button(painter, self.decoration_button_rect(), "装修")
        self._draw_scene_button(painter, self.exit_button_rect(), "退出")
        painter.restore()
        if self.is_decorating():
            self._draw_decoration_panel(painter)
        painter.end()

    def show_scene(self):
        progression.ensure_progression(self.state)
        self._clear_manual_destination()
        self._reset_home_pet_controller()
        self.state.setdefault("home_scene", {})["enabled"] = True
        saved_scene = self.state["home_scene"]
        saved_scene["decorating"] = False
        saved_scene["viewport_pinned"] = False
        self._manual_camera = False
        self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
        hide_overlays = getattr(self.pet, "hide_overlays", None)
        if callable(hide_overlays):
            hide_overlays()
        self._set_pet_visible(False)
        self.show()
        self.raise_()
        self._sync_scene()
        self.save_state(self.state)

    def hide_scene(self):
        self.state.setdefault("home_scene", {})["enabled"] = False
        hide_overlays = getattr(self.pet, "hide_overlays", None)
        if callable(hide_overlays):
            hide_overlays()
        self.end_pan()
        self.state["home_scene"]["decorating"] = False
        self._selected_furniture = None
        self._clear_manual_destination()
        self.home_pet.cancel_target()
        self._save_home_pet_position()
        self.hide()
        self._set_pet_visible(True)
        raise_pet = getattr(self.pet, "raise_", None)
        if callable(raise_pet):
            raise_pet()

    def exit_button_rect(self):
        width = 58
        height = 38
        margin = 14
        canvas = self.scene_canvas_rect()
        return QRect(
            canvas.right() - margin - width + 1,
            margin,
            width,
            height,
        )

    def decoration_button_rect(self):
        width = 66
        height = 38
        gap = 8
        margin = 14
        canvas = self.scene_canvas_rect()
        return QRect(
            canvas.right() - margin - 58 - gap - width + 1,
            margin,
            width,
            height,
        )

    def left_view_button_rect(self):
        return QRect(
            self._scene_content_offset() + 14,
            max(14, (self.height() - 44) // 2),
            68,
            44,
        )

    def right_view_button_rect(self):
        canvas = self.scene_canvas_rect()
        return QRect(
            canvas.right() - 68 + 1,
            max(14, (self.height() - 44) // 2),
            68,
            44,
        )

    def decoration_panel_close_button_rect(self):
        panel = self._panel_rect()
        size = 30
        margin = 10
        return QRect(
            panel.right() - margin - size + 1,
            panel.top() + margin,
            size,
            size,
        )

    @staticmethod
    def scene_button_label(button):
        return {
            "left": "左移",
            "right": "右移",
            "decorate": "装修",
            "exit": "退出",
        }.get(button, "")

    def _draw_scene_button(self, painter, rect, label):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(68, 45, 38, 112))
        painter.drawRoundedRect(rect.adjusted(1, 3, 1, 3), 12, 12)
        painter.setBrush(QColor("#a96751"))
        painter.drawRoundedRect(rect, 12, 12)
        painter.setPen(QPen(QColor("#f9ddbc"), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 11, 11)
        painter.setPen(QColor("#fff8ed"))
        painter.drawText(rect, Qt.AlignCenter, label)

    def is_decorating(self):
        return bool(self.state.get("home_scene", {}).get("decorating", False))

    def view_pan_enabled(self):
        """Manual home viewport controls are available only while decorating."""
        return self.is_decorating()

    def toggle_decoration_mode(self):
        decorating = not self.is_decorating()
        home_scene = self.state.setdefault("home_scene", {})
        home_scene["decorating"] = decorating
        if decorating:
            hide_overlays = getattr(self.pet, "hide_overlays", None)
            if callable(hide_overlays):
                hide_overlays()
            self._clear_manual_destination()
            self.home_pet.cancel_target()
            self._manual_camera = True
            home_scene["viewport_x"] = self._camera_x
            home_scene["viewport_pinned"] = True
        else:
            self.end_pan()
            self._manual_camera = False
            home_scene["viewport_pinned"] = False
            self._camera_x = camera_x_for_dog(self.home_pet.position[0], 0)
            self._selected_furniture = None
            self._dragging_item = None
            self._editing_gesture = None
        self.save_state(self.state)
        self.update()
        return decorating

    def select_furniture(self, decoration_id):
        if decoration_id in self.state.get("owned_home_decorations", []):
            self._selected_furniture = decoration_id
            self.update()

    def store_furniture(self, decoration_id):
        if not self.is_decorating():
            return False
        result = progression.store_home_decoration(self.state, decoration_id)
        if result:
            if self._selected_furniture == decoration_id:
                self._selected_furniture = None
            self.save_state(self.state)
            self.update()
        return result

    def place_furniture(self, decoration_id):
        if not self.is_decorating():
            return False
        result = progression.place_home_decoration(self.state, decoration_id)
        if result:
            self.save_state(self.state)
            self.update()
        return result

    def adjust_selected_furniture(self, kind, amount):
        if not self.is_decorating() or self._selected_furniture is None:
            return None
        transform = progression.home_decoration_transform(
            self.state, self._selected_furniture
        )
        if kind == "scale":
            transform["scale"] += float(amount)
        elif kind == "rotation":
            transform["rotation"] += float(amount)
        else:
            return None
        result = progression.set_home_decoration_transform(
            self.state, self._selected_furniture, **transform
        )
        self.save_state(self.state)
        self.update()
        return result

    def _draw_furniture(self, painter, decoration_id, position):
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return
        transform = progression.home_decoration_transform(self.state, decoration_id)
        painter.save()
        painter.translate(
            self._scene_content_offset()
            + int(position.get("x", 0))
            - self._camera_x
            + pixmap.width() / 2,
            int(position.get("y", 0)) + pixmap.height() / 2,
        )
        painter.rotate(transform["rotation"])
        painter.scale(transform["scale"], transform["scale"])
        painter.drawPixmap(-pixmap.width() // 2, -pixmap.height() // 2, pixmap)
        painter.restore()

    def home_pet_draw_rect(
        self,
        visual_scale=1.0,
        aspect_ratio=512.0 / 464.0,
    ):
        """Return the home-pet artwork rect anchored to its world-space feet."""

        world_x, world_y = self.home_pet.position
        height = 464.0 * 0.23 * HOME_PET_FIXED_DEPTH_SCALE * visual_scale
        width = height * float(aspect_ratio)
        center_x = self._scene_content_offset() + world_x - self._camera_x
        return QRectF(
            center_x - width / 2.0,
            world_y - height,
            width,
            height,
        )

    def home_pet_render_rect(self, render_spec):
        """Return a foot-anchored rect without stretching the source artwork."""

        if render_spec is None or render_spec.source_rect.height() <= 0:
            return self.home_pet_draw_rect()
        return self.home_pet_draw_rect(
            render_spec.visual_scale,
            render_spec.source_rect.width() / render_spec.source_rect.height(),
        )

    def home_pet_hit_rect(self):
        """Return the local rendered body rectangle used for pointer hits."""

        return self.home_pet_render_rect(self.home_pet_render_spec())

    def home_pet_global_rect(self):
        """Return the rendered home-pet body in global screen coordinates."""

        local = self.home_pet_hit_rect().toAlignedRect()
        return QRect(self.mapToGlobal(local.topLeft()), local.size())

    def open_home_pet_menu(self, point):
        """Open the shared pet menu only when a right-click hits the home pet."""

        if (
            not self.home_pet_visible()
            or self.is_decorating()
            or not self.scene_canvas_rect().contains(point)
            or not self.home_pet_hit_rect().contains(QPointF(point))
        ):
            return False
        opener = getattr(self.pet, "open_bubble_menu", None)
        if not callable(opener):
            return False
        opener()
        return True

    def home_pet_walk_frame(self, now=None):
        """Return the current authored frame, holding frame zero while idle."""

        if self.home_pet.state not in {
            "manual_walk",
            "manual_sleep_walk",
            "auto_sleep_walk",
        }:
            return 0
        current = time.monotonic() if now is None else max(0.0, float(now))
        return int(current * HOME_PET_WALK_FPS) % HOME_PET_WALK_FRAME_COUNT

    def home_pet_sleep_frame(self, now=None):
        """Return the current sleep frame at its deliberately gentle cadence."""

        if self.home_pet.state != "sleeping":
            return 0
        current = time.monotonic() if now is None else max(0.0, float(now))
        return int(current * HOME_PET_SLEEP_FPS) % HOME_PET_SLEEP_FRAME_COUNT

    def home_pet_walk_render_spec(self, now=None):
        """Return all artwork and foot-contact data for the active walk frame."""

        if self.home_pet.state == "sleeping":
            return None
        frame = self.home_pet_walk_frame(now)
        contact = home_pet_frame_contact(self.home_pet.direction, frame)
        if self.home_pet.direction in {"front_left", "front_right"}:
            if self.home_pet_walk_down.isNull():
                return None
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_walk_down,
                source_rect=home_pet_walk_source_rect(frame),
                mirrored=self.home_pet.direction == "front_left",
                frame_index=frame,
                visual_scale=1.0,
                contact_center_x=contact[0],
                contact_width=contact[1],
                contact_foot_y=contact[2],
            )
        if self.home_pet.direction in {"back_left", "back_right"}:
            if self.home_pet_walk_back_right.isNull():
                return None
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_walk_back_right,
                source_rect=home_pet_back_walk_source_rect(frame),
                mirrored=self.home_pet.direction == "back_left",
                frame_index=frame,
                visual_scale=1.06,
                contact_center_x=contact[0],
                contact_width=contact[1],
                contact_foot_y=contact[2],
            )
        return None

    def home_pet_render_spec(self, now=None):
        """Return the authored artwork for the current home-pet state."""

        if self.home_pet.state == "sleeping":
            if self.home_pet_sleep.isNull():
                return None
            frame = self.home_pet_sleep_frame(now)
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_sleep,
                source_rect=home_pet_sleep_source_rect(frame),
                mirrored=False,
                frame_index=frame,
                visual_scale=0.62,
                contact_center_x=0.50,
                contact_width=0.84,
                contact_foot_y=0.98,
            )
        if self.home_pet.state == "idle" and not self.home_pet_idle.isNull():
            return HomePetWalkRenderSpec(
                pixmap=self.home_pet_idle,
                source_rect=HOME_PET_IDLE_CONTENT_RECT,
                mirrored=False,
                frame_index=0,
                visual_scale=1.0,
                contact_center_x=0.55,
                contact_width=0.55,
                contact_foot_y=0.99,
            )
        return self.home_pet_walk_render_spec(now)

    def navigation_feedback(self, now=None):
        """Return transient screen-space path and destination geometry."""

        if self._manual_destination is None or not self.home_pet_visible():
            return None
        current = time.monotonic() if now is None else float(now)
        opacity = home_destination_opacity(
            self._destination_fade_started_at,
            current,
        )
        if opacity <= 0.0:
            return None
        end_x, end_y = self._manual_destination
        route = self._manual_route
        if route is None or route.get("end") != self._manual_destination:
            start = tuple(float(value) for value in self.home_pet.position)
            route = {
                "start": start,
                "end": self._manual_destination,
                "footprints": route_footprints(
                    start,
                    self._manual_destination,
                ),
            }
        start_x, start_y = route["start"]
        offset = self._scene_content_offset() - self._camera_x
        footprint_height = 22.0
        footprint_width = footprint_height * (
            HOME_NAV_PAW_CONTENT_RECT.width()
            / HOME_NAV_PAW_CONTENT_RECT.height()
        )
        footprints = []
        route_dx = end_x - start_x
        route_dy = end_y - start_y
        route_length_sq = route_dx * route_dx + route_dy * route_dy
        pet_x, pet_y = self.home_pet.position
        pet_progress = (
            (pet_x - start_x) * route_dx
            + (pet_y - start_y) * route_dy
        )
        passed_tolerance = 6.0 * math.sqrt(route_length_sq)
        for placement in route["footprints"]:
            footprint_progress = (
                (placement["x"] - start_x) * route_dx
                + (placement["y"] - start_y) * route_dy
            )
            if footprint_progress <= pet_progress + passed_tolerance:
                continue
            center = QPointF(offset + placement["x"], placement["y"])
            footprints.append({
                "rect": QRectF(
                    center.x() - footprint_width / 2.0,
                    center.y() - footprint_height / 2.0,
                    footprint_width,
                    footprint_height,
                ),
                "angle": placement["angle"] + 90.0,
                "mirrored": placement["mirrored"],
            })
        end = QPointF(offset + end_x, end_y)
        pulse = 1.0 + 0.04 * math.sin(current * math.tau / 0.9)
        target_height = 24.0 * pulse
        target_width = target_height * (
            HOME_NAV_TARGET_CONTENT_RECT.width()
            / HOME_NAV_TARGET_CONTENT_RECT.height()
        )
        target_rect = QRectF(
            end.x() - target_width / 2.0,
            end.y() - target_height / 2.0,
            target_width,
            target_height,
        )
        arrow_offset = 2.5 * math.sin(current * math.tau / 0.9)
        arrow_height = 27.0 * pulse
        arrow_width = arrow_height * (
            HOME_NAV_ARROW_CONTENT_RECT.width()
            / HOME_NAV_ARROW_CONTENT_RECT.height()
        )
        arrow_rect = QRectF(
            end.x() - arrow_width / 2.0,
            target_rect.top() - arrow_height - 2.0 + arrow_offset,
            arrow_width,
            arrow_height,
        )
        return {
            "start": QPointF(offset + start_x, start_y),
            "end": end,
            "opacity": opacity,
            "pulse": pulse,
            "footprints": tuple(footprints),
            "target_rect": target_rect,
            "arrow_rect": arrow_rect,
            "arrow_offset": arrow_offset,
        }

    @staticmethod
    def _draw_navigation_pixmap(
        painter,
        pixmap,
        source_rect,
        target_rect,
        *,
        rotation=0.0,
        mirrored=False,
        opacity=1.0,
    ):
        """Draw one alpha asset centered, rotated, and never stretched."""

        if pixmap is None or pixmap.isNull() or target_rect.isEmpty():
            return
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(max(0.0, min(1.0, float(opacity))))
        center = target_rect.center()
        painter.translate(center)
        painter.rotate(float(rotation))
        if mirrored:
            painter.scale(-1.0, 1.0)
        local_target = QRectF(
            -target_rect.width() / 2.0,
            -target_rect.height() / 2.0,
            target_rect.width(),
            target_rect.height(),
        )
        painter.drawPixmap(local_target, pixmap, QRectF(source_rect))
        painter.restore()

    def _draw_navigation_feedback(self, painter, now=None):
        """Draw the manual route and warm destination marker on the floor."""

        feedback = self.navigation_feedback(now)
        if feedback is None:
            return
        opacity = feedback["opacity"]

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        for footprint in feedback["footprints"]:
            self._draw_navigation_pixmap(
                painter,
                self.home_nav_paw,
                HOME_NAV_PAW_CONTENT_RECT,
                footprint["rect"],
                rotation=footprint["angle"],
                mirrored=footprint["mirrored"],
                opacity=opacity * 0.82,
            )
        self._draw_navigation_pixmap(
            painter,
            self.home_nav_target,
            HOME_NAV_TARGET_CONTENT_RECT,
            feedback["target_rect"],
            opacity=opacity,
        )
        self._draw_navigation_pixmap(
            painter,
            self.home_nav_arrow,
            HOME_NAV_ARROW_CONTENT_RECT,
            feedback["arrow_rect"],
            opacity=opacity,
        )
        painter.restore()

    def _draw_home_pet(self, painter):
        """Draw the replaceable four-direction placeholder pet."""

        if not self.home_pet_visible():
            return
        render_spec = self.home_pet_render_spec()
        body = self.home_pet_render_rect(render_spec)
        if render_spec is None:
            contact = home_pet_frame_contact(self.home_pet.direction, 0)
        else:
            contact = (
                render_spec.contact_center_x,
                render_spec.contact_width,
                render_spec.contact_foot_y,
            )
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if render_spec is None or self.home_pet.state != "sleeping":
            shadow = home_pet_shadow_rect(body, contact)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(91, 64, 45, 42))
            painter.drawEllipse(shadow)

        if render_spec is not None:
            source = QRectF(render_spec.source_rect)
            if render_spec.mirrored:
                painter.save()
                painter.translate(body.left() + body.right(), 0.0)
                painter.scale(-1.0, 1.0)
                painter.drawPixmap(body, render_spec.pixmap, source)
                painter.restore()
            else:
                painter.drawPixmap(body, render_spec.pixmap, source)
            painter.restore()
            return

        draw_body = QRectF(body)
        if self.home_pet.state in {"manual_walk", "auto_sleep_walk"}:
            bob = 3.0 * math.sin(time.monotonic() * 12.0)
            draw_body.translate(0.0, -abs(bob))
        elif self.home_pet.state == "sleeping":
            sleep_height = draw_body.height() * 0.62
            draw_body.setTop(draw_body.bottom() - sleep_height)

        colors = {
            "front_left": QColor("#d88974"),
            "front_right": QColor("#e4a06f"),
            "back_left": QColor("#8aa890"),
            "back_right": QColor("#79a3ad"),
        }
        painter.setBrush(colors.get(self.home_pet.direction, QColor("#d88974")))
        painter.setPen(QPen(QColor("#754b3a"), 2))
        painter.drawRoundedRect(draw_body, 14, 14)
        labels = {
            "front_left": "↙",
            "front_right": "↘",
            "back_left": "↖",
            "back_right": "↗",
        }
        painter.setPen(QColor("#fff8ed"))
        painter.drawText(
            draw_body,
            Qt.AlignCenter,
            "Z  Z" if self.home_pet.state == "sleeping" else labels.get(
                self.home_pet.direction, "•"
            ),
        )
        painter.restore()

    def _furniture_depth_key(self, decoration_id):
        if decoration_id == "home_wall_art":
            return (0, 0.0)
        if decoration_id == "home_rug":
            return (1, 0.0)
        return (2, float(self.selection_bounds(decoration_id).bottom()))

    def _scene_render_entries(self):
        """Return normal scene entries in deterministic 2.5D paint order."""

        entries = []
        for item_id in self.state.get("owned_home_decorations", []):
            if item_id in self.state.get("home_stored_decorations", []):
                continue
            pixmap = self.furniture.get(item_id)
            if pixmap is None or pixmap.isNull():
                continue
            entries.append((self._furniture_depth_key(item_id), "furniture", item_id))
        if self.navigation_feedback() is not None:
            entries.append(((1, 1.0), "navigation", "home_navigation"))
        if self.home_pet_visible():
            entries.append(((2, float(self.home_pet.position[1])), "pet", "home_pet"))
        return sorted(entries, key=lambda entry: entry[0])

    def _furniture_transform_rect(self, decoration_id):
        return self.selection_bounds(decoration_id).toAlignedRect()

    def selection_bounds(self, decoration_id):
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRectF()
        position = self.state.get("home_decoration_positions", {}).get(decoration_id, {})
        transform = progression.home_decoration_transform(self.state, decoration_id)
        bounds = home_decoration_bounds(
            position,
            (pixmap.width(), pixmap.height()),
            transform,
            self._camera_x,
        )
        bounds.translate(self._scene_content_offset(), 0)
        return bounds

    def selection_handles(self, decoration_id):
        return home_decoration_handles(self.selection_bounds(decoration_id))

    def _draw_selection(self, painter, decoration_id):
        bounds = self.selection_bounds(decoration_id)
        handles = self.selection_handles(decoration_id)
        painter.save()
        painter.setBrush(HOME_SELECTION_FILL_COLOR)
        painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 2))
        painter.drawRoundedRect(bounds, 9, 9)
        rotate = handles["rotate"]
        painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 1))
        painter.drawLine(
            int(bounds.center().x()), int(bounds.top()),
            int(rotate.center().x()), int(rotate.center().y()),
        )
        for handle, rect in handles.items():
            painter.setBrush(QColor(HOME_SELECTION_HANDLE_COLOR))
            painter.setPen(QPen(QColor(HOME_SELECTION_BORDER_COLOR), 2))
            painter.drawEllipse(rect)
        painter.restore()

    def _panel_rect(self):
        return QRect(0, 0, HOME_DECORATION_SIDEBAR_WIDTH, self.height())

    def _visible_decoration_ids(self):
        category = self._decoration_category
        return [
            item_id for item_id in self.state.get("owned_home_decorations", [])
            if category == "all" or HOME_DECORATION_CATEGORY_BY_ID.get(item_id) == category
        ]

    def _category_rects(self):
        panel = self._panel_rect()
        width = (panel.width() - 24) // len(HOME_DECORATION_CATEGORIES)
        return {
            category: QRect(
                panel.x() + 12 + index * width,
                panel.y() + HOME_DECORATION_CATEGORY_TOP,
                width - 5,
                26,
            )
            for index, (category, _label) in enumerate(HOME_DECORATION_CATEGORIES)
        }

    def _item_card_rects(self):
        panel = self._panel_rect()
        items = self._visible_decoration_ids()
        card_width = (panel.width() - 36) // 2
        return {
            item_id: QRect(
                panel.x() + 12 + (index % 2) * (card_width + 8),
                panel.y()
                + HOME_DECORATION_CARD_TOP
                + (index // 2) * HOME_DECORATION_CARD_STEP,
                card_width,
                HOME_DECORATION_CARD_HEIGHT,
            )
            for index, item_id in enumerate(items)
        }

    @staticmethod
    def _item_thumbnail_rect(card):
        return QRect(
            card.x() + 8,
            card.y() + 8,
            card.width() - 16,
            HOME_DECORATION_THUMBNAIL_HEIGHT,
        )

    def furniture_preview_rect(self, decoration_id, card):
        """Fit a furniture bitmap inside its card without changing its aspect ratio."""
        thumbnail = self._item_thumbnail_rect(card)
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRect()
        preview = pixmap.scaled(
            thumbnail.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        return QRect(
            thumbnail.x() + (thumbnail.width() - preview.width()) // 2,
            thumbnail.y() + (thumbnail.height() - preview.height()) // 2,
            preview.width(),
            preview.height(),
        )

    @staticmethod
    def _item_action_rect(card):
        return QRect(card.x() + 8, card.bottom() - 32, card.width() - 16, 27)

    def _draw_decoration_panel(self, painter):
        panel = self._panel_rect()
        painter.setPen(QPen(QColor("#e7c4ad"), 1))
        painter.setBrush(QColor(255, 248, 236, 238))
        painter.drawRoundedRect(panel, 18, 18)
        painter.setPen(QColor("#754b3a"))
        painter.drawText(
            QRect(panel.x() + 14, panel.y() + 8, panel.width() - 64, 24),
            Qt.AlignLeft,
            "家具布置",
        )
        self._draw_scene_button(
            painter, self.decoration_panel_close_button_rect(), "×"
        )
        for category, label in HOME_DECORATION_CATEGORIES:
            rect = self._category_rects()[category]
            painter.setBrush(QColor("#cf846a" if category == self._decoration_category else "#f9e7ce"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 7, 7)
            painter.setPen(QColor("#65483b"))
            painter.drawText(rect, Qt.AlignCenter, label)
        for item_id, card in self._item_card_rects().items():
            stored = item_id in self.state.get("home_stored_decorations", [])
            name = progression.HOME_DECORATION_DEFINITIONS[item_id]["name"]
            painter.setPen(QColor("#cf846a" if item_id == self._selected_furniture else "#e7c4ad"))
            painter.setBrush(QColor("#fffaf1"))
            painter.drawRoundedRect(card, 9, 9)
            thumbnail = self._item_thumbnail_rect(card)
            pixmap = self.furniture.get(item_id)
            if pixmap is not None and not pixmap.isNull():
                preview = self.furniture_preview_rect(item_id, card)
                painter.drawPixmap(
                    preview.topLeft(),
                    pixmap.scaled(
                        thumbnail.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ),
                )
            painter.setPen(QColor("#754b3a"))
            name_rect = QRect(card.x() + 8, card.y() + 88, card.width() - 12, 23)
            painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name)
            action = "放置" if stored else "收纳"
            painter.setBrush(QColor("#f5d6b3"))
            painter.setPen(Qt.NoPen)
            action_rect = self._item_action_rect(card)
            painter.drawRoundedRect(action_rect, 7, 7)
            painter.setPen(QColor("#65483b"))
            painter.drawText(action_rect, Qt.AlignCenter, action)

    def handle_scene_click(self, point):
        """Handle non-furniture clicks without allowing the board above pet."""
        if self.exit_button_rect().contains(point):
            self.hide_scene()
            return True
        if self.decoration_button_rect().contains(point):
            self.toggle_decoration_mode()
            return True
        if self.view_pan_enabled() and self.left_view_button_rect().contains(point):
            self.begin_pan("left")
            return True
        if self.view_pan_enabled() and self.right_view_button_rect().contains(point):
            self.begin_pan("right")
            return True
        if self.is_decorating():
            if self._handle_decoration_panel_click(point):
                return True
            return False
        self.pet.raise_()
        return False

    def _scene_control_at(self, point):
        if self.exit_button_rect().contains(point):
            return True
        if self.decoration_button_rect().contains(point):
            return True
        if self.view_pan_enabled() and (
            self.left_view_button_rect().contains(point)
            or self.right_view_button_rect().contains(point)
        ):
            return True
        return self.is_decorating() and self._panel_rect().contains(point)

    def canvas_to_world(self, point):
        """Convert a window-local canvas point to home-world coordinates."""

        canvas = self.scene_canvas_rect()
        return (
            float(point.x() - canvas.left() + self._camera_x),
            float(point.y()),
        )

    def command_home_pet(self, point, now=None):
        """Send the in-scene pet toward a right-clicked floor point."""

        canvas = self.scene_canvas_rect()
        if (
            not self.isVisible()
            or self.is_decorating()
            or not canvas.contains(point)
            or self._scene_control_at(point)
        ):
            return False
        interrupted_sleep = self.home_pet.command_move(
            self.canvas_to_world(point),
            time.monotonic() if now is None else float(now),
        )
        self._set_manual_destination(self.home_pet.target)
        if interrupted_sleep:
            self.state["sleeping"] = False
            self.state["sleep_mode"] = None
            self.save_state(self.state)
        self.update()
        return True

    def _handle_decoration_panel_click(self, point):
        if self.decoration_panel_close_button_rect().contains(point):
            self.toggle_decoration_mode()
            return True
        for category, rect in self._category_rects().items():
            if rect.contains(point):
                self._decoration_category = category
                self.update()
                return True
        for item_id, card in self._item_card_rects().items():
            if card.contains(point):
                if self._item_action_rect(card).contains(point):
                    if item_id in self.state.get("home_stored_decorations", []):
                        self.place_furniture(item_id)
                    else:
                        self.store_furniture(item_id)
                elif item_id not in self.state.get("home_stored_decorations", []):
                    self.select_furniture(item_id)
                return True
        return self._panel_rect().contains(point)

    def _furniture_rect(self, decoration_id):
        pixmap = self.furniture.get(decoration_id)
        if pixmap is None or pixmap.isNull():
            return QRect()
        position = self.state.get("home_decoration_positions", {}).get(
            decoration_id, {}
        )
        return self._furniture_transform_rect(decoration_id)

    def furniture_at(self, point):
        """Return the top-most owned furniture item at a board-local point."""
        if not self.is_decorating():
            return None
        for decoration_id in reversed(self.state.get("owned_home_decorations", [])):
            if decoration_id in self.state.get("home_stored_decorations", []):
                continue
            if self._furniture_rect(decoration_id).contains(point):
                return decoration_id
        return None

    def move_furniture(self, decoration_id, world_position):
        """Store an authored world position after a furniture drag."""
        if not self.is_decorating():
            return None
        position = progression.set_home_decoration_position(
            self.state,
            decoration_id,
            world_position.x(),
            world_position.y(),
        )
        self.save_state(self.state)
        self.update()
        return position

    def begin_furniture_gesture(self, point):
        """Select furniture or start a direct move, scale, or rotate gesture."""
        if not self.is_decorating():
            return False
        if self._selected_furniture is not None:
            for handle, rect in self.selection_handles(self._selected_furniture).items():
                if rect.contains(point):
                    item_id = self._selected_furniture
                    self._editing_gesture = {
                        "item_id": item_id,
                        "kind": "rotate" if handle == "rotate" else "scale",
                        "handle": handle,
                        "origin": QPoint(point),
                        "position": progression.home_decoration_position(self.state, item_id),
                        "transform": progression.home_decoration_transform(self.state, item_id),
                    }
                    return True
        decoration_id = self.furniture_at(point)
        if decoration_id is None:
            self._selected_furniture = None
            self.update()
            return False
        self.select_furniture(decoration_id)
        self._editing_gesture = {
            "item_id": decoration_id,
            "kind": "move",
            "origin": QPoint(point),
            "position": progression.home_decoration_position(self.state, decoration_id),
            "transform": progression.home_decoration_transform(self.state, decoration_id),
        }
        return True

    def update_furniture_gesture(self, point):
        gesture = self._editing_gesture
        if gesture is None or not self.is_decorating():
            return False
        decoration_id = gesture["item_id"]
        if gesture["kind"] == "move":
            delta = point - gesture["origin"]
            position = gesture["position"]
            self.move_furniture(
                decoration_id,
                QPoint(position["x"] + delta.x(), position["y"] + delta.y()),
            )
            return True
        bounds = self.selection_bounds(decoration_id)
        pixmap = self.furniture[decoration_id]
        transform = gesture["transform"]
        if gesture["kind"] == "scale":
            scale = scale_from_handle(
                bounds.center(), point, gesture["handle"],
                (pixmap.width(), pixmap.height()), transform["rotation"], transform["scale"],
            )
            progression.set_home_decoration_transform(
                self.state, decoration_id, scale=scale, rotation=transform["rotation"]
            )
        else:
            rotation = rotation_from_pointer(bounds.center(), point)
            progression.set_home_decoration_transform(
                self.state, decoration_id, scale=transform["scale"], rotation=rotation
            )
        self.save_state(self.state)
        self.update()
        return True

    def end_furniture_gesture(self, point):
        if self._editing_gesture is None:
            return False
        self.update_furniture_gesture(point)
        self._editing_gesture = None
        self.setCursor(Qt.ArrowCursor)
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            if self.open_home_pet_menu(event.pos()):
                event.accept()
            return
        if event.button() != Qt.LeftButton:
            return
        if self.handle_scene_click(event.pos()):
            event.accept()
            return
        if not self.is_decorating():
            if self.command_home_pet(event.pos()):
                event.accept()
            return
        if not self.begin_furniture_gesture(event.pos()):
            event.accept()
            return
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._editing_gesture is None:
            return
        self.update_furniture_gesture(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._pan_direction is not None:
            self.end_pan()
            event.accept()
            return
        if self._editing_gesture is None:
            return
        self.end_furniture_gesture(event.pos())
