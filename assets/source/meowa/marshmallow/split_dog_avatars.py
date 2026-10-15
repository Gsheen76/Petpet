# -*- coding: utf-8 -*-
"""双犬刺绣贴纸 → 两只 avatar.png（圆形刺绣框外透明，630² RGBA）。

左=午餐肉（杏框柴犬）、右=冰淇淋（紫框白绒犬）。
分割：底布=灰麻纹理；圆框=非底布色的最大圆形内容——按行/列投影取
内容 bbox，圆心=bbox 中心、半径=bbox 短边/2（框是正圆）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = Path(r"C:\Users\sheen\Downloads\粉彩双犬刺绣头像贴纸.png")
PETS = Path(r"D:\Agent_project\Petpet\assets\runtime\pets")


def extract_avatar(im: Image.Image) -> Image.Image:
    a = np.asarray(im.convert("RGB")).astype(int)
    h, w = a.shape[:2]
    # 底布色：四角中位数
    corners = np.concatenate([
        a[:40, :40].reshape(-1, 3), a[:40, -40:].reshape(-1, 3),
        a[-40:, :40].reshape(-1, 3), a[-40:, -40:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.abs(a - bg).sum(axis=-1)
    content = dist > 60
    # 去小块噪点（麻布纹理反光）
    content = ndimage.binary_opening(content, iterations=2)
    content = ndimage.binary_closing(content, iterations=6)
    lab, n = ndimage.label(content)
    if n:
        sizes = ndimage.sum(content, lab, range(1, n + 1))
        content = lab == (np.argmax(sizes) + 1)
    ys, xs = np.where(content)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
    r = min(x1 - x0, y1 - y0) / 2
    # 圆形蒙版（外扩 2px 保框缘完整，边缘 3px 羽化）
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    alpha = np.clip((r + 2 - d) / 3.0, 0, 1)
    out = np.dstack([a.astype(np.uint8), (alpha * 255).astype(np.uint8)])
    side = int(2 * r + 8)
    crop = Image.fromarray(out, "RGBA").crop((
        int(cx - side / 2), int(cy - side / 2),
        int(cx + side / 2), int(cy + side / 2)))
    return crop.resize((630, 630), Image.LANCZOS)


def main() -> None:
    im = Image.open(SRC)
    w = im.width
    halves = {
        "lunch_meat": im.crop((0, 0, w // 2, im.height)),
        "ice_cream": im.crop((w // 2, 0, w, im.height)),
    }
    for pet_id, half in halves.items():
        av = extract_avatar(half)
        av.save(PETS / pet_id / "avatar.png")
        a = np.asarray(av)
        ys, xs = np.where(a[..., 3] > 50)
        print(f"{pet_id}: 630² 圆形覆盖 {(a[...,3]>50).mean()*100:.0f}% "
              f"内容 x[{xs.min()}-{xs.max()}] y[{ys.min()}-{ys.max()}]")


if __name__ == "__main__":
    main()
