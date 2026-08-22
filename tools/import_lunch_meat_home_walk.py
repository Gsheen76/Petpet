"""Clean and import a 4x4 lunch-meat home-walk sprite grid."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy
from PIL import Image
from scipy import ndimage


GRID_SIZE = 4
OUTPUT_SIZE = 1600
ALPHA_THRESHOLD = 32
SOURCE_FILES = {
    "walk_right": "job_87fb25d73c4648429a1cc637b8a1dcd7-transparent.png",
    "walk_right_dinosaur": "job_18089add7a83419b8dc5cc60e203e38d-transparent.png",
    "walk_right_strawberry": "job_185a81ec997e44c689f114046221d89d-transparent.png",
}


def _dog_region(frame: Image.Image) -> numpy.ndarray:
    """Keep the largest authored subject regardless of outfit color."""

    pixels = numpy.asarray(frame)
    alpha = pixels[:, :, 3]
    candidate = alpha >= ALPHA_THRESHOLD
    labels, count = ndimage.label(candidate)
    if count == 0:
        return alpha >= ALPHA_THRESHOLD
    sizes = ndimage.sum(candidate, labels, range(1, count + 1))
    largest = labels == (int(numpy.argmax(sizes)) + 1)
    return ndimage.binary_dilation(largest, iterations=2)


def clean_grid(source: Path) -> Image.Image:
    """Remove semi-transparent generator residue from every 4x4 cell."""

    image = Image.open(source).convert("RGBA")
    result = Image.new("RGBA", image.size)
    for row in range(GRID_SIZE):
        top = round(row * image.height / GRID_SIZE)
        bottom = round((row + 1) * image.height / GRID_SIZE)
        for column in range(GRID_SIZE):
            left = round(column * image.width / GRID_SIZE)
            right = round((column + 1) * image.width / GRID_SIZE)
            frame = image.crop((left, top, right, bottom))
            pixels = numpy.asarray(frame).copy()
            pixels[:, :, 3] = numpy.where(
                _dog_region(frame), pixels[:, :, 3], 0
            )
            result.alpha_composite(Image.fromarray(pixels), (left, top))
    return result


def import_grids(source_dir: Path, output_dir: Path) -> None:
    """Write the three cleaned right-facing grids with geometry unchanged."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for action, filename in SOURCE_FILES.items():
        source = source_dir / filename
        image = clean_grid(source)
        if image.width != image.height:
            raise ValueError(f"Expected a square {GRID_SIZE}x{GRID_SIZE} grid: {source}")
        if image.width > OUTPUT_SIZE:
            image = image.resize(
                (OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS
            )
        image.save(output_dir / f"{action}.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    arguments = parser.parse_args()
    import_grids(arguments.source_dir, arguments.output_dir)


if __name__ == "__main__":
    main()
