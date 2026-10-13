# -*- coding: utf-8 -*-
"""Phase 3+4：胸腹冻结区 SAD 整数对齐——根治 bbox 软边噪声注入的 ±1.5px 帧间抖动。

窗口 = 全帧实心交集在胸部带（y 470-595）内的自动求交（避开眨眼/嘴型/尾巴）。
每帧在 ±3px 内搜 SAD 最小整数平移，对齐到帧 0。原地修运行时帧。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

IDLE = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry\idle")


def solid(a):
    return a[..., 3] > 60


def main() -> int:
    paths = sorted(IDLE.glob("*.png"))
    arrs = [np.asarray(Image.open(p)) for p in paths]
    n = len(arrs)

    # 自动画窗：胸部带交集
    inter = np.logical_and.reduce([solid(a) for a in arrs])
    band = np.zeros_like(inter)
    band[470:596, :] = True
    win_mask = inter & band
    win_mask = ndimage.binary_erosion(win_mask, iterations=2)
    ys, xs = np.where(win_mask)
    x0, x1, y0, y1 = int(xs.min()) + 4, int(xs.max()) - 3, 470 + 4, 596 - 3
    print(f"胸部窗口: x[{x0}..{x1}] y[{y0}..{y1}] ({x1-x0+1}x{y1-y0+1})")

    ref = arrs[0][y0:y1, x0:x1, :3].astype(np.int16)
    shifts = []
    print("\n帧  最优平移  SAD(对齐前→后)")
    for i, a in enumerate(arrs):
        win = a[y0:y1, x0:x1, :3].astype(np.int16)
        best = (0, 0)
        best_sad = float(np.abs(win - ref).mean())
        before = best_sad
        if i > 0:
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    sh = np.roll(np.roll(win, dy, axis=0), dx, axis=1)
                    sad = float(np.abs(sh - ref).mean())
                    if sad < best_sad:
                        best_sad = sad
                        best = (dx, dy)
        shifts.append(best)
        print(f"{i:2d}  {best}  {before:.2f} → {best_sad:.2f}")

    # 应用平移（dx>0 = 内容右移）
    applied = 0
    for i, (a, (dx, dy)) in enumerate(zip(arrs, shifts)):
        if (dx, dy) == (0, 0):
            continue
        out = np.zeros_like(a)
        out[..., :3] = np.roll(np.roll(a[..., :3], dy, axis=0), dx, axis=1)
        out[..., 3] = np.roll(np.roll(a[..., 3], dy, axis=0), dx, axis=1)
        Image.fromarray(out, "RGBA").save(paths[i])
        applied += 1
    print(f"\n应用平移 {applied}/{n} 帧")

    # 复测：眼簇/爪带
    arrs2 = [np.asarray(Image.open(p)) for p in paths]
    eyes, paws = [], []
    for a in arrs2:
        m = solid(a)
        rgb = a[..., :3].astype(float)
        lum = rgb.mean(axis=-1)
        ysb, xsb = np.where(m)
        y0b, y1b = ysb.min(), ysb.max()
        head = np.zeros_like(m); head[y0b:int(y0b + (y1b - y0b) * 0.45), :] = True
        dark = m & head & (lum < 95)
        hy, hx = np.where(dark)
        eyes.append(float(hx[hx > hx.max() - 40].mean()) if len(hx) else float("nan"))
        foot = np.zeros_like(m); foot[y1b - max(2, int((y1b - y0b) * 0.06)):, :] = True
        foot &= m
        fy, fx = np.where(foot)
        paws.append(float(fx.mean()))
    print(f"复测 眼簇cx: σ={np.std(eyes):.2f} 极差={max(eyes)-min(eyes):.2f}")
    print(f"复测 爪带cx: σ={np.std(paws):.2f} 极差={max(paws)-min(paws):.2f}")
    ok = (max(eyes) - min(eyes)) <= 0.6 and (max(paws) - min(paws)) <= 0.6
    print("PASS" if ok else "STILL_WOBBLE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
