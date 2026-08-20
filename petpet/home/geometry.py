"""Geometry and state helpers for the home scene.

The module intentionally has no window or progression dependencies so it can be
used by both the scene view and persistence tests without starting Qt widgets.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from PyQt5.QtCore import QPoint, QPointF, QRect, QRectF


HOME_VIEWPORT_SIZE = (900, 768)
HOME_WORLD_SIZE = (1800, 768)
HOME_CAMERA_PAN_STEP = 220
HOME_CAMERA_REPEAT_STEP = 18
HOME_DECORATION_SCALE_MIN = 0.5
HOME_DECORATION_SCALE_MAX = 1.5
HOME_DECORATION_ROTATION_MIN = -180.0
HOME_DECORATION_ROTATION_MAX = 180.0
HOME_DECORATION_HANDLE_SIZE = 14.0
HOME_DECORATION_ROTATE_HANDLE_OFFSET = 32.0

# Authored dimensions in world pixels.  Keep these in sync with the furniture
# catalog used by progression once the shop is wired in.
HOME_FURNITURE_SIZES = {
    "home_rug": (440, 270),
    "home_sofa": (360, 225),
    "home_plant": (190, 340),
    "home_wall_art": (220, 285),
    "home_status_card": (420, 270),
}


def _clamp_viewport_x(value: Any) -> int:
    return max(
        0,
        min(
            HOME_WORLD_SIZE[0] - HOME_VIEWPORT_SIZE[0],
            _finite_int(value, 0),
        ),
    )


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def _finite_int(value: Any, default: int = 0) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return int(number)


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def normalize_home_scene(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a safe, stable representation of persisted home-scene state."""

    source = value if isinstance(value, Mapping) else {}
    return {
        "enabled": _as_bool(source.get("enabled"), False),
        "background_visible": _as_bool(source.get("background_visible"), True),
        "screen_index": max(0, _finite_int(source.get("screen_index"), 0)),
        "viewport_x": max(0, min(HOME_WORLD_SIZE[0] - HOME_VIEWPORT_SIZE[0], _finite_int(source.get("viewport_x"), 0))),
        "viewport_y": max(0, min(HOME_WORLD_SIZE[1] - HOME_VIEWPORT_SIZE[1], _finite_int(source.get("viewport_y"), 0))),
        "viewport_pinned": _as_bool(source.get("viewport_pinned"), False),
        "decorating": _as_bool(source.get("decorating"), False),
    }


def pan_viewport_x(viewport_x: Any, direction: str, step: int = HOME_CAMERA_PAN_STEP) -> int:
    """Move the home viewport left or right while respecting world edges."""
    delta = abs(_finite_int(step, HOME_CAMERA_PAN_STEP))
    if direction == "left":
        delta = -delta
    elif direction != "right":
        return _clamp_viewport_x(viewport_x)
    return _clamp_viewport_x(_finite_int(viewport_x, 0) + delta)


def normalize_home_decoration_transform(value: Mapping[str, Any] | None) -> dict[str, float]:
    source = value if isinstance(value, Mapping) else {}
    try:
        scale = float(source.get("scale", 1.0))
    except (TypeError, ValueError, OverflowError):
        scale = 1.0
    try:
        rotation = float(source.get("rotation", 0.0))
    except (TypeError, ValueError, OverflowError):
        rotation = 0.0
    if not math.isfinite(scale):
        scale = 1.0
    if not math.isfinite(rotation):
        rotation = 0.0
    rotation = ((rotation + 180.0) % 360.0) - 180.0
    return {
        "scale": max(HOME_DECORATION_SCALE_MIN, min(HOME_DECORATION_SCALE_MAX, scale)),
        "rotation": max(HOME_DECORATION_ROTATION_MIN, min(HOME_DECORATION_ROTATION_MAX, rotation)),
    }


def home_decoration_bounds(
    position: Mapping[str, Any],
    size: tuple[int, int],
    transform: Mapping[str, Any] | None,
    camera_x: Any,
) -> QRectF:
    """Return the axis-aligned screen bounds of a transformed home item."""

    width, height = size
    normalized = normalize_home_decoration_transform(transform)
    angle = math.radians(normalized["rotation"])
    scaled_width = width * normalized["scale"]
    scaled_height = height * normalized["scale"]
    bound_width = abs(scaled_width * math.cos(angle)) + abs(scaled_height * math.sin(angle))
    bound_height = abs(scaled_width * math.sin(angle)) + abs(scaled_height * math.cos(angle))
    center_x = _finite_int(position.get("x", 0)) - _finite_int(camera_x) + width / 2
    center_y = _finite_int(position.get("y", 0)) + height / 2
    return QRectF(
        center_x - bound_width / 2,
        center_y - bound_height / 2,
        bound_width,
        bound_height,
    )


