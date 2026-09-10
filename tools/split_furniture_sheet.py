# -*- coding: utf-8 -*-
"""家园家具素材表拆分器（2026-09-10 家具扩充轮）。

把 2×2 家具素材表拆成四件家具，按定义尺寸缩放后写入
assets/runtime/furniture/home/（同名覆盖占位稿）。与礼物/按键
拆分器的差别：家具保持各自原始宽高比（不压方形画布），输出尺寸
= HOME_DECORATION_DEFINITIONS 里的 size。

用法：python tools/split_furniture_sheet.py <素材表.png> [--threshold 240]
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet_utils import axis_bounds, cell_to_icon, nonwhite_mask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FURNITURE_DIR = os.path.join(ROOT, "assets", "runtime", "furniture", "home")

# 顺序 = 提示词顺序（行优先）→ (asset 文件名, 定义尺寸)。
FURNITURE_ORDER = (
    ("lamp.png", (150, 330)),
    ("bookshelf.png", (230, 280)),
    ("round_table.png", (280, 190)),
    ("toy_basket.png", (220, 150)),
)

COLUMNS = 2


def split_sheet(sheet_path: str, threshold: int = 240,
                write: bool = True) -> list[tuple[str, int]]:
    sheet = Image.open(sheet_path).convert("RGBA")
    mask = nonwhite_mask(sheet, threshold)
    rows = -(-len(FURNITURE_ORDER) // COLUMNS)
    col_bounds = axis_bounds(mask, COLUMNS, axis=1)
    row_bounds = axis_bounds(mask, rows, axis=0)
    print(f"gutter cuts: cols {[c for c, _ in col_bounds[1:]]} "
          f"rows {[r for r, _ in row_bounds[1:]]}")
    results = []
    for index, (filename, size) in enumerate(FURNITURE_ORDER):
        col, row = index % COLUMNS, index // COLUMNS
        x0, x1 = col_bounds[col]
        y0, y1 = row_bounds[row]
        cell = sheet.crop((x0, y0, x1, y1))
        icon, opaque = cell_to_icon(cell, threshold, max(size))
        if write and opaque > 0:
            # 目标画布 = 定义尺寸，内容等比缩入居中（保持家具原比例）。
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            fitted = icon.copy()
            fitted.thumbnail(size, Image.LANCZOS)
            canvas.paste(
                fitted,
                ((size[0] - fitted.width) // 2,
                 (size[1] - fitted.height) // 2),
                fitted,
            )
            canvas.save(os.path.join(FURNITURE_DIR, filename))
        results.append((filename, opaque))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="拆 2x2 家具素材表")
    parser.add_argument("sheet")
    parser.add_argument("--threshold", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    results = split_sheet(args.sheet, args.threshold,
                          write=not args.dry_run)
    empty = [name for name, opaque in results if opaque <= 0]
    for name, opaque in results:
        print(f"{name:<18} opaque px: {opaque:>7}  "
              f"{'OK' if opaque > 0 else 'EMPTY!'}")
    if empty:
        print(f"警告：{len(empty)} 个格子为空：{empty}")
        return 1
    if not args.dry_run:
        print(f"已写入 {FURNITURE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
