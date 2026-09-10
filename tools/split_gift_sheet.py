# -*- coding: utf-8 -*-
"""礼物素材表拆分器（2026-09-09 礼物正式素材轮）。

把生图 AI 产出的 3×3 九宫格礼物素材表拆成 9 张独立图标，替换
assets/runtime/ui/gifts/ 下的运行时素材（同名覆盖，引用链不动）。

处理链：3×3 等分格 → 近白转透明（阈值可调）→ 内容 bbox 裁剪 →
方形画布居中 → LANCZOS 缩放到 340×340 → PNG 落盘。

格子顺序 = 提示词顺序（从左到右、从上到下）：
  甜心曲奇 / 元气布丁 / 香香起司
  肉肉罐头 / 毛绒小球 / 莓莓小篮
  爱心礼盒 / 暖暖小毯 / 亮晶晶奖牌

用法：python tools/split_gift_sheet.py <素材表.png> [--threshold 240]
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
GIFTS_DIR = os.path.join(ROOT, "assets", "runtime", "ui", "gifts")

# 顺序 = 提示词九宫格顺序（行优先）。
GIFT_ORDER = (
    "sweet_cookie", "milk_pudding", "cheese_cubes",
    "meat_can", "plush_ball", "berry_basket",
    "love_box", "warm_blanket", "shiny_medal",
)

OUTPUT_SIZE = 340
# 方形画布上的安全边距（内容最大占 92%），防贴边裁切。
PAD_RATIO = 0.92


def split_sheet(sheet_path: str, threshold: int = 240,
                write: bool = True) -> list[tuple[str, int]]:
    """拆表；返回 [(gift_id, 不透明像素数)]；write=False 只统计不落盘。"""
    sheet = Image.open(sheet_path).convert("RGBA")
    mask = nonwhite_mask(sheet, threshold)
    col_bounds = axis_bounds(mask, 3, axis=1)
    row_bounds = axis_bounds(mask, 3, axis=0)
    print(f"gutter cuts: cols {[c for c, _ in col_bounds[1:]]} "
          f"rows {[r for r, _ in row_bounds[1:]]}")
    results = []
    for index, gift_id in enumerate(GIFT_ORDER):
        col, row = index % 3, index // 3
        x0, x1 = col_bounds[col]
        y0, y1 = row_bounds[row]
        cell = sheet.crop((x0, y0, x1, y1))
        icon, opaque = cell_to_icon(cell, threshold, OUTPUT_SIZE)
        results.append((gift_id, opaque))
        if write and opaque > 0:
            icon.save(os.path.join(GIFTS_DIR, f"{gift_id}.png"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="拆 3×3 礼物素材表")
    parser.add_argument("sheet", help="生图 AI 产出的素材表路径")
    parser.add_argument("--threshold", type=int, default=240,
                        help="近白判定阈值（默认 240）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只统计不写文件")
    args = parser.parse_args()

    results = split_sheet(args.sheet, args.threshold, write=not args.dry_run)
    empty = [gift_id for gift_id, opaque in results if opaque <= 0]
    for gift_id, opaque in results:
        status = "OK" if opaque > 0 else "EMPTY!"
        print(f"{gift_id:<14} opaque px: {opaque:>7}  {status}")
    if empty:
        print(f"警告：{len(empty)} 个格子为空：{empty}")
        print("请确认素材表是标准 3×3 且顺序与提示词一致。")
        return 1
    if not args.dry_run:
        print(f"已写入 {GIFTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
