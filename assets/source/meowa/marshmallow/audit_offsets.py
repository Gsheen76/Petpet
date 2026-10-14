# -*- coding: utf-8 -*-
"""棉花糖八套动画逐帧偏移取证。

锚选择（按动画类型）：
- 眼簇 cx（头带深色像素质心）——头部稳定类动画的真锚
- 接触patch cx（底 10% 带最大连通域质心）——接地类
- 底线/左缘/右缘——bbox 硬边
- 躯干窗 SAD vs 首/相位参照帧——雕像类真值
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

PET = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\marshmallow\desktop\animations")
ANIMS = ["idle", "pet", "eat", "play", "dig", "happy", "sleep", "drag"]


def solid(a):
    return a[..., 3] > 50


def eye_cx(a):
    m = solid(a)
    rgb = a[..., :3].astype(float)
    lum = rgb.mean(axis=-1)
    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    head = np.zeros_like(m)
    head[y0:int(y0 + (y1 - y0) * 0.40), :] = True  # 兔头低（耳占比大）
    dark = m & head & (lum < 95)
    hy, hx = np.where(dark)
    return float(hx.mean()) if len(hx) else float("nan")


def contact_cx(a):
    m = solid(a)
    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    band = np.zeros_like(m)
    band[y1 - max(2, int((y1 - y0) * 0.10)):, :] = True
    band &= m
    lab, n = ndimage.label(band)
    if n == 0:
        return float("nan")
    sizes = ndimage.sum(band, lab, range(1, n + 1))
    cy, cx = np.where(lab == np.argmax(sizes) + 1)
    return float(cx.mean())


def bbox_of(a):
    m = solid(a)
    ys, xs = np.where(m)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def torso_sad(a, ref, y0, y1, x0, x1):
    w1 = a[y0:y1, x0:x1, :3].astype(np.int16)
    w2 = ref[y0:y1, x0:x1, :3].astype(np.int16)
    best = None
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            sh = np.roll(np.roll(w1, dy, axis=0), dx, axis=1)
            sad = float(np.abs(sh - w2).mean())
            if best is None or sad < best[0]:
                best = (sad, dx, dy)
    return best  # (sad, dx, dy)——(0,0) 即已对齐


def main() -> int:
    for anim in ANIMS:
        paths = sorted((PET / anim).glob("*.png"))
        arrs = [np.asarray(Image.open(p)) for p in paths]
        n = len(arrs)
        eyes = [eye_cx(a) for a in arrs]
        cons = [contact_cx(a) for a in arrs]
        lefts = [bbox_of(a)[0] for a in arrs]
        bots = [bbox_of(a)[2 + 1] for a in arrs]
        print(f"== {anim}（{n}帧）==")
        print("  帧  眼簇cx  接触cx   左缘  底线")
        for i in range(n):
            print(f"  {i:2d}  {eyes[i]:7.1f} {cons[i]:7.1f} {lefts[i]:5d} {bots[i]:5d}")
        ev = [e for e in eyes if not np.isnan(e)]
        cv = [c for c in cons if not np.isnan(c)]
        print(f"  眼簇极差 {max(ev)-min(ev):.2f}  接触极差 {max(cv)-min(cv):.2f}  "
              f"左缘集 {sorted(set(lefts))[:6]}  底线集 {sorted(set(bots))[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
