# -*- coding: utf-8 -*-
"""sleep 落位（scale 常量可调）：帧 6-15 无缝呼吸环 → 640 画布。

锚：底 606（地线，与 idle 共线）+ 内容水平中心 320。
对色：整体分位 LUT → idle。
2026-10-14 用户令「睡觉动作小一点」：0.79 → 0.70。
"""
from __future__ import annotations

import glob

import numpy as np
from PIL import Image

SRC = r"D:\Agent_project\Petpet\assets\source\meowa\strawberry-outfit\v3-sleep"
OUT = SRC + r"\colored"
IDLE = sorted(glob.glob(
    r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop"
    r"\animations\outfits\strawberry\idle\*.png"))
KEEP = list(range(6, 16))
SCALE = 0.70
BOTTOM, CX = 606, 320.0


def premult_scale(img, scale):
    arr = np.asarray(img).astype(float)
    a = arr[..., 3] / 255.0
    pm = np.empty_like(arr)
    pm[..., :3] = arr[..., :3] * a[..., None]
    pm[..., 3] = arr[..., 3]
    nw, nh = round(img.width * scale), round(img.height * scale)
    chans = [np.asarray(Image.fromarray(pm[..., i].astype(np.float32), mode="F").resize((nw, nh), Image.LANCZOS), dtype=float) for i in range(4)]
    out = np.stack(chans, axis=-1)
    a2 = np.clip(out[..., 3] / 255.0, 0, 1)
    safe = a2 > 0.003
    rgb = np.zeros_like(out[..., :3])
    rgb[safe] = out[..., :3][safe] / a2[safe, None]
    return np.concatenate([np.clip(rgb, 0, 255), (a2 * 255)[:, :, None]], axis=-1)


def paste(cv, src, tx, ty):
    h2, w2 = src.shape[:2]
    xs0, ys0 = max(0, tx), max(0, ty)
    xs1 = min(cv.shape[1], tx + w2)
    ys1 = min(cv.shape[0], ty + h2)
    if xs1 > xs0 and ys1 > ys0:
        cv[ys0:ys1, xs0:xs1] = src[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]


def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    idle = np.concatenate([
        (lambda a: a[..., :3][a[..., 3] > 200].astype(float))(
            np.asarray(Image.open(p))) for p in IDLE])
    new_px = []
    for i in KEEP:
        a = np.asarray(Image.open(f"{SRC}\\frames\\{i:03d}.png"))
        new_px.append(a[..., :3][a[..., 3] > 200].astype(float))
    new = np.concatenate(new_px)
    luts = []
    for c in range(3):
        q = np.linspace(0, 1, 256)
        lut = np.maximum.accumulate(np.clip(
            np.interp(np.arange(256), np.quantile(new[:, c], q),
                      np.quantile(idle[:, c], q)), 0, 255))
        luts.append(lut)
    for out_i, i in enumerate(KEEP):
        a = np.asarray(Image.open(f"{SRC}\\frames\\{i:03d}.png"))
        ys, xs = np.where(a[..., 3] > 50)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        pad = 6
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cell = Image.fromarray(a[cy0:y1 + pad + 1, cx0:x1 + pad + 1], "RGBA")
        scaled = premult_scale(cell, SCALE)
        s_cx = ((x0 + x1 + 1) / 2 - cx0) * SCALE
        s_bot = (y1 + 1 - cy0) * SCALE
        tx = round(CX - s_cx)
        ty = round(BOTTOM - s_bot)
        canvas = np.zeros((640, 640, 4))
        paste(canvas, scaled, tx, ty)
        f = np.clip(np.round(canvas), 0, 255).astype(np.uint8)
        ys2, xs2 = np.where(f[..., 3] > 50)
        dx = int(round(CX - (xs2.min() + xs2.max() + 1) / 2))
        dy = int(BOTTOM) - int(ys2.max())
        if dx or dy:
            sh = np.zeros_like(f)
            hh, ww = sh.shape[:2]
            xs0, ys0 = max(0, dx), max(0, dy)
            xs1, ys1 = min(ww, dx + ww), min(hh, dy + hh)
            sh[ys0:ys1, xs0:xs1] = f[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            f = sh
        m3 = f[..., 3] > 10
        for c in range(3):
            f[..., c][m3] = luts[c][np.clip(f[..., c][m3].astype(int), 0, 255)]
        Image.fromarray(f, "RGBA").save(f"{OUT}\\{out_i:03d}.png")
    bots, tops = [], []
    for p in sorted(glob.glob(OUT + r"\*.png")):
        a = np.asarray(Image.open(p))
        ys, xs = np.where(a[..., 3] > 50)
        bots.append(int(ys.max())); tops.append(int(ys.min()))
    print(f"scale={SCALE} 底 {sorted(set(bots))} 高 {min(b-t+1 for b,t in zip(bots,tops))}-{max(b-t+1 for b,t in zip(bots,tops))}")


if __name__ == "__main__":
    main()
