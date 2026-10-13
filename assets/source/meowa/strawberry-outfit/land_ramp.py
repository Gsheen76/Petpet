# -*- coding: utf-8 -*-
"""drag_land 落地渐缩坡道：帧 0=1.05 → 帧 6=1.00（线性）。

提起来放大到 1.16 后，触地瞬间从 630 直跳 576 会有 -8.7% 的突变；
给 land 前段一个 1.05 起步的坡道，触地只 -4%（读作落地压缩），
末帧精确回 576 与 idle 无缝。锚点=底边 606（爪不离地）+ 内容水平中心。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

LAND = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry\drag_land")
BOTTOM = 606.0
CX = 306.5  # 内容水平中心（左152 右461 中点）


def premult_scale(img: Image.Image, scale: float) -> np.ndarray:
    arr = np.asarray(img).astype(np.float64)
    a = arr[..., 3] / 255.0
    pm = np.empty_like(arr)
    pm[..., :3] = arr[..., :3] * a[..., None]
    pm[..., 3] = arr[..., 3]
    new_w = round(img.width * scale)
    new_h = round(img.height * scale)
    chans = [
        np.asarray(
            Image.fromarray(pm[..., i].astype(np.float32), mode="F").resize(
                (new_w, new_h), Image.LANCZOS),
            dtype=np.float64)
        for i in range(4)
    ]
    out = np.stack(chans, axis=-1)
    a2 = np.clip(out[..., 3] / 255.0, 0, 1)
    safe = a2 > 0.003
    rgb = np.zeros_like(out[..., :3])
    rgb[safe] = out[..., :3][safe] / a2[safe, None]
    return np.concatenate([np.clip(rgb, 0, 255), (a2 * 255)[:, :, None]], axis=-1)


def paste(canvas: np.ndarray, src: np.ndarray, tx: int, ty: int) -> None:
    h2, w2 = src.shape[:2]
    size = canvas.shape[0]
    xs0, ys0 = max(0, tx), max(0, ty)
    xs1, ys1 = min(size, tx + w2), min(size, ty + h2)
    if xs1 > xs0 and ys1 > ys0:
        canvas[ys0:ys1, xs0:xs1] = src[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]


def main() -> int:
    paths = sorted(LAND.glob("*.png"))
    n = len(paths)
    for i, p in enumerate(paths):
        s = 1.0 + 0.05 * (1 - i / (n - 1))
        if abs(s - 1.0) < 1e-9:
            print(f"{p.name}: scale 1.0000（末帧不动）")
            continue
        a = np.asarray(Image.open(p))
        m = a[..., 3] > 50
        ys, xs = np.where(m)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        pad = 6
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cell = Image.fromarray(a[cy0:y1 + pad + 1, cx0:x1 + pad + 1], "RGBA")
        scaled = premult_scale(cell, s)
        # 缩放后内容底/中心在 cell 内的位置
        s_cx = ((x0 + x1 + 1) / 2 - cx0) * s
        s_bottom = (y1 + 1 - cy0) * s
        tx = round(CX - s_cx)
        ty = round(BOTTOM - s_bottom)
        canvas = np.zeros((640, 640, 4))
        paste(canvas, scaled, tx, ty)
        # uint8 后校正底边与中心（量最终物）
        f = np.clip(np.round(canvas), 0, 255).astype(np.uint8)
        m2 = f[..., 3] > 50
        ys2, xs2 = np.where(m2)
        dx = int(round(CX - (xs2.min() + xs2.max() + 1) / 2))
        dy = int(BOTTOM) - int(ys2.max())
        if dx or dy:
            shifted = np.zeros_like(f)
            hh, ww = shifted.shape[:2]
            xs0, ys0 = max(0, dx), max(0, dy)
            xs1, ys1 = min(ww, dx + ww), min(hh, dy + hh)
            shifted[ys0:ys1, xs0:xs1] = f[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            f = shifted
        Image.fromarray(f, "RGBA").save(p)
        m3 = np.asarray(Image.open(p))[..., 3] > 50
        ys3, xs3 = np.where(m3)
        print(f"{p.name}: scale {s:.4f} → 高 {ys3.max()-ys3.min()+1} 底 {ys3.max()} 中心 {(xs3.min()+xs3.max()+1)/2:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
