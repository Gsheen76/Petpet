# -*- coding: utf-8 -*-
"""Phase 1 取证：待机 24 帧真实身体偏移（固定画布窗口互相关，禁用 bbox）。

窗口取全帧实心掩码交集的侵蚀中心区——保证每帧测的都是同一块冻体解剖。
同时输出眼簇/爪带质心做交叉验证。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

IDLE = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry\idle")


def phase_offset(ref: np.ndarray, mov: np.ndarray) -> tuple[float, float]:
    g1 = ref.astype(np.float64)
    g2 = mov.astype(np.float64)
    win = np.outer(np.hanning(g1.shape[0]), np.hanning(g1.shape[1]))
    g1w = (g1 - g1.mean()) * win
    g2w = (g2 - g2.mean()) * win
    cross = np.fft.fft2(g1w) * np.fft.fft2(g2w).conj()
    cross /= np.maximum(np.abs(cross), 1e-9)
    corr = np.fft.ifft2(cross).real
    py, px = np.unravel_index(np.argmax(corr), corr.shape)

    def sub(idx, axis):
        n = corr.shape[axis]
        def at(k):
            r = (idx + k) % n if axis == 0 else py
            c = px if axis == 0 else (idx + k) % n
            return corr[r, c]
        c0, c1, c2 = at(-1), at(0), at(1)
        den = c0 - 2 * c1 + c2
        return 0.0 if abs(den) < 1e-12 else float(np.clip(0.5 * (c0 - c2) / den, -1, 1))

    h, w = corr.shape
    dy = (py + sub(py, 0)) - (h if py > h // 2 else 0)
    dx = (px + sub(px, 1)) - (w if px > w // 2 else 0)
    return dx, dy


def main() -> int:
    paths = sorted(IDLE.glob("*.png"))
    arrs = [np.asarray(Image.open(p)) for p in paths]
    n = len(arrs)

    # 固定窗口 = 全帧实心交集侵蚀后的中心 bbox
    solids = [a[..., 3] > 60 for a in arrs]
    inter = np.logical_and.reduce(solids)
    inter = ndimage.binary_erosion(inter, iterations=3)
    ys, xs = np.where(inter)
    wx0, wx1 = int(xs.min()) + 8, int(xs.max()) - 8
    wy0, wy1 = int(ys.min()) + 8, int(ys.max()) - 8
    print(f"冻结体交集窗口: x[{wx0}..{wx1}] y[{wy0}..{wy1}] "
          f"({wx1-wx0+1}x{wy1-wy0+1})")
    # 窗口内再限定身体纹理丰富区（避免窗口大部分是透明）
    win_stack = [a[wy0:wy1, wx0:wx1, 3].astype(np.float64) for a in arrs]
    ref = win_stack[0]
    print("\n帧  窗口互相关(dx,dy)   眼簇cx   爪带cx   右缘  左缘")
    dxs, dys = [], []
    eyes, paws = [], []
    for i, (a, w_) in enumerate(zip(arrs, win_stack)):
        dx, dy = (0.0, 0.0) if i == 0 else phase_offset(ref, w_)
        dxs.append(dx); dys.append(dy)
        m = a[..., 3] > 60
        rgb = a[..., :3].astype(float)
        lum = rgb.mean(axis=-1)
        ysb, xsb = np.where(m)
        y0, y1 = ysb.min(), ysb.max()
        head = np.zeros_like(m); head[y0:int(y0 + (y1 - y0) * 0.45), :] = True
        dark = m & head & (lum < 95)
        hy, hx = np.where(dark)
        eye = float(hx[(hx > hx.max() - 40)].mean()) if len(hx) else float("nan")
        foot = np.zeros_like(m); foot[y1 - max(2, int((y1 - y0) * 0.06)):, :] = True
        foot &= m
        fy, fx = np.where(foot)
        paw = float(fx.mean()) if len(fx) else float("nan")
        eyes.append(eye); paws.append(paw)
        ys2, xs2 = np.where(m)
        print(f"{i:2d}  ({dx:+.2f},{dy:+.2f})  {eye:7.1f} {paw:7.1f}  {xs2.max()}  {xs2.min()}")
    dxs_a = np.abs(dxs[1:]); dys_a = np.abs(dys[1:])
    print(f"\n窗口互相关: |dx| max={dxs_a.max():.2f} σ={np.std(dxs):.2f} | "
          f"|dy| max={dys_a.max():.2f} σ={np.std(dys):.2f}")
    print(f"眼簇cx: σ={np.std(eyes):.2f} 极差={max(eyes)-min(eyes):.1f}")
    print(f"爪带cx: σ={np.std(paws):.2f} 极差={max(paws)-min(paws):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
