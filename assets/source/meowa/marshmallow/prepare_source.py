# -*- coding: utf-8 -*-
"""marshmallow（棉花糖）源图处理：poses/idle.png + avatar.png + Meowa 参照图。

源图朝左 → 水平翻转朝右（与 lunch_meat 一致，facing 留空）。
画布规范：640²、内容高 575、底 606、水平居中（与草莓工具链同标定）。
参照：1150²、体高 62%、底边距 90（垫边规范）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(r"C:\Users\sheen\Downloads\粉彩水彩风可爱兔子贴图.png")
PET = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\marshmallow")
MEOWA = Path(r"D:\Agent_project\Petpet\assets\source\meowa\marshmallow")


def trim(im: Image.Image, thr: int = 10) -> Image.Image:
    a = np.asarray(im)
    ys, xs = np.where(a[..., 3] > thr)
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def premult_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    arr = np.asarray(im).astype(np.float64)
    al = arr[..., 3] / 255.0
    pm = arr.copy()
    pm[..., :3] *= al[..., None]
    chans = [
        np.asarray(Image.fromarray(pm[..., c].astype(np.float32), mode="F").resize(size, Image.LANCZOS), dtype=np.float64)
        for c in range(4)
    ]
    out = np.stack(chans, axis=-1)
    a2 = np.clip(out[..., 3] / 255.0, 0, 1)
    safe = a2 > 0.003
    rgb = np.zeros_like(out[..., :3])
    rgb[safe] = out[..., :3][safe] / a2[safe, None]
    return Image.fromarray(np.concatenate([np.clip(rgb, 0, 255), (a2 * 255)[:, :, None]], axis=-1).astype(np.uint8), "RGBA")


def paste(canvas: np.ndarray, src: np.ndarray, tx: int, ty: int) -> None:
    h2, w2 = src.shape[:2]
    xs0, ys0 = max(0, tx), max(0, ty)
    xs1 = min(canvas.shape[1], tx + w2)
    ys1 = min(canvas.shape[0], ty + h2)
    if xs1 > xs0 and ys1 > ys0:
        canvas[ys0:ys1, xs0:xs1] = src[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]


def main() -> None:
    raw = Image.open(SRC).convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT)
    body = trim(raw)
    print("内容 bbox:", body.size)

    # ---- poses/idle.png：640 画布，高 575，底 606，居中 ----
    scale = 575.0 / body.height
    new = premult_resize(body, (round(body.width * scale), 575))
    canvas = np.zeros((640, 640, 4))
    arr = np.asarray(new)
    paste(canvas, arr, (640 - arr.shape[1]) // 2, 606 - 575 + 1)
    (PET / "desktop" / "poses").mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas.astype(np.uint8), "RGBA").save(PET / "desktop" / "poses" / "idle.png")
    a = np.asarray(Image.open(PET / "desktop" / "poses" / "idle.png"))
    ys, xs = np.where(a[..., 3] > 50)
    print(f"idle.png: 底 {ys.max()} 高 {ys.max()-ys.min()+1} x[{xs.min()}-{xs.max()}]")

    # ---- avatar.png：整身裁（顶部 68% → 近方居中方裁 → 630²）----
    top68 = body.crop((0, 0, body.width, round(body.height * 0.68)))
    side = min(top68.width, top68.height)
    left = (top68.width - side) // 2
    top = (top68.height - side) // 2
    sq = top68.crop((left, top, left + side, top + side))
    avatar = premult_resize(sq, (630, 630))
    bg = Image.new("RGB", (630, 630), (255, 255, 255))
    bg.paste(avatar, (0, 0), avatar)
    bg.save(PET / "avatar.png", quality=95)
    print("avatar.png: 630² (白底整身)")

    # ---- Meowa 参照：1150²，体高 62%，底边距 90 ----
    s = (1150 - 90 - 60) / body.height  # 顶部留 60
    ref_body = premult_resize(body, (round(body.width * s), round(body.height * s)))
    rc = Image.new("RGBA", (1150, 1150), (0, 0, 0, 0))
    rc.paste(ref_body, ((1150 - ref_body.width) // 2, 1150 - 90 - ref_body.height), ref_body)
    MEOWA.mkdir(parents=True, exist_ok=True)
    rc.save(MEOWA / "ref_sq.png")
    b = np.asarray(rc)
    ys2, xs2 = np.where(b[..., 3] > 50)
    print(f"ref_sq.png: 高占比 {100*(ys2.max()-ys2.min()+1)/1150:.0f}% 底边距 {1150-1-ys2.max()} 左右[{xs2.min()},{xs2.max()}]")


if __name__ == "__main__":
    main()