def home_decoration_handles(bounds: QRectF) -> dict[str, QRectF]:
    """Return PPT-like resize and rotate hit targets around selection bounds."""

    half = HOME_DECORATION_HANDLE_SIZE / 2

    def handle_at(point: QPointF) -> QRectF:
        return QRectF(point.x() - half, point.y() - half, HOME_DECORATION_HANDLE_SIZE, HOME_DECORATION_HANDLE_SIZE)

    top = QPointF(bounds.center().x(), bounds.top())
    return {
        "nw": handle_at(bounds.topLeft()),
        "n": handle_at(top),
        "ne": handle_at(bounds.topRight()),
        "e": handle_at(QPointF(bounds.right(), bounds.center().y())),
        "se": handle_at(bounds.bottomRight()),
        "s": handle_at(QPointF(bounds.center().x(), bounds.bottom())),
        "sw": handle_at(bounds.bottomLeft()),
        "w": handle_at(QPointF(bounds.left(), bounds.center().y())),
        "rotate": handle_at(QPointF(top.x(), top.y() - HOME_DECORATION_ROTATE_HANDLE_OFFSET)),
    }


def scale_from_handle(
    center: QPoint | QPointF,
    pointer: QPoint | QPointF,
    handle: str,
    base_size: tuple[int, int],
    rotation: Any,
    current_scale: Any,
) -> float:
    """Return the uniform scale implied by dragging a selection-box handle."""

    width, height = base_size
    if width <= 0 or height <= 0:
        return _finite_float(current_scale, 1.0)
    angle = math.radians(-_finite_float(rotation, 0.0))
    delta_x = pointer.x() - center.x()
    delta_y = pointer.y() - center.y()
    local_x = delta_x * math.cos(angle) - delta_y * math.sin(angle)
    local_y = delta_x * math.sin(angle) + delta_y * math.cos(angle)
    if handle in {"n", "s"}:
        scale = abs(local_y) / (height / 2)
    elif handle in {"e", "w"}:
        scale = abs(local_x) / (width / 2)
    else:
        scale = max(abs(local_x) / (width / 2), abs(local_y) / (height / 2))
    return max(0.0, scale)


def rotation_from_pointer(center: QPoint | QPointF, pointer: QPoint | QPointF) -> float:
    """Return the object angle that puts its rotate handle under ``pointer``."""

    angle = math.degrees(math.atan2(pointer.y() - center.y(), pointer.x() - center.x())) + 90.0
    return ((angle + 180.0) % 360.0) - 180.0


def camera_x_for_dog(world_x: float, dog_width: float) -> int:
    """Center the viewport on the dog while respecting world boundaries."""

    target = _finite_int(world_x, 0) + _finite_int(dog_width, 0) / 2 - HOME_VIEWPORT_SIZE[0] / 2
    maximum = HOME_WORLD_SIZE[0] - HOME_VIEWPORT_SIZE[0]
    return int(max(0, min(maximum, round(target))))


def scene_rect_for_screen(screen_rect: QRect, saved_x: Any = 0, saved_y: Any = 0) -> QRect:
    """Place the fixed-size scene board inside a screen rectangle."""

    width, height = HOME_VIEWPORT_SIZE
    max_x = max(0, screen_rect.width() - width)
    max_y = max(0, screen_rect.height() - height)
    x = screen_rect.left() + max(0, min(max_x, _finite_int(saved_x, 0)))
    y = screen_rect.top() + max(0, min(max_y, _finite_int(saved_y, 0)))
    return QRect(x, y, width, height)


def clamp_dog_to_scene(dog_rect: QRect, scene_rect: QRect) -> QPoint:
    """Return a dog top-left that keeps the complete dog inside the board."""

    max_x = max(scene_rect.left(), scene_rect.right() - dog_rect.width() + 1)
    max_y = max(scene_rect.top(), scene_rect.bottom() - dog_rect.height() + 1)
    x = max(scene_rect.left(), min(max_x, dog_rect.x()))
    y = max(scene_rect.top(), min(max_y, dog_rect.y()))
    return QPoint(x, y)


def clamp_home_furniture_position(decoration_id: str, x: Any, y: Any) -> dict[str, int]:
    """Clamp a furniture top-left to the authored world dimensions."""

    width, height = HOME_FURNITURE_SIZES.get(decoration_id, (0, 0))
    max_x = max(0, HOME_WORLD_SIZE[0] - width)
    max_y = max(0, HOME_WORLD_SIZE[1] - height)
    return {
        "x": max(0, min(max_x, _finite_int(x, 0))),
        "y": max(0, min(max_y, _finite_int(y, 0))),
    }
