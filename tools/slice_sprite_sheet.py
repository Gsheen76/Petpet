"""Split an equal-cell sprite sheet into Petpet animation PNG frames."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parent.parent
ANIMATIONS_DIR = PROJECT_DIR / "assets" / "animations"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split a sprite sheet into numbered Petpet frames."
    )
    parser.add_argument("image", type=Path, help="Source sprite sheet PNG")
    parser.add_argument("action", help="Animation name, for example walk")
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--frames", type=int, default=None,
                        help="Number of cells to export; defaults to all")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.columns < 1 or args.rows < 1:
        raise SystemExit("columns and rows must be positive")
    total_cells = args.columns * args.rows
    frame_count = args.frames if args.frames is not None else total_cells
    if not 1 <= frame_count <= total_cells:
        raise SystemExit("frames must be between 1 and columns*rows")

    source = Image.open(args.image).convert("RGBA")
    if source.width % args.columns or source.height % args.rows:
        raise SystemExit("image size must divide evenly by columns and rows")
    cell_w = source.width // args.columns
    cell_h = source.height // args.rows
    output_dir = ANIMATIONS_DIR / args.action
    output_dir.mkdir(parents=True, exist_ok=True)

    for index in range(frame_count):
        column = index % args.columns
        row = index // args.columns
        frame = source.crop((
            column * cell_w,
            row * cell_h,
            (column + 1) * cell_w,
            (row + 1) * cell_h,
        ))
        output_path = output_dir / f"{index:03d}.png"
        frame.save(output_path)
        print(output_path)


if __name__ == "__main__":
    main()
