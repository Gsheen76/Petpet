"""Small deterministic 2D cutout-rig runtime used by Petpet.

The rig is deliberately independent from the existing pre-rendered animation
loader. It can be prepared and visually reviewed before becoming the default
pet renderer, and it keeps decorations attached to named bones instead of
guessing coordinates independently for every PNG frame.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPainter, QPixmap, QTransform


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class Affine2D:
    """A compact row-major 2D affine matrix."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def __matmul__(self, other):
        return Affine2D(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            tx=self.a * other.tx + self.c * other.ty + self.tx,
            ty=self.b * other.tx + self.d * other.ty + self.ty,
        )

    def map(self, x, y):
        return QPointF(
            self.a * float(x) + self.c * float(y) + self.tx,
            self.b * float(x) + self.d * float(y) + self.ty,
        )

    def to_qtransform(self):
        return QTransform(
            self.a,
            self.b,
            0.0,
            self.c,
            self.d,
            0.0,
            self.tx,
            self.ty,
            1.0,
        )


def local_matrix(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0):
    radians = math.radians(float(rotation))
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return Affine2D(
        a=cosine * float(scale_x),
        b=sine * float(scale_x),
        c=-sine * float(scale_y),
        d=cosine * float(scale_y),
        tx=float(x),
        ty=float(y),
    )


@dataclass(frozen=True)
class Bone:
    name: str
    parent: str | None
    x: float
    y: float
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0

    @classmethod
    def from_dict(cls, values):
        return cls(
            name=str(values["name"]),
            parent=(
                str(values["parent"])
                if values.get("parent") not in (None, "")
                else None
            ),
            x=_number(values.get("x")),
            y=_number(values.get("y")),
            rotation=_number(values.get("rotation")),
            scale_x=_number(values.get("scale_x"), 1.0),
            scale_y=_number(values.get("scale_y"), 1.0),
        )


@dataclass(frozen=True)
class Slot:
    name: str
    bone: str
    asset: str
    order: int = 0
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    pivot_x: float = 0.5
    pivot_y: float = 0.5
    attachment: str | None = None

    @classmethod
    def from_dict(cls, values):
        return cls(
            name=str(values["name"]),
            bone=str(values["bone"]),
            asset=str(values["asset"]),
            order=int(values.get("order", 0)),
            x=_number(values.get("x")),
            y=_number(values.get("y")),
            rotation=_number(values.get("rotation")),
            scale_x=_number(values.get("scale_x"), 1.0),
            scale_y=_number(values.get("scale_y"), 1.0),
            pivot_x=_number(values.get("pivot_x"), 0.5),
            pivot_y=_number(values.get("pivot_y"), 0.5),
            attachment=(
                str(values["attachment"])
                if values.get("attachment") not in (None, "")
                else None
            ),
        )


@dataclass(frozen=True)
class Animation:
    name: str
    fps: float
    loop: bool
    frames: int
    tracks: dict

    @classmethod
    def from_dict(cls, name, values):
        return cls(
            name=str(name),
            fps=max(0.1, _number(values.get("fps"), 12.0)),
            loop=bool(values.get("loop", True)),
            frames=max(1, int(values.get("frames", 1))),
            tracks=values.get("tracks", {})
            if isinstance(values.get("tracks", {}), dict)
            else {},
        )


class RigDefinition:
    def __init__(self, canvas_width, canvas_height, bones, slots, animations):
        self.canvas_width = max(1, int(canvas_width))
        self.canvas_height = max(1, int(canvas_height))
        self.bones = {bone.name: bone for bone in bones}
        self.slots = tuple(sorted(slots, key=lambda slot: (slot.order, slot.name)))
        self.animations = {animation.name: animation for animation in animations}
        self._validate()

    @classmethod
    def from_dict(cls, values):
        canvas = values.get("canvas", {})
        bones = [
            Bone.from_dict(item)
            for item in values.get("bones", [])
            if isinstance(item, dict)
        ]
        slots = [
            Slot.from_dict(item)
            for item in values.get("slots", [])
            if isinstance(item, dict)
        ]
        animations = [
            Animation.from_dict(name, item)
            for name, item in values.get("animations", {}).items()
            if isinstance(item, dict)
        ]
        return cls(
            canvas.get("width", 512),
            canvas.get("height", 512),
            bones,
            slots,
            animations,
        )

    @classmethod
    def load(cls, path):
        path = Path(path)
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8-sig")))

    def _validate(self):
        if not self.bones:
            raise ValueError("A 2D rig must contain at least one bone")
        for bone in self.bones.values():
            if bone.parent and bone.parent not in self.bones:
                raise ValueError(
                    f"Bone {bone.name!r} has missing parent {bone.parent!r}"
                )
            seen = {bone.name}
            parent = bone.parent
            while parent:
                if parent in seen:
                    raise ValueError(f"Bone cycle detected at {parent!r}")
                seen.add(parent)
                parent = self.bones[parent].parent
        for slot in self.slots:
            if slot.bone not in self.bones:
                raise ValueError(
                    f"Slot {slot.name!r} has missing bone {slot.bone!r}"
                )


