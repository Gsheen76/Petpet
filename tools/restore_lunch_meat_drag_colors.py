"""Restore the lunch_meat drag frames to their original sheet colors.

2026-09-22: the user judged the baked color calibration on the original
skin's grab animation visibly off. The source 4x4 sheet is no longer on
disk, but every baked op is a per-pixel linear map, so the exact chain is
invertible (validated against the 892fa44 vs b09b75f frame pair held in
git: model error mean 0.48/255, no pixel > 3).

Forward chain applied to the source sheet (git archaeology):
  1. saturation x1.153   (import_lunch_meat_grab.py @ b09b75f)
  2. brightness x0.862   (same)
  3. green channel x0.96 (added in 96c84c1, kept)
  4. uniform x1.0597     (the "brighten one notch" 379e315 tweak; factor
                          fitted from the b09b75f->379e315 frame diff,
                          NOT 1/0.92 as the commit message implied)

Run:  python tools/restore_lunch_meat_drag_colors.py   (in-place, git is
the backup). NOT idempotent: running it twice applies the inverse twice
and WILL overshoot -- do not re-run after committing.
"""

from __future__ import annotations

from pathlib import Path

import numpy
from PIL import Image

SAT_GAIN = 1.153
BRIGHT_GAIN = 0.862
GREEN_GAIN = 0.96
BRIGHTEN_NOTCH = 1.0597

DRAG_DIR = (
    Path(__file__).resolve().parents[1]
    / "assets" / "runtime" / "pets" / "lunch_meat" / "desktop" / "animations" / "drag"
)


def saturation_matrix(gain: float) -> numpy.ndarray:
    """ImageEnhance.Color as a 3x3 linear map (blend toward luminance)."""
    luminance = numpy.array([0.299, 0.587, 0.114])
    return gain * numpy.eye(3) + (1 - gain) * numpy.outer(numpy.ones(3), luminance)


def inverse_chain() -> numpy.ndarray:
    forward = (
        BRIGHTEN_NOTCH
        * numpy.diag([1.0, GREEN_GAIN, 1.0])
        @ (BRIGHT_GAIN * numpy.eye(3))
        @ saturation_matrix(SAT_GAIN)
    )
    return numpy.linalg.inv(forward)


def frame_stats(frame: Image.Image) -> tuple[float, float]:
    pixels = numpy.asarray(frame.convert("RGBA")).astype(numpy.float64)
    mask = pixels[:, :, 3] >= 32
    rgb = pixels[:, :, :3][mask]
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    value = (mx / 255.0).mean()
    sat = numpy.where(mx > 0, (mx - mn) / numpy.maximum(mx, 1e-9), 0).mean()
    return sat, value


def main() -> None:
    inv = inverse_chain()
    paths = sorted(DRAG_DIR.glob("*.png"))
    if not paths:
        raise SystemExit(f"no drag frames under {DRAG_DIR}")
    for path in paths:
        frame = Image.open(path).convert("RGBA")
        before = frame_stats(frame)
        array = numpy.asarray(frame).astype(numpy.float64)
        restored = array.copy()
        restored[:, :, :3] = numpy.clip(array[:, :, :3] @ inv.T, 0, 255)
        out = Image.fromarray(restored.round().astype(numpy.uint8))
        out.save(path, optimize=True)
        after = frame_stats(out)
        print(
            f"{path.name}: sat {before[0]:.3f}->{after[0]:.3f} "
            f"val {before[1]:.3f}->{after[1]:.3f}"
        )


if __name__ == "__main__":
    main()
