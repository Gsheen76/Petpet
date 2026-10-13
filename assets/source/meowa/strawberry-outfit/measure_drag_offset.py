# -*- coding: utf-8 -*-
"""测量 idle 核心质心 vs drag 族整体质心的水平差（向左平移量依据）。"""
from __future__ import annotations

import glob
import statistics as st
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry")


def load(path) -> np.ndarray:
    return np.asarray(Image.open(path))


def bbox_of(a):
    m = a[..., 3] > 50
    ys, xs = np.where(m)
    return xs.min(), xs.max(), ys.min(), ys.max()


def core_cx(a):
    """待机核心：躯干窗（x 38-78%、y 42-88%）质心——排除左侧扫动尾巴。"""
    m = a[..., 3] > 50
    x0, x1, y0, y1 = bbox_of(a)
    win = np.zeros_like(m)
    win[int(y0 + (y1 - y0) * 0.42): int(y0 + (y1 - y0) * 0.88),
        int(x0 + (x1 - x0) * 0.38): int(x0 + (x1 - x0) * 0.78)] = True
    win &= m
    wy, wx = np.where(win)
    return float(wx.mean())


def solid_stats(a):
    m = a[..., 3] > 50
    ys, xs = np.where(m)
    return float(xs.mean()), int(ys.max())


idle_frames = [load(p) for p in sorted((BASE / "idle").glob("*.png"))]
idle_core = st.median([core_cx(a) for a in idle_frames])
print(f"idle 核心质心 cx 中位 = {idle_core:.1f}  (24帧 core cx 范围 "
      f"{min(core_cx(a) for a in idle_frames):.1f}~{max(core_cx(a) for a in idle_frames):.1f})")
print(f"{'动画':<12}{'整体质心cx':>12}{'与idle差':>10}{'底线':>6}{'帧数':>5}")
for anim in ("drag", "drag_sway", "drag_hover", "drag_land"):
    paths = sorted((BASE / anim).glob("*.png"))
    if not paths:
        print(f"{anim:<12}（无帧目录）")
        continue
    cxs, bots = [], []
    for p in paths:
        cx, bot = solid_stats(load(p))
        cxs.append(cx)
        bots.append(bot)
    med = st.median(cxs)
    rng = f"[{min(cxs):.0f}~{max(cxs):.0f}]"
    print(f"{anim:<12}{med:>12.1f}{med - idle_core:>+10.1f}{st.median(bots):>6}{len(paths):>5}  {rng}")