def _interpolate_track(keyframes, frame, field, default):
    parsed = sorted(
        (
            (max(0.0, _number(item.get("frame"))), _number(item.get(field), default))
            for item in keyframes
            if isinstance(item, dict) and field in item
        ),
        key=lambda item: item[0],
    )
    if not parsed:
        return float(default)
    if frame <= parsed[0][0]:
        return parsed[0][1]
    if frame >= parsed[-1][0]:
        return parsed[-1][1]
    for before, after in zip(parsed, parsed[1:]):
        if before[0] <= frame <= after[0]:
            span = max(0.000001, after[0] - before[0])
            progress = (frame - before[0]) / span
            return before[1] + (after[1] - before[1]) * progress
    return parsed[-1][1]


class RigPose:
    def __init__(self, definition, animation_name=None, frame=0.0):
        self.definition = definition
        self.animation = definition.animations.get(animation_name)
        self.frame = self._resolved_frame(frame)
        self._world_cache = {}

    def _resolved_frame(self, frame):
        if self.animation is None:
            return 0.0
        value = max(0.0, float(frame))
        if self.animation.loop:
            return value % self.animation.frames
        return min(value, self.animation.frames - 1)

    def _local_transform(self, bone):
        values = {
            "x": bone.x,
            "y": bone.y,
            "rotation": bone.rotation,
            "scale_x": bone.scale_x,
            "scale_y": bone.scale_y,
        }
        if self.animation:
            track = self.animation.tracks.get(bone.name, [])
            if isinstance(track, list):
                for field, default in tuple(values.items()):
                    values[field] = _interpolate_track(
                        track, self.frame, field, default
                    )
        return local_matrix(**values)

    def world_transform(self, bone_name):
        if bone_name in self._world_cache:
            return self._world_cache[bone_name]
        bone = self.definition.bones[bone_name]
        local = self._local_transform(bone)
        world = (
            self.world_transform(bone.parent) @ local
            if bone.parent
            else local
        )
        self._world_cache[bone_name] = world
        return world

    def slot_transform(self, slot):
        return self.world_transform(slot.bone) @ local_matrix(
            slot.x,
            slot.y,
            slot.rotation,
            slot.scale_x,
            slot.scale_y,
        )


class RigRenderer:
    def __init__(self, definition, asset_root):
        self.definition = definition
        self.asset_root = Path(asset_root)
        self._pixmaps = {}

    def _pixmap(self, asset):
        if asset not in self._pixmaps:
            self._pixmaps[asset] = QPixmap(str(self.asset_root / asset))
        return self._pixmaps[asset]

    def render(self, animation=None, frame=0.0, attachments=()):
        pixmap = QPixmap(
            self.definition.canvas_width,
            self.definition.canvas_height,
        )
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        pose = RigPose(self.definition, animation, frame)
        slots = sorted(
            (*self.definition.slots, *attachments),
            key=lambda slot: (slot.order, slot.name),
        )
        for slot in slots:
            layer = self._pixmap(slot.asset)
            if layer.isNull():
                continue
            painter.save()
            painter.setWorldTransform(
                pose.slot_transform(slot).to_qtransform(),
                combine=False,
            )
            painter.drawPixmap(
                QPointF(
                    -layer.width() * slot.pivot_x,
                    -layer.height() * slot.pivot_y,
                ),
                layer,
            )
            painter.restore()
        painter.end()
        return pixmap
