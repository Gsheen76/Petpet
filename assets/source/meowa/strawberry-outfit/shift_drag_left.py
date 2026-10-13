# -*- coding: utf-8 -*-
"""drag 族向左平移到与 idle 主体同一垂直线（用户 2026-10-12 指令）。

实测：idle 核心质心 302.2；drag/sway/hover 整体质心 +18 偏右 → 统一 -18；
drag_land 逐帧质心 316.4→306.7 → 斜坡 [-14,-10,-6,-4,-4,-4,-4]
（首帧接 sway 末帧线、末帧接 idle 线，双双无缝；帧间差 4,4,2,0.. 平滑收敛）。
纯水平整数平移，底线/帧内容零改动。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry")
SHIFTS = {
    "drag": [-18] * 19,
    "drag_sway": [-18] * 12,
    "drag_hover": [-18] * 3,
    "drag_land": [-14, -10, -6, -4, -4, -4, -4],
}


def shift_left(a: np.ndarray, dx: int) -> np.ndarray:
    if dx == 0:
        return a
    out = np.zeros_like(a)
    if dx < 0:
        out[:, :dx] = a[:, -dx:]
    else:
        out[:, dx:] = a[:, :-dx]
    return out


def main() -> None:
    for anim, shifts in SHIFTS.items():
        paths = sorted((BASE / anim).glob("*.png"))
        assert len(paths) == len(shifts), f"{anim}: {len(paths)} 帧 vs {len(shifts)} 平移量"
        cxs_after = []
        for p, dx in zip(paths, shifts):
            a = np.asarray(Image.open(p))
            Image.fromarray(shift_left(a, dx), "RGBA").save(p)
            b = np.asarray(Image.open(p))
            ys, xs = np.where(b[..., 3] > 50)
            cxs_after.append(xs.mean())
        rng = f"[{min(cxs_after):.1f}~{max(cxs_after):.1f}]"
        print(f"{anim:<12} 平移 {shifts[0]}..{shifts[-1]} → 质心 {rng}")


if __name__ == "__main__":
    main()
