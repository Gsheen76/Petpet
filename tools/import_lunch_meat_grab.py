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
SATURATION_GAIN = 1.296
BRIGHTNESS_GAIN = 0.845


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


def import_grid(source: Path, output_dir: Path) -> int:
    image = Image.open(source).convert("RGBA")
    if image.width != image.height:
        raise ValueError(f"Expected a square {GRID_SIZE}x{GRID_SIZE} grid: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_w = image.width // GRID_SIZE
    cell_h = image.height // GRID_SIZE
    written = 0
    for row in range(GRID_SIZE):
        for column in range(GRID_SIZE):
            index = row * GRID_SIZE + column
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
            frame.save(output_dir / f"{index:03d}.png", optimize=True)
            written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    arguments = parser.parse_args()
    written = import_grid(arguments.source, arguments.output_dir)
    print(f"wrote {written} frames to {arguments.output_dir}")


if __name__ == "__main__":
    main()
