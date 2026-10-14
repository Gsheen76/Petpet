# -*- coding: utf-8 -*-
"""棉花糖八套逐帧偏移取证 II：腹部冻区 SAD（窗口=全帧实心交集 y60-85%带）。

每帧报告 vs 参照帧的最优整数平移——(0,0) 即已对齐；非零=真偏移。
参照：帧 0（+分相位参照 pet/eat/dig/happy 的动作中段帧）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

PET = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\marshmallow\desktop\animations")
ANIMS = ["idle", "pet", "eat", "play", "dig", "happy", "sleep", "drag"]


def solid(a):
    return a[..., 3] > 60


def best_shift(a, ref, y0, y1, x0, x1, rng=4):
    w1 = a[y0:y1, x0:x1, :3].astype(np.int16)
    w2 = ref[y0:y1, x0:x1, :3].astype(np.int16)
    best = (float(np.abs(w1 - w2).mean()), 0, 0)
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            if dx == 0 and dy == 0:
                continue
            sh = np.roll(np.roll(w1, dy, axis=0), dx, axis=1)
            sad = float(np.abs(sh - w2).mean())
            if sad < best[0] - 1e-9:
                best = (sad, dx, dy)
    return best


def main() -> int:
    for anim in ANIMS:
        paths = sorted((PET / anim).glob("*.png"))
        arrs = [np.asarray(Image.open(p)) for p in paths]
        n = len(arrs)
        inter = np.logical_and.reduce([solid(a) for a in arrs])
        inter = ndimage.binary_erosion(inter, iterations=3)
        ys, xs = np.where(inter)
        if len(ys) < 500:
            print(f"== {anim}: 交集窗口太小（{len(ys)}px），跳过")
            continue
        iy0, iy1 = int(ys.min()), int(ys.max())
        band_y0 = iy0 + int((iy1 - iy0) * 0.60)
        band_y1 = iy0 + int((iy1 - iy0) * 0.85)
        win = inter.copy()
        win[:band_y0, :] = False
        win[band_y1:, :] = False
        wys, wxs = np.where(win)
        if len(wys) < 300:
            print(f"== {anim}: 腹带窗口太小（{len(wys)}px），放宽到全交集")
            win = inter
            wys, wxs = np.where(win)
        x0, x1 = int(wxs.min()) + 4, int(wxs.max()) - 3
        y0, y1 = max(band_y0, int(wys.min())) + 3, min(band_y1, int(wys.max())) - 3
        print(f"== {anim}（{n}帧）腹窗 x[{x0}..{x1}] y[{y0}..{y1}] ==")
        results = []
        for i in range(n):
            sad, dx, dy = best_shift(arrs[i], arrs[0], y0, y1, x0, x1)
            results.append((dx, dy))
            mark = "" if (dx, dy) == (0, 0) else "  ← 偏移"
            print(f"  {i:2d}: ({dx:+d},{dy:+d})  SAD {sad:.2f}{mark}")
        moved = [(i, d) for i, d in enumerate(results) if d != (0, 0)]
        print(f"  小结: {len(moved)}/{n} 帧偏移 {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
