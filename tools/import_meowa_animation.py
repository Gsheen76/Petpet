# -*- coding: utf-8 -*-
"""把 Meowa animate-run 的 4x4 精灵表导入为 Petpet 运行时动画帧。

管线（2026-10-06 happy 轮跑通，复用参数与坑位见各步注释）：
拆帧 -> 预乘 alpha LANCZOS 缩放（匹配 idle 主体尺寸）-> 几何对齐
（落地基线/中心/腾空离地偏移，顶部呼吸空间保护）-> 全局逐通道
均值+std 线性对色（gain 限幅 0.95-1.05）-> 落盘 000..015.png。

用法:
    python tools/import_meowa_animation.py --sheet <spritesheet.png> \
        --out assets/runtime/pets/<pet>/desktop/animations/<anim> \
        --idle assets/runtime/pets/<pet>/desktop/animations/idle
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

TOP_MARGIN_PX = 3  # 顶部呼吸空间下限，不足则整帧下移（内容永不裁）


def premult_scale(cell: Image.Image, scale: float) -> np.ndarray:
    """预乘 alpha 后缩放（Image.fromarray mode='F' 必须 float32，float64 会字节错位成灰色）。"""
    arr = np.asarray(cell).astype(np.float64)
    a = arr[..., 3] / 255.0
    pm = np.empty_like(arr)
    pm[..., :3] = arr[..., :3] * a[..., None]
    pm[..., 3] = arr[..., 3]
    new_w = round(cell.width * scale)
    new_h = round(cell.height * scale)
    chans = [
        np.asarray(
            Image.fromarray(pm[..., i].astype(np.float32), mode="F").resize(
                (new_w, new_h), Image.LANCZOS
            ),
            dtype=np.float64,
        )
        for i in range(4)
    ]
    out = np.stack(chans, axis=-1)
    a2 = np.clip(out[..., 3] / 255.0, 0, 1)
    safe = a2 > 0.003
    rgb = np.zeros_like(out[..., :3])
    rgb[safe] = out[..., :3][safe] / a2[safe, None]
    return np.concatenate([np.clip(rgb, 0, 255), (a2 * 255)[:, :, None]], axis=-1)


def frame_bbox(alpha: np.ndarray, threshold: int = 10):
    ys, xs = np.where(alpha > threshold)
    if len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def opaque_stats(frames) -> tuple[np.ndarray, np.ndarray]:
    px = np.concatenate(
        [f[..., :3][f[..., 3] > 200].astype(np.float64) for f in frames]
    )
    return px.mean(axis=0), px.std(axis=0)


def idle_metrics(idle_dir: Path):
    heights, baselines, centers = [], [], []
    for path in sorted(idle_dir.glob("*.png")):
        alpha = np.asarray(Image.open(path))[..., 3]
        box = frame_bbox(alpha)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        heights.append(y1 - y0 + 1)
        baselines.append(y1)
        centers.append((x0 + x1) / 2)
    return (
        float(np.median(heights)),
        float(np.median(baselines)),
        float(np.median(centers)),
        [np.asarray(Image.open(p)) for p in sorted(idle_dir.glob("*.png"))],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--idle", type=Path, required=True)
    args = parser.parse_args()

    sheet = Image.open(args.sheet)
    cols = rows = 4
    cell_w, cell_h = sheet.width // cols, sheet.height // rows
    total = cols * rows
    print(f"精灵表 {sheet.size} -> {cols}x{rows} 格 {cell_w}x{cell_h}")

    cells = [
        sheet.crop(
            (i % cols * cell_w, i // cols * cell_h,
             i % cols * cell_w + cell_w, i // cols * cell_h + cell_h)
        )
        for i in range(total)
    ]
    boxes = []
    for cell in cells:
        box = frame_bbox(np.asarray(cell)[..., 3])
        if box is None:
            raise SystemExit("存在空帧，中止")
        boxes.append(box)

    ground_y = max(b[3] for b in boxes)
    ground_heights = [
        b[3] - b[1] + 1 for b in boxes if b[3] >= ground_y - 4
    ]
    idle_height, target_base, target_cx, idle_frames = idle_metrics(args.idle)
    scale = idle_height / float(np.median(ground_heights))
    canvas_size = idle_frames[0].shape[0] if idle_frames else 640
    # 宽组合（如狗+食盆）按最大帧宽限幅缩放，防左右出界
    max_width = max(x1 - x0 + 1 for x0, _y0, x1, _y1 in boxes)
    scale = min(scale, (canvas_size - 2 * TOP_MARGIN_PX) / max_width)
    mean_cx = float(np.mean([(b[0] + b[2]) / 2 for b in boxes]))
    print(f"地面线={ground_y} 落地帧高median={int(np.median(ground_heights))} "
          f"idle高={int(idle_height)} 底线={int(target_base)} 中心x={target_cx:.0f} "
          f"SCALE={scale:.4f}")

    frames = []
    for cell, (x0, y0, x1, y1) in zip(cells, boxes):
        scaled = premult_scale(cell.crop((x0, y0, x1 + 1, y1 + 1)), scale)
        h2, w2 = scaled.shape[:2]
        frame_cx = (x0 + x1) / 2
        tx = round(target_cx + (frame_cx - mean_cx) - w2 / 2)
        tx = max(TOP_MARGIN_PX, min(tx, canvas_size - TOP_MARGIN_PX - w2))
        ty = round(target_base - (ground_y - y1) * scale - h2)
        if ty < TOP_MARGIN_PX:
            ty = TOP_MARGIN_PX
        canvas = np.zeros((canvas_size, canvas_size, 4))
        xs0, ys0 = max(0, tx), max(0, ty)
        xs1, ys1 = min(canvas_size, tx + w2), min(canvas_size, ty + h2)
        if xs1 > xs0 and ys1 > ys0:
            canvas[ys0:ys1, xs0:xs1] = scaled[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]
        frames.append(np.clip(canvas, 0, 255).astype(np.uint8))

    src_mean, src_std = opaque_stats(frames)
    idle_mean, idle_std = opaque_stats(idle_frames)
    gain = np.clip(idle_std / np.maximum(src_std, 1e-6), 0.95, 1.05)

    args.out.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        fixed = (frame[..., :3].astype(np.float64) - src_mean) * gain + idle_mean
        out = np.concatenate(
            [np.clip(fixed, 0, 255), frame[..., 3:4]], axis=-1
        ).astype(np.uint8)
        Image.fromarray(out, "RGBA").save(args.out / f"{index:03d}.png")

    check = [np.asarray(Image.open(args.out / f"{i:03d}.png")) for i in range(total)]
    after_mean, _ = opaque_stats(check)
    diff = np.abs(after_mean - idle_mean)
    print(f"对色残差 ΔR={diff[0]:.1f} ΔG={diff[1]:.1f} ΔB={diff[2]:.1f} /255")
    problems = []
    for index, frame in enumerate(check):
        box = frame_bbox(frame[..., 3], threshold=50)
        if box is None:
            problems.append(f"帧{index}: 空")
            continue
        x0, y0, x1, y1 = box
        if x0 < 2 or x1 > canvas_size - 3 or y0 < 2:
            problems.append(f"帧{index}: x[{x0},{x1}] y[{y0},{y1}] 边界不足")
    if problems:
        for line in problems:
            print("⚠", line)
        return 1
    baselines = sorted({frame_bbox(f[..., 3], 50)[3] for f in check})
    print(f"全部 {total} 帧边界安全，底线分布 {baselines}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
