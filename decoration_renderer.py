"""Reusable idle-pose decoration rendering for Petpet."""

from __future__ import annotations

import os

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPainter, QPixmap, QRegion, QTransform

import progression
from app_paths import DECORATIONS_DIR


def crop_to_visible_alpha(pixmap):
    """Remove transparent padding so scale values describe visible artwork."""
    if pixmap is None or pixmap.isNull():
        return QPixmap()
    visible = QRegion(pixmap.mask()).boundingRect()
    if visible.isEmpty():
        return pixmap
    return pixmap.copy(visible)


def load_decoration_pixmaps(directory=DECORATIONS_DIR):
    """Load one trimmed runtime pixmap for every decoration definition."""
    pixmaps = {}
    for decoration_id, definition in progression.DECORATION_DEFINITIONS.items():
        path = os.path.join(directory, definition["asset"])
        pixmap = crop_to_visible_alpha(QPixmap(path))
        if not pixmap.isNull():
            pixmaps[decoration_id] = pixmap
    return pixmaps


def fit_pixmap_rect(pixmap, bounds):
    """Return a centered aspect-fit rectangle for ``pixmap`` in ``bounds``."""
    bounds = QRectF(bounds)
    if (
        pixmap is None
        or pixmap.isNull()
        or bounds.width() <= 0
        or bounds.height() <= 0
    ):
        return QRectF()
    scale = min(
        bounds.width() / pixmap.width(),
        bounds.height() / pixmap.height(),
    )
    width = pixmap.width() * scale
    height = pixmap.height() * scale
    return QRectF(
        bounds.center().x() - width / 2.0,
        bounds.center().y() - height / 2.0,
        width,
        height,
    )


def decoration_rect(
    state,
    decoration_id,
    dog_bounds,
    pixmap,
    transform=None,
):
    """Return the unrotated destination rect for one decoration."""
    transform = transform or progression.decoration_transform(
        state, decoration_id
    )
    dog_bounds = QRectF(dog_bounds)
    width = dog_bounds.width() * transform["scale"]
    if pixmap is None or pixmap.isNull() or pixmap.width() <= 0:
        height = width
    else:
        height = width * pixmap.height() / pixmap.width()
    center_x = dog_bounds.left() + dog_bounds.width() * transform["x"]
    center_y = dog_bounds.top() + dog_bounds.height() * transform["y"]
    return QRectF(
        center_x - width / 2.0,
        center_y - height / 2.0,
        width,
        height,
    )


def rotated_bounds(rect, degrees):
    """Return an axis-aligned hit/selection rect after center rotation."""
    rect = QRectF(rect)
    transform = QTransform()
    transform.translate(rect.center().x(), rect.center().y())
    transform.rotate(float(degrees))
    transform.translate(-rect.center().x(), -rect.center().y())
    return transform.mapRect(rect)


def draw_decoration(
    painter,
    state,
    decoration_id,
    dog_bounds,
    pixmap,
    transform=None,
):
    """Draw one transformed decoration and return its rotated bounds."""
    if pixmap is None or pixmap.isNull():
        return QRectF()
    transform = transform or progression.decoration_transform(
        state, decoration_id
    )
    target = decoration_rect(
        state,
        decoration_id,
        dog_bounds,
        pixmap,
        transform=transform,
    )
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.translate(target.center())
    painter.rotate(transform["rotation"])
    local = QRectF(
        -target.width() / 2.0,
        -target.height() / 2.0,
        target.width(),
        target.height(),
    )
    painter.drawPixmap(
        local,
        pixmap,
        QRectF(0, 0, pixmap.width(), pixmap.height()),
    )
    painter.restore()
    return rotated_bounds(target, transform["rotation"])


def equipped_ids(state):
    """Return equipped decorations in their authored visual order."""
    progression.ensure_progression(state)
    equipped = state["equipped_decorations"]
    ids = [
        decoration_id
        for decoration_id in equipped.values()
        if decoration_id in progression.DECORATION_DEFINITIONS
    ]
    return sorted(
        ids,
        key=lambda item: progression.DECORATION_DEFINITIONS[item].get(
            "z_index", 0
        ),
    )


def draw_equipped_idle(
    painter,
    state,
    dog_bounds,
    pixmaps,
    selected_id=None,
):
    """Draw all equipped idle decorations and return their screen bounds."""
    geometries = {}
    for decoration_id in equipped_ids(state):
        transform = progression.decoration_transform(
            state,
            decoration_id,
            normalize_state=False,
        )
        geometry = draw_decoration(
            painter,
            state,
            decoration_id,
            dog_bounds,
            pixmaps.get(decoration_id),
            transform=transform,
        )
        if not geometry.isEmpty():
            geometries[decoration_id] = geometry
    return geometries
