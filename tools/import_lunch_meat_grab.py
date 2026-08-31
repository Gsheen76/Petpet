"""Clean and import the 4x4 lunch-meat grab (picked-up) sprite grid.

Frames keep their authored 640x640 cell geometry so the animation loader's
fit-and-scale pipeline can size the held dog consistently with idle.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy
from PIL import Image, ImageEnhance
from scipy import ndimage


GRID_SIZE = 4
ALPHA_THRESHOLD = 32
# Match the idle animation's measured saturation/brightness so the held
# silhouette reads as the same dog. (Measured: idle sat .644 val .784
# vs raw grab sat .529 val .899.)
SATURATION_GAIN = 1.153
BRIGHTNESS_GAIN = 0.862
# This sheet runs ~1.3 degrees yellow of the idle hue; trimming green
# pulls the orange back toward the idle red-orange.
GREEN_GAIN = 0.96


def _dog_region(frame: Image.Image) -> numpy.ndarray:
    """Keep the largest authored subject and drop generator residue."""

    pixels = numpy.asarray(frame)
    alpha = pixels[:, :, 3]
    candidate = alpha >= ALPHA_THRESHOLD
    labels, count = ndimage.label(candidate)
    if count == 0:
        return candidate
    sizes = ndimage.sum(candidate, labels, range(1, count + 1))
    largest = labels == (int(numpy.argmax(sizes)) + 1)
    return ndimage.binary_dilation(largest, iterations=2)


def import_grid(
    source: Path, output_dir: Path, columns: int = GRID_SIZE,
    rows: int = GRID_SIZE,
) -> int:
    image = Image.open(source).convert("RGBA")
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_w = image.width // columns
    cell_h = image.height // rows
    written = 0
    for row in range(rows):
        for column in range(columns):
            index = row * columns + column
            frame = image.crop((
                column * cell_w, row * cell_h,
                (column + 1) * cell_w, (row + 1) * cell_h,
            ))
            pixels = numpy.asarray(frame).copy()
            keep = _dog_region(frame)
            pixels[:, :, 3] = numpy.where(keep, pixels[:, :, 3], 0)
            frame = Image.fromarray(pixels)
            frame = ImageEnhance.Color(frame).enhance(SATURATION_GAIN)
            frame = ImageEnhance.Brightness(frame).enhance(BRIGHTNESS_GAIN)
            if abs(GREEN_GAIN - 1.0) > 1e-3:
                rgb = frame.convert("RGBA")
                channels = list(rgb.split())
                channels[1] = channels[1].point(
                    lambda value: int(round(value * GREEN_GAIN))
                )
                frame = Image.merge("RGBA", channels)
            frame.save(output_dir / f"{index:03d}.png", optimize=True)
            written += 1
    return written


def main() -> None:
    global SATURATION_GAIN, BRIGHTNESS_GAIN, GREEN_GAIN
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--sat", type=float, default=SATURATION_GAIN)
    parser.add_argument("--val", type=float, default=BRIGHTNESS_GAIN)
    parser.add_argument("--green", type=float, default=GREEN_GAIN)
    parser.add_argument("--no-correct", action="store_true")
    parser.add_argument("--cols", type=int, default=GRID_SIZE)
    parser.add_argument("--rows", type=int, default=GRID_SIZE)
    arguments = parser.parse_args()
    if arguments.no_correct:
        SATURATION_GAIN = BRIGHTNESS_GAIN = GREEN_GAIN = 1.0
    else:
        SATURATION_GAIN = arguments.sat
        BRIGHTNESS_GAIN = arguments.val
        GREEN_GAIN = arguments.green
    written = import_grid(
        arguments.source, arguments.output_dir,
        arguments.cols, arguments.rows,
    )
    print(f"wrote {written} frames to {arguments.output_dir}")


if __name__ == "__main__":
    main()
