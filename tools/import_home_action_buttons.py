"""Import home action buttons from the transparent UI sheet.

Splits the sheet by alpha connected components, maps each button to its
runtime name, and writes 2x-resolution PNGs under
``assets/runtime/scenes/home/buttons``.  Labels are drawn at runtime, so the
sheet must contain no baked text.

Usage:
    python tools/import_home_action_buttons.py [sheet]
"""

from __future__ import annotations

import os
import shutil
import sys
from collections import deque

import numpy as np
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_BUTTONS_DIR = os.path.join(
    PROJECT_ROOT, "assets", "runtime", "scenes", "home", "buttons"
)
REFERENCE_DIR = os.path.join(PROJECT_ROOT, "assets", "source", "references")

DEFAULT_SHEET = os.path.join(REFERENCE_DIR, "home-action-buttons-transparent.png")

# Sheet order: two columns, top to bottom.  The cream round paw button is
# imported for reference but intentionally unused by the home window.
COLUMN_NAMES = (
    ("exit", "decorate", "interaction", "shop", "collapse", "paw_round"),
    ("sleep", "play", "feed", "pet", "back", "menu_round"),
)

WIDE_TARGET = (240, 92)  # 2x of the 120x46 bar button
ROUND_TARGET = (92, 92)  # 2x of the 46x46 round toggle


def components(mask):
    """Label 4-connected components of an alpha mask."""
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    boxes = {}
    label = 0
    for sy in range(height):
        for sx in range(width):
            if mask[sy, sx] and labels[sy, sx] == 0:
                label += 1
                queue = deque([(sy, sx)])
                labels[sy, sx] = label
                y0 = y1 = sy
                x0 = x1 = sx
                while queue:
                    y, x = queue.popleft()
                    y0 = min(y0, y)
                    y1 = max(y1, y)
                    x0 = min(x0, x)
                    x1 = max(x1, x)
                    for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                        if 0 <= ny < height and 0 <= nx < width:
                            if mask[ny, nx] and labels[ny, nx] == 0:
                                labels[ny, nx] = label
                                queue.append((ny, nx))
                boxes[label] = (x0, y0, x1 + 1, y1 + 1)
    return boxes


def box_area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def box_center(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def main():
    sheet = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SHEET
    if not os.path.exists(sheet):
        raise SystemExit(f"missing sheet: {sheet}")
    os.makedirs(RUNTIME_BUTTONS_DIR, exist_ok=True)
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    archive = os.path.join(REFERENCE_DIR, "home-action-buttons-transparent.png")
    if os.path.abspath(sheet) != os.path.abspath(archive):
        shutil.copyfile(sheet, archive)
        print(f"reference: {archive}")

    image = Image.open(sheet).convert("RGBA")
    alpha = np.asarray(image)[:, :, 3] > 8
    raw = list(components(alpha).values())
    # Button bodies are huge; floating hearts/sparkles/bows are small.
    bodies = [box for box in raw if box_area(box) >= 10000]
    decorations = [box for box in raw if box_area(box) < 10000]
    if len(bodies) != 12:
        raise SystemExit(f"expected 12 button bodies, found {len(bodies)}")
    boxes = list(bodies)
    for decoration in decorations:
        center = box_center(decoration)
        nearest = min(
            range(len(boxes)),
            key=lambda i: (
                (box_center(boxes[i])[0] - center[0]) ** 2
                + (box_center(boxes[i])[1] - center[1]) ** 2
            ),
        )
        target = boxes[nearest]
        boxes[nearest] = (
            min(target[0], decoration[0]),
            min(target[1], decoration[1]),
            max(target[2], decoration[2]),
            max(target[3], decoration[3]),
        )

    ordered = sorted(boxes, key=lambda b: (0 if b[0] < image.width / 2 else 1, b[1]))
    left = [b for b in ordered if b[0] < image.width / 2]
    right = [b for b in ordered if b[0] >= image.width / 2]
    if len(left) != 6 or len(right) != 6:
        raise SystemExit(f"expected 6 buttons per column, got {len(left)}/{len(right)}")

    written = []
    for name, (x0, y0, x1, y1) in zip(COLUMN_NAMES[0] + COLUMN_NAMES[1], left + right):
        pad = 2
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cx1, cy1 = min(image.width, x1 + pad), min(image.height, y1 + pad)
        crop = image.crop((cx0, cy0, cx1, cy1))
        width, height = crop.size
        target = WIDE_TARGET if width > height * 1.5 else ROUND_TARGET
        resized = crop.resize(target, Image.LANCZOS)
        path = os.path.join(RUNTIME_BUTTONS_DIR, f"{name}.png")
        resized.save(path)
        written.append((name, path, crop.size, target))

    for name, path, source_size, target in written:
        with Image.open(path) as check:
            corners = [
                check.getpixel(pixel)[3]
                for pixel in ((0, 0), (check.width - 1, 0), (0, check.height - 1), (check.width - 1, check.height - 1))
            ]
            print(
                f"{name}: {source_size} -> {check.size} corner-alpha={corners}"
            )
    stale = os.path.join(RUNTIME_BUTTONS_DIR, "menu.png")
    if os.path.exists(stale):
        os.remove(stale)
        print("removed stale menu.png")


if __name__ == "__main__":
    main()
