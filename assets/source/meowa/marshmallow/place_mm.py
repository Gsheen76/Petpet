# -*- coding: utf-8 -*-
"""marshmallow 通用落位器：源帧（960² 提取帧）→ 640 画布。

锚：底 606 + 鼻尖左缘（兔朝左，左缘=鼻尖全帧恒定；耳朵在顶/尾在后自由动）。
scale 常量按各动画指定。uint8 后整数校正（量最终物）。
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
from PIL import Image


def premult_scale(img: Image.Image, scale: float) -> np.ndarray:
    arr = np.asarray(img).astype(np.float64)
    a = arr[..., 3] / 255.0
    pm = np.empty_like(arr)
    pm[..., :3] = arr[..., :3] * a[..., None]
    pm[..., 3] = arr[..., 3]
    nw, nh = round(img.width * scale), round(img.height * scale)
    chans = [
        np.asarray(Image.fromarray(pm[..., i].astype(np.float32), mode="F").resize((nw, nh), Image.LANCZOS), dtype=np.float64)
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
    xs0, ys0 = max(0, tx), max(0, ty)
    xs1 = min(canvas.shape[1], tx + w2)
    ys1 = min(canvas.shape[0], ty + h2)
    if xs1 > xs0 and ys1 > ys0:
        canvas[ys0:ys1, xs0:xs1] = src[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]


def place_frames(frames_dir: Path, out_dir: Path, scale: float,
                 target_left: int, target_bottom: int = 606,
                 keep: list[int] | None = None,
                 anchor_source_y: int | None = None) -> list[Path]:
    """按左缘+底双锚落位；keep 选帧（None=全部）。

    anchor_source_y：以源画布上的固定地线（如 dig 的兔子爪线 884）为
    垂直锚，bbox 底可能含道具（土堆）垂到锚线下。None=用 bbox 底。"""
    paths = sorted(frames_dir.glob("*.png"))
    idxs = keep if keep is not None else list(range(len(paths)))
    out_dir.mkdir(parents=True, exist_ok=True)
    outs = []
    for out_i, i in enumerate(idxs):
        a = np.asarray(Image.open(paths[i]))
        m = a[..., 3] > 50
        ys, xs = np.where(m)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        pad = 6
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cell = Image.fromarray(a[cy0:y1 + pad + 1, cx0:x1 + pad + 1], "RGBA")
        scaled = premult_scale(cell, scale)
        s_left = (x0 - cx0) * scale
        anchor_y = (anchor_source_y if anchor_source_y is not None else y1) + 1
        s_bottom = (anchor_y - cy0) * scale
        tx = round(target_left + 0.5 - s_left)
        ty = round(target_bottom + 0.5 - s_bottom)
        canvas = np.zeros((640, 640, 4))
        paste(canvas, scaled, tx, ty)
        f = np.clip(np.round(canvas), 0, 255).astype(np.uint8)
        m2 = f[..., 3] > 50
        ys2, xs2 = np.where(m2)
        dx = target_left - int(xs2.min())
        if anchor_source_y is None:
            dy = target_bottom - int(ys2.max())
        else:
            dy = round((anchor_source_y + 1 - ys.min() - (ys.min() - cy0)) * 0) or (
                round(target_bottom - (anchor_source_y - cy0) * scale - ty))
        if dx or dy:
            sh = np.zeros_like(f)
            hh, ww = sh.shape[:2]
            xs0, ys0 = max(0, dx), max(0, dy)
            xs1, ys1 = min(ww, dx + ww), min(hh, dy + hh)
            sh[ys0:ys1, xs0:xs1] = f[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            f = sh
        p = out_dir / f"{out_i:03d}.png"
        Image.fromarray(f, "RGBA").save(p)
        outs.append(p)
    return outs


def solid_measure(p: Path):
    a = np.asarray(Image.open(p))
    m = a[..., 3] > 50
    ys, xs = np.where(m)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def report(out_dir: Path, tag: str) -> None:
    lefts, rights, bots, tops = [], [], [], []
    for p in sorted(out_dir.glob("*.png")):
        l, r, t, b = solid_measure(p)
        lefts.append(l); rights.append(r); bots.append(b); tops.append(t)
    print(f"{tag}: 左 {sorted(set(lefts))} 底 {sorted(set(bots))} "
          f"顶 {min(tops)}..{max(tops)} 右 {min(rights)}..{max(rights)}")
