"""Flatten a downloaded Meowa background and midground into Petpet's canvas."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


TARGET_SIZE = (1800, 768)


def flatten_scene(source_dir: Path, output_path: Path) -> None:
    background = Image.open(source_dir / "background.png").convert("RGBA")
    midground = Image.open(source_dir / "midground.png").convert("RGBA")
    if background.size != midground.size:
        raise ValueError("background.png and midground.png must have the same size")

    background.alpha_composite(midground)
    flattened = ImageOps.fit(
        background,
        TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    flattened.save(output_path, "PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    flatten_scene(args.source_dir, args.output_path)


if __name__ == "__main__":
    main()
