# -*- coding: utf-8 -*-
"""白底→透明抠图（水彩素材专用）：亮度+饱和度联合判定+软边+边缘收缩。

水彩画有淡彩笔触（接近白但带色），纯白阈值会漏淡彩底——用
「亮度>238 且饱和度<14」判底，边缘 2px 羽化，另做 1px 收缩防白边。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

TUT = Path(r"D:\Agent_project\Petpet\assets\runtime\ui\tutorial")


def clean(path: Path) -> None:
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    h, w = a.shape[:2]
    lum = a.mean(axis=-1)
    sat = a.max(axis=-1) - a.min(axis=-1)
    # 底=白/近白且低饱和
    bg = (lum > 236) & (sat < 16)
    # 补洞：内部白底通过 flood fill 从边框连出（保留眼白/高光）
    outside = ndimage.binary_propagation(
        np.pad(np.zeros((h, w), bool), 1, constant_values=True)[1:-1, 1:-1]
        if False else bg.copy(),
        mask=bg,
    ) if False else None
    # 简化：seed=边框上的 bg 像素，向内传播
    seed = np.zeros((h, w), bool)
    seed[0, :] = bg[0, :]
    seed[-1, :] = bg[-1, :]
    seed[:, 0] = bg[:, 0]
    seed[:, -1] = bg[:, -1]
    connected_bg = ndimage.binary_propagation(seed, mask=bg)
    alpha = np.where(connected_bg, 0, 255).astype(float)
    # 软边：alpha 高斯 1.2 + 1px 收缩（吃掉白边残留）
    alpha = ndimage.gaussian_filter(alpha, 1.2)
    solid = alpha > 128
    shrink = ndimage.binary_erosion(solid, iterations=1)
    alpha = np.where(shrink, np.maximum(alpha, 200), alpha)
    out = np.dstack([
        np.clip(a, 0, 255).astype(np.uint8),
        np.clip(alpha, 0, 255).astype(np.uint8),
    ])
    # 内容裁切
    ys, xs = np.where(alpha > 40)
    if len(ys) == 0:
        print(f"{path.name}: 空！跳过")
        return
    crop = Image.fromarray(out, "RGBA").crop(
        (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    crop.save(path)
    print(f"{path.name}: {crop.size} 透明占比 {(np.asarray(crop)[..., 3] < 20).mean()*100:.0f}%")


def main() -> None:
    for path in sorted(TUT.glob("tutorial_icon_*.png")):
        clean(path)


if __name__ == "__main__":
    main()
