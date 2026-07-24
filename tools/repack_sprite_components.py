"""Extract sprite subjects from an AI sheet and place them on stable anchors.

Unlike equal-cell cropping, this keeps subjects intact when AI-generated art
slightly crosses a theoretical cell boundary.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


PROJECT_DIR = Path(__file__).resolve().parent.parent
ANIMATIONS_DIR = PROJECT_DIR / "assets" / "animations"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("action")
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--subject-center-x", type=int, required=True)
    parser.add_argument("--subject-bottom", type=int, required=True)
    parser.add_argument("--prop-center-x", type=int)
    parser.add_argument("--prop-bottom", type=int)
    parser.add_argument("--alpha-threshold", type=int, default=20)
    return parser.parse_args()


def component_records(rgba, threshold):
    alpha = np.asarray(rgba.getchannel("A"))
    labels, count = ndimage.label(alpha > threshold)
    records = []
    for label_id, slices in enumerate(ndimage.find_objects(labels), 1):
        if slices is None:
            continue
        ys, xs = slices
        component = labels[ys, xs] == label_id
        area = int(component.sum())
        records.append({
            "id": label_id,
            "area": area,
            "bbox": (xs.start, ys.start, xs.stop, ys.stop),
            "center": ((xs.start + xs.stop) / 2,
                       (ys.start + ys.stop) / 2),
        })
    return labels, records


def ordered(records, count, columns):
    selected = sorted(records, key=lambda item: item["area"], reverse=True)[:count]
    by_height = sorted(selected, key=lambda item: item["center"][1])
    result = []
    for row_start in range(0, count, columns):
        row = by_height[row_start:row_start + columns]
        result.extend(sorted(row, key=lambda item: item["center"][0]))
    return result


def isolated_crop(source, labels, record):
    left, top, right, bottom = record["bbox"]
    crop = np.array(source.crop((left, top, right, bottom)), copy=True)
    component = labels[top:bottom, left:right] == record["id"]
    crop[:, :, 3] = np.where(component, crop[:, :, 3], 0)
    return Image.fromarray(crop, "RGBA")


def paste_anchored(canvas, sprite, center_x, bottom):
    x = round(center_x - sprite.width / 2)
    y = bottom - sprite.height
    canvas.alpha_composite(sprite, (x, y))


def main():
    args = parse_args()
    source = Image.open(args.image).convert("RGBA")
    if source.width % args.columns or source.height % args.rows:
        raise SystemExit("image dimensions must divide evenly by the grid")
    if args.frames != args.columns * args.rows:
        raise SystemExit("this tool currently expects one frame per grid cell")

    labels, records = component_records(source, args.alpha_threshold)
    meaningful = [record for record in records if record["area"] >= 100]
    if len(meaningful) < args.frames:
        raise SystemExit("not enough visible components for all subjects")

    subjects = ordered(meaningful, args.frames, args.columns)
    subject_ids = {record["id"] for record in subjects}
    remaining = [record for record in meaningful
                 if record["id"] not in subject_ids]
    use_props = args.prop_center_x is not None and args.prop_bottom is not None
    props = ordered(remaining, args.frames, args.columns) if use_props else []
    if use_props and len(props) != args.frames:
        raise SystemExit("expected one separate prop component per frame")

    cell_size = (source.width // args.columns,
                 source.height // args.rows)
    output_dir = ANIMATIONS_DIR / args.action
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, subject_record in enumerate(subjects):
        canvas = Image.new("RGBA", cell_size, (0, 0, 0, 0))
        subject = isolated_crop(source, labels, subject_record)
        paste_anchored(canvas, subject, args.subject_center_x,
                       args.subject_bottom)
        if use_props:
            prop = isolated_crop(source, labels, props[index])
            paste_anchored(canvas, prop, args.prop_center_x,
                           args.prop_bottom)
        output_path = output_dir / f"{index:03d}.png"
        canvas.save(output_path)
        print(output_path)


if __name__ == "__main__":
    main()
