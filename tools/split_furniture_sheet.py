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
from sheet_utils import axis_bounds, nonwhite_mask, soft_matte_from_white

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FURNITURE_DIR = os.path.join(ROOT, "assets", "runtime", "furniture", "home")

# 顺序 = 提示词顺序（行优先）→ (asset 文件名, 定义尺寸)。
def _definition_sizes():
    """从 HOME_DECORATION_DEFINITIONS 读 asset 文件名 → 定义尺寸。

    单一事实源（2026-09-15 技术债 C2）：此前尺寸在定义与拆分器
    双份维护，改一边即静默失同步。
    """
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    from petpet.progression.core import HOME_DECORATION_DEFINITIONS
    return {
        definition["asset"]: tuple(definition["size"])
        for definition in HOME_DECORATION_DEFINITIONS.values()
        if definition.get("asset")
    }


# 每批只声明拆分顺序（asset 文件名），尺寸一律取定义。
FURNITURE_SETS = {
    "new": ("lamp.png", "bookshelf.png", "round_table.png",
            "toy_basket.png"),
    "legacy": ("rug.png", "sofa.png", "plant.png", "wall_art.png"),
    "cozy2": ("clock.png", "cat_tree.png", "pet_bed.png",
              "rocking_chair.png"),
}
FURNITURE_ORDER = FURNITURE_SETS["new"]

COLUMNS = 2


def split_sheet(sheet_path: str, threshold: int = 240,
                write: bool = True, order=None) -> list[tuple[str, int]]:
    order = order or FURNITURE_ORDER
    sheet = Image.open(sheet_path).convert("RGBA")
    # 透明输入模式（2026-09-13：用户自行去背景的素材表）——背景已是
    # 真 alpha，按 alpha 分格/裁切，跳过白底抠图整条链路，边缘软硬
    # 完全尊重用户处理结果。
    import numpy as _np
    _alpha = _np.asarray(sheet)[..., 3]
    transparent_input = (_alpha < 243).mean() > 0.30
    if transparent_input:
        mask = _alpha > 12
    else:
        mask = nonwhite_mask(sheet, threshold)
    rows = -(-len(order) // COLUMNS)
    col_bounds = axis_bounds(mask, COLUMNS, axis=1)
    row_bounds = axis_bounds(mask, rows, axis=0)
    print(f"gutter cuts: cols {[c for c, _ in col_bounds[1:]]} "
          f"rows {[r for r, _ in row_bounds[1:]]}")
    results = []
    sizes = _definition_sizes()
    for index, filename in enumerate(order):
        size = sizes.get(filename)
        if size is None:
            raise SystemExit(f"定义中找不到 {filename} 的尺寸")
        col, row = index % COLUMNS, index // COLUMNS
        x0, x1 = col_bounds[col]
        y0, y1 = row_bounds[row]
        cell = sheet.crop((x0, y0, x1, y1))
        if transparent_input:
            # 用户已去背景：直接按 alpha 取内容框，不动颜色与边缘。
            matte = np.asarray(cell)[..., 3]
            ys, xs = np.nonzero(matte > 12)
            if len(xs) == 0:
                results.append((filename, 0))
                continue
            cropped = cell.crop(
                (int(xs.min()), int(ys.min()),
                 int(xs.max()) + 1, int(ys.max()) + 1))
        else:
            # 认真抠图（2026-09-12）：连通背景判定 + 边缘软 alpha 反混色，
            # 替代旧的硬白阈值（奶油色家具被误蚀/留白毛边的根源）。
            icon = soft_matte_from_white(cell)
            matte = np.asarray(icon)[..., 3]
            ys, xs = np.nonzero(matte > 12)
            if len(xs) == 0:
                if write:
                    print(f"{filename}: 空格子跳过")
                results.append((filename, 0))
                continue
            cropped = icon.crop(
                (int(xs.min()), int(ys.min()),
                 int(xs.max()) + 1, int(ys.max()) + 1))
        if write:
            # 目标画布 = 定义尺寸，内容等比缩入居中（保持家具原比例）。
            canvas = Image.new("RGBA", size, (0, 0, 0, 0))
            fitted = cropped.copy()
            fitted.thumbnail(size, Image.LANCZOS)
            canvas.paste(
                fitted,
                ((size[0] - fitted.width) // 2,
                 (size[1] - fitted.height) // 2),
                fitted,
            )
            canvas.save(os.path.join(FURNITURE_DIR, filename))
        results.append((filename, int((matte > 12).sum())))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="拆 2x2 家具素材表")
    parser.add_argument("sheet")
    parser.add_argument("--threshold", type=int, default=240)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--set", choices=tuple(FURNITURE_SETS), default="new",
        help="素材表批次：new=新四件（灯/书架/茶几/藤篮），"
             "legacy=旧四件重制（地毯/沙发/绿植/墙画）",
    )
    args = parser.parse_args()
    results = split_sheet(
        args.sheet, args.threshold,
        write=not args.dry_run,
        order=FURNITURE_SETS[args.set],
    )
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
