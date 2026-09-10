# -*- coding: utf-8 -*-
"""气泡菜单按键素材表拆分器（2026-09-09 精细抠图版）。

把生图 AI 产出的六列三行、18 图标素材表拆成独立图标，暂存
assets/source/bubble_menu_drafts/。分割走 gutter 检测（白隙中心下刀，
AI 图栅格漂移不会切到邻居/切丢自己，见 sheet_utils），格子内再按
内容 bbox 裁剪到 240² 方形画布。

用法：python tools/split_button_sheet.py <素材表.png> [--threshold 240]
       python tools/split_button_sheet.py <素材表.png> --runtime  # 直接写 runtime
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet_utils import axis_bounds, cell_to_icon, nonwhite_mask

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_DIR = os.path.join(ROOT, "assets", "source", "bubble_menu_drafts")
RUNTIME_DIR = os.path.join(
    ROOT, "assets", "runtime", "ui", "bubble_menu",
)

# 顺序 = 提示词顺序（行优先）：主菜单 6 + 互动 4 + 更多 8。
BUTTON_ORDER = (
    # primary
    "chat", "pet_profile", "home", "shop", "interaction", "more",
    # interaction
    "pet", "feed", "play", "sleep",
    # more
    "records", "achievements", "minigames", "settings",
    "hide", "tutorial", "back", "quit",
)

OUTPUT_SIZE = 240
COLUMNS = 6
ROWS = 3


def split_sheet(sheet_path: str, threshold: int = 240,
                write: bool = True, out_dir: str | None = None
                ) -> list[tuple[str, int]]:
    sheet = Image.open(sheet_path).convert("RGBA")
    mask = nonwhite_mask(sheet, threshold)
    width, height = sheet.size
    col_bounds = axis_bounds(mask, COLUMNS, axis=1)
    row_bounds = axis_bounds(mask, ROWS, axis=0)
    print(f"gutter cuts: cols {[c for c, _ in col_bounds[1:]]} "
          f"rows {[r for r, _ in row_bounds[1:]]}")
    results = []
    for index, action in enumerate(BUTTON_ORDER):
        col, row = index % COLUMNS, index // COLUMNS
        x0, x1 = col_bounds[col]
        y0, y1 = row_bounds[row]
        cell = sheet.crop((x0, y0, x1, y1))
        icon, opaque = cell_to_icon(cell, threshold, OUTPUT_SIZE)
        results.append((action, opaque))
        if write and opaque > 0:
            icon.save(os.path.join(out_dir or DRAFTS_DIR, f"{action}.png"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="拆 6x3 气泡按键素材表")
    parser.add_argument("sheet", help="生图 AI 产出的素材表路径")
    parser.add_argument("--threshold", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--runtime", action="store_true",
                        help="直接写入 assets/runtime/ui/bubble_menu（接线用）")
    args = parser.parse_args()

    out_dir = RUNTIME_DIR if args.runtime else DRAFTS_DIR
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
    results = split_sheet(args.sheet, args.threshold,
                          write=not args.dry_run, out_dir=out_dir)
    empty = [action for action, opaque in results if opaque <= 0]
    for action, opaque in results:
        print(f"{action:<12} opaque px: {opaque:>7}  "
              f"{'OK' if opaque > 0 else 'EMPTY!'}")
    if empty:
        print(f"警告：{len(empty)} 个格子为空：{empty}")
        return 1
    if not args.dry_run:
        print(f"已写入 {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
