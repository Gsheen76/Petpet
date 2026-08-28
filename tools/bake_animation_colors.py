"""Bake color corrections into an animation folder's frames in place.

Usage:
    python tools/bake_animation_colors.py <folder> --sat 1.08 --val 0.88 --green 0.96

Gains are measured against the idle animation's alpha-weighted stats so
every action reads as the same dog. Source PNGs are rewritten; the
originals stay recoverable through git history.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy
from PIL import Image, ImageEnhance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--sat", type=float, default=1.0)
    parser.add_argument("--val", type=float, default=1.0)
    parser.add_argument("--green", type=float, default=1.0)
    arguments = parser.parse_args()

    frames = sorted(arguments.folder.glob("*.png"))
    if not frames:
        raise SystemExit(f"no PNG frames under {arguments.folder}")
    for path in frames:
        frame = Image.open(path).convert("RGBA")
        if abs(arguments.sat - 1.0) > 1e-3:
            frame = ImageEnhance.Color(frame).enhance(arguments.sat)
        if abs(arguments.val - 1.0) > 1e-3:
            frame = ImageEnhance.Brightness(frame).enhance(arguments.val)
        if abs(arguments.green - 1.0) > 1e-3:
            channels = list(frame.split())
            channels[1] = channels[1].point(
                lambda value: int(round(value * arguments.green))
            )
            frame = Image.merge("RGBA", channels)
        frame.save(path, optimize=True)
    print(f"adjusted {len(frames)} frames in {arguments.folder}")


if __name__ == "__main__":
    main()
