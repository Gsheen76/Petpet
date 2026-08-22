"""Clean and import a 4x4 lunch-meat home-walk sprite grid."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy
from PIL import Image
from scipy import ndimage


GRID_SIZE = 4
ALPHA_THRESHOLD = 144
SOURCE_FILES = {
    "walk_down": "ChatGPT Image 2026年8月22日 20_55_13 (1).png",
    "walk_right": "ChatGPT Image 2026年8月22日 20_55_13 (2).png",
    "walk_up": "ChatGPT Image 2026年8月22日 20_55_13 (3).png",
    "walk_left": "ChatGPT Image 2026年8月22日 20_55_14 (4).png",
}


def _dog_region(frame: Image.Image) -> numpy.ndarray:
    """Keep the largest warm/cream connected region in one sprite cell."""

    pixels = numpy.asarray(frame)
    red, green, blue, alpha = numpy.moveaxis(pixels, -1, 0)
    orange = (red >= 120) & (green >= 40) & (green <= 225) & (blue <= 170)
    cream = (
        (red >= 130)
        & (green >= 90)
        & (blue >= 55)
        & ((red.astype(int) - blue.astype(int)) <= 125)
    )
    candidate = (alpha >= ALPHA_THRESHOLD) & (orange | cream)
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
    """Write the four cleaned source grids with their 4x4 geometry unchanged."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for action, filename in SOURCE_FILES.items():
        source = source_dir / filename
        image = clean_grid(source)
        if image.width != image.height:
            raise ValueError(f"Expected a square {GRID_SIZE}x{GRID_SIZE} grid: {source}")
        image.save(output_dir / f"{action}.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    arguments = parser.parse_args()
    import_grids(arguments.source_dir, arguments.output_dir)


if __name__ == "__main__":
    main()
