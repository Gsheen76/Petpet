# -*- coding: utf-8 -*-
"""把 Meowa animate-run 的 4x4 精灵表导入为 Petpet 运行时动画帧。

管线（2026-10-06 happy 轮跑通；细节轮升级：实心锚点+比例参数）：
拆帧 -> 预乘 alpha LANCZOS 缩放 -> 几何对齐 -> 对色 -> 落盘 000..015.png。

对齐锚点用**实心像素**（alpha>50）测量（基线/尺寸/中心精确锁定、
跨动画零错动），裁剪框用软边缘（alpha>10）保留毛发边缘不裁丢。

尺寸协调：--height-ratio 按 idle 主体高的比例定目标高。参照午餐肉
原作比例：pet(坐)≈0.742、eat≈0.811、play(邀玩)≈0.686、跳跳类 1.0。

用法:
    python tools/import_meowa_animation.py --sheet <spritesheet.png> \
        --out assets/runtime/pets/<pet>/desktop/animations/<anim> \
        --idle assets/runtime/pets/<pet>/desktop/animations/idle \
        [--height-ratio 0.742]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

SOFT_ALPHA = 10   # 裁剪框：保留软毛发边缘
SOLID_ALPHA = 50  # 定位锚：实心主体，基线/尺寸跨动画一致的基准
MARGIN_PX = 3     # 四边呼吸空间下限，不足整帧平移（内容永不裁）


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


def frame_bbox(alpha: np.ndarray, threshold: int = SOFT_ALPHA):
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
        box = frame_bbox(alpha, SOLID_ALPHA)
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


def _paste(canvas: np.ndarray, src: np.ndarray, tx: int, ty: int) -> None:
    """把 src 钳制边界后贴进 canvas（越界部分丢弃）。"""
    h2, w2 = src.shape[:2]
    size = canvas.shape[0]
    xs0, ys0 = max(0, tx), max(0, ty)
    xs1, ys1 = min(size, tx + w2), min(size, ty + h2)
    if xs1 > xs0 and ys1 > ys0:
        canvas[ys0:ys1, xs0:xs1] = src[ys0 - ty:ys1 - ty, xs0 - tx:xs1 - tx]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--idle", type=Path, required=True)
    parser.add_argument("--height-ratio", type=float, default=1.0,
                        help="目标主体高 = idle 主体高 × ratio（坐姿 0.742 等）")
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
    soft_boxes, solid_boxes = [], []
    for cell in cells:
        alpha = np.asarray(cell)[..., 3]
        soft = frame_bbox(alpha, SOFT_ALPHA)
        solid = frame_bbox(alpha, SOLID_ALPHA)
        if soft is None or solid is None:
            raise SystemExit("存在空帧，中止")
        soft_boxes.append(soft)
        solid_boxes.append(solid)

    ground_y = max(b[3] for b in solid_boxes)
    ground_heights = [
        b[3] - b[1] + 1 for b in solid_boxes if b[3] >= ground_y - 4
    ]
    idle_height, target_base, target_cx, idle_frames = idle_metrics(args.idle)
    target_height = idle_height * args.height_ratio
    scale = target_height / float(np.median(ground_heights))
    canvas_size = idle_frames[0].shape[0] if idle_frames else 640
    # 宽组合（如狗+食盆）按最大实心帧宽限幅缩放，防左右出界
    max_width = max(b[2] - b[0] + 1 for b in solid_boxes)
    scale = min(scale, (canvas_size - 2 * MARGIN_PX) / max_width)
    mean_cx = float(np.mean([(b[0] + b[2]) / 2 for b in solid_boxes]))
    print(f"地面线={ground_y} 落地实心高median={int(np.median(ground_heights))} "
          f"idle高={int(idle_height)} ratio={args.height_ratio} 目标高={target_height:.0f} "
          f"底线={int(target_base)} 中心x={target_cx:.0f} SCALE={scale:.4f}")

    frames = []
    for cell, soft, solid in zip(cells, soft_boxes, solid_boxes):
        sx0, sy0, _sx1, _sy1 = soft
        kx0, ky0, kx1, ky1 = solid
        scaled = premult_scale(cell.crop((sx0, sy0, _sx1 + 1, _sy1 + 1)), scale)
        # 缩放后实心锚在裁剪图内的位置与尺寸
        solid_left = (kx0 - sx0) * scale
        solid_top = (ky0 - sy0) * scale
        solid_w = (kx1 - kx0 + 1) * scale
        frame_cx = (kx0 + kx1) / 2
        # 目标实心底边：自身底部在地面线上方 (ground_y-ky1)px → 目标也在
        # 基线上方同缩放距离（符号是减——写反空中帧会沉到地面以下）
        desired_bottom = round(target_base - (ground_y - ky1) * scale)
        solid_h = (ky1 - ky0 + 1) * scale
        tx = round(target_cx + (frame_cx - mean_cx) - solid_w / 2 - solid_left)
        ty = round(desired_bottom - solid_h - solid_top)
        h2, w2 = scaled.shape[:2]
        tx = max(MARGIN_PX, min(tx, canvas_size - MARGIN_PX - w2))
        ty = max(MARGIN_PX, ty)
        canvas = np.zeros((canvas_size, canvas_size, 4))
        _paste(canvas, scaled, tx, ty)
        # 落盘级精确校正：实测实心底边，差多少平移多少（消灭四舍五入残差）
        box = frame_bbox(canvas[..., 3], SOLID_ALPHA)
        if box is not None:
            dy = desired_bottom - box[3]
            if dy:
                shifted = np.zeros_like(canvas)
                _paste(shifted, canvas, 0, dy)
                canvas = shifted
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
    ground_after = []
    for index, frame in enumerate(check):
        box = frame_bbox(frame[..., 3], SOLID_ALPHA)
        if box is None:
            problems.append(f"帧{index}: 空")
            continue
        x0, y0, x1, y1 = box
        if x0 < 2 or x1 > canvas_size - 3 or y0 < 2:
            problems.append(f"帧{index}: x[{x0},{x1}] y[{y0},{y1}] 边界不足")
        if y1 >= target_base - 2:
            ground_after.append(y1)
    if problems:
        for line in problems:
            print("⚠", line)
        return 1
    print(f"全部 {total} 帧边界安全；落地帧实心底线 {sorted(set(ground_after))}（目标 {int(target_base)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
