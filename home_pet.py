"""Qt-free movement and geometry primitives for the in-home pet."""

from __future__ import annotations

import math
from typing import Any, Mapping


Point = tuple[float, float]

HOME_WALKABLE_POLYGON: tuple[Point, ...] = (
    (60.0, 460.0),
    (1740.0, 460.0),
    (1800.0, 730.0),
    (0.0, 730.0),
)
HOME_DEFAULT_ENTRY: Point = (450.0, 620.0)
HOME_DEFAULT_SLEEP_POINT: Point = (260.0, 610.0)


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _point_on_segment(point: Point, start: Point, end: Point) -> Point:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return start
    ratio = ((px - sx) * dx + (py - sy) * dy) / length_squared
    ratio = max(0.0, min(1.0, ratio))
    return (sx + ratio * dx, sy + ratio * dy)


def _inside_polygon(point: Point, polygon: tuple[Point, ...]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        nearest = _point_on_segment(point, previous, current)
        if math.dist(point, nearest) <= 1e-9:
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def clamp_to_walkable(
    point: Point,
    polygon: tuple[Point, ...] = HOME_WALKABLE_POLYGON,
) -> Point:
    """Return ``point`` inside the floor, projecting to its nearest edge."""

    x = _finite_float(point[0])
    y = _finite_float(point[1])
    normalized = HOME_DEFAULT_ENTRY if x is None or y is None else (x, y)
    if not polygon:
        return normalized
    if _inside_polygon(normalized, polygon):
        return normalized
    candidates = [
        _point_on_segment(normalized, polygon[index - 1], polygon[index])
        for index in range(len(polygon))
    ]
    return min(candidates, key=lambda candidate: math.dist(normalized, candidate))


def direction_for_delta(
    dx: float,
    dy: float,
    fallback: str = "front_right",
) -> str:
    """Map a screen-space target vector to one of four home directions."""

    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return fallback
    depth = "front" if dy >= 0 else "back"
    side = "right" if dx >= 0 else "left"
    return f"{depth}_{side}"


def route_footprints(
    start: Point,
    end: Point,
    spacing: float = 42.0,
    lateral_offset: float = 6.0,
) -> tuple[dict[str, float | bool], ...]:
    """Sample alternating paw placements along a straight route."""

    start_x, start_y = start
    end_x, end_y = end
    dx = end_x - start_x
    dy = end_y - start_y
    distance = math.hypot(dx, dy)
    step = max(1.0, float(spacing))
    if distance < step:
        return ()
    unit_x = dx / distance
    unit_y = dy / distance
    normal_x = -unit_y
    normal_y = unit_x
    angle = math.degrees(math.atan2(dy, dx))
    offset = max(0.0, float(lateral_offset))
    placements = []
    along = step * 0.5
    end_clearance = step * 0.75
    index = 0
    while along <= distance - end_clearance:
        side = -1.0 if index % 2 == 0 else 1.0
        placements.append({
            "x": start_x + unit_x * along + normal_x * offset * side,
            "y": start_y + unit_y * along + normal_y * offset * side,
            "angle": angle,
            "mirrored": bool(index % 2),
        })
        along += step
        index += 1
    return tuple(placements)


def depth_scale_for_y(
    y: float,
    polygon: tuple[Point, ...] = HOME_WALKABLE_POLYGON,
    minimum: float = 0.72,
    maximum: float = 1.08,
) -> float:
    """Return a bounded far-to-near scale from the pet's foot depth."""

    finite_y = _finite_float(y)
    if finite_y is None:
        finite_y = HOME_DEFAULT_ENTRY[1]
    depths = [point[1] for point in polygon] or [finite_y]
    far_y = min(depths)
    near_y = max(depths)
    if near_y <= far_y:
        return minimum
    ratio = max(0.0, min(1.0, (finite_y - far_y) / (near_y - far_y)))
    return minimum + (maximum - minimum) * ratio


def load_home_pet_position(
    home_scene: Mapping[str, Any] | None,
    legacy_x: Any = None,
) -> Point:
    """Load the saved two-dimensional position or migrate a legacy x value."""

    source = home_scene if isinstance(home_scene, Mapping) else {}
    raw_position = source.get("pet_position")
    if isinstance(raw_position, Mapping):
        x = _finite_float(raw_position.get("x"))
        y = _finite_float(raw_position.get("y"))
        if x is not None and y is not None:
            return clamp_to_walkable((x, y))
        return HOME_DEFAULT_ENTRY
    migrated_x = _finite_float(legacy_x)
    if migrated_x is None:
        return HOME_DEFAULT_ENTRY
    return clamp_to_walkable((migrated_x, HOME_DEFAULT_ENTRY[1]))


def serialize_home_pet_position(position: Point) -> dict[str, float]:
    """Return the stable persisted representation of a home-pet position."""

    x, y = clamp_to_walkable(position)
    return {"x": round(x, 2), "y": round(y, 2)}


class HomePetController:
    """Deterministic movement state for the pet drawn inside the home."""

    def __init__(
        self,
        position: Point,
        *,
        walk_speed: float = 180.0,
        arrival_radius: float = 3.0,
        sleep_retry_seconds: float = 60.0,
    ):
        self.position = clamp_to_walkable(position)
        self.target: Point | None = None
        self.state = "idle"
        self.direction = "front_right"
        self.walk_speed = max(0.0, float(walk_speed))
        self.arrival_radius = max(0.0, float(arrival_radius))
        self.sleep_retry_seconds = max(0.0, float(sleep_retry_seconds))
        self.sleep_retry_until = 0.0

    def command_move(self, target: Point, now: float) -> bool:
        """Replace the current destination with a user-selected target."""

        interrupted_sleep = self.state in {
            "manual_sleep_walk",
            "auto_sleep_walk",
            "sleeping",
        }
        if interrupted_sleep:
            self.sleep_retry_until = float(now) + self.sleep_retry_seconds
        normalized = clamp_to_walkable(target)
        dx = normalized[0] - self.position[0]
        dy = normalized[1] - self.position[1]
        self.target = normalized
        self.direction = direction_for_delta(dx, dy, self.direction)
        self.state = "manual_walk"
        return interrupted_sleep

    def request_manual_sleep(self, target: Point, now: float) -> bool:
        """Walk to a user-requested sleep target without sleeping early."""

        if self.state != "idle":
            return False
        normalized = clamp_to_walkable(target)
        dx = normalized[0] - self.position[0]
        dy = normalized[1] - self.position[1]
        self.target = normalized
        self.direction = direction_for_delta(dx, dy, self.direction)
        self.state = "manual_sleep_walk"
        return True

    def request_auto_sleep(self, target: Point, now: float) -> bool:
        """Start walking to a sleep target when the controller is eligible."""

        if self.state != "idle" or float(now) < self.sleep_retry_until:
            return False
        normalized = clamp_to_walkable(target)
        dx = normalized[0] - self.position[0]
        dy = normalized[1] - self.position[1]
        self.target = normalized
        self.direction = direction_for_delta(dx, dy, self.direction)
        self.state = "auto_sleep_walk"
        return True

    def advance(self, dt: float) -> tuple[str, ...]:
        """Advance movement by elapsed seconds and return transition events."""

        if self.target is None or self.state not in {
            "manual_walk",
            "manual_sleep_walk",
            "auto_sleep_walk",
        }:
            return ()
        elapsed = max(0.0, min(0.1, float(dt)))
        dx = self.target[0] - self.position[0]
        dy = self.target[1] - self.position[1]
        distance = math.hypot(dx, dy)
        step = self.walk_speed * elapsed
        if distance <= step + self.arrival_radius:
            arrived_from = self.state
            self.position = self.target
            self.target = None
            if arrived_from == "manual_sleep_walk":
                self.state = "sleeping"
                return ("arrived", "manual_sleep_started")
            if arrived_from == "auto_sleep_walk":
                self.state = "sleeping"
                return ("arrived", "sleep_started")
            self.state = "idle"
            return ("arrived",)
        if distance > 0.0 and step > 0.0:
            ratio = step / distance
            self.position = (
                self.position[0] + dx * ratio,
                self.position[1] + dy * ratio,
            )
        return ()

    def cancel_target(self) -> None:
        """Stop walking without changing the current position or facing."""

        self.target = None
        if self.state in {
            "manual_walk",
            "manual_sleep_walk",
            "auto_sleep_walk",
        }:
            self.state = "idle"

    def set_sleeping(self) -> None:
        """Restore or enter sleep without changing the current position."""

        self.target = None
        self.state = "sleeping"

    def wake_if_recovered(self, energy: float, wake_threshold: float) -> bool:
        """Wake a sleeping home pet once shared energy reaches its threshold."""

        if self.state != "sleeping":
            return False
        if float(energy) < float(wake_threshold):
            return False
        self.state = "idle"
        return True
