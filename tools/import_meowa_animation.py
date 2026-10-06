# -*- coding: utf-8 -*-
"""把 Meowa animate-run 的 4x4 精灵表导入为 Petpet 运行时动画帧。

管线（2026-10-06 happy 轮跑通；细节二轮升级：狗本体锚定）：
拆帧 -> 预乘 alpha LANCZOS 缩放 -> 几何对齐 -> 对色 -> 落盘 000..015.png。

**狗本体锚定**（2026-10-06 用户定稿：「是小狗的最低点在一条线上，
不是素材的边界」）：带道具的帧（如食盆）自动按颜色分离道具（盆=暖棕
B<75 大块），基线/尺寸/中心/对色统计全部只用**狗本体**像素；道具仍
完整渲染，允许垂在基线下方（近景透视，参照午餐肉原作盆低于爪 29px）。

尺寸协调：--height-ratio = 目标狗高 / idle 狗高。参照午餐肉原作实测：
pet(坐) 0.926（头宽比 0.815 换算）、eat 0.754、play 0.686、跳跳类 1.0。

用法:
    python tools/import_meowa_animation.py --sheet <spritesheet.png> \
        --out assets/runtime/pets/<pet>/desktop/animations/<anim> \
        --idle assets/runtime/pets/<pet>/desktop/animations/idle \
        [--height-ratio 0.754]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

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


def prop_mask(rgb: np.ndarray, solid: np.ndarray) -> np.ndarray | None:
    """分离垂在狗地面线**以下**的暖棕道具（食盆）。

    候选=主体下 35% 区域内 B<75 的最大连通块（实测：盆 RGB≈
    [148~179,77~113,39~69]）；**有效性校验**：块底必须比剔除后的
    狗本体底边低 ≥6px 才算道具——狗自身暗部阴影（腹部/后腿
    B≈40~64）不会垂到自己的爪子之下，借此排除误检。
    """
    ys, xs = np.where(solid)
    if len(ys) == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    zone = np.zeros(solid.shape, dtype=bool)
    zone[int(y0 + (y1 - y0) * 0.65):, :] = True
    brown = zone & solid & (rgb[..., 2] < 75)
    if int(brown.sum()) < 500:
        return None
    labels, count = ndimage.label(brown)
    sizes = ndimage.sum(brown, labels, range(1, count + 1))
    blob = labels == (int(np.argmax(sizes)) + 1)
    dilated = ndimage.binary_dilation(blob, iterations=3)
    dog = solid & ~dilated
    dog_rows = np.where(dog.any(axis=1))[0]
    if len(dog_rows) == 0:
        return None
    blob_bottom = int(np.max(np.where(blob.any(axis=1))[0]))
    if blob_bottom < int(dog_rows.max()) + 6:
        return None  # 不垂在狗地面之下：是狗自身暗部阴影，不是道具
    return dilated


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
    soft_boxes, solid_boxes, dog_boxes = [], [], []
    for cell in cells:
        arr = np.asarray(cell)
        alpha = arr[..., 3]
        soft = frame_bbox(alpha, SOFT_ALPHA)
        solid = frame_bbox(alpha, SOLID_ALPHA)
        if soft is None or solid is None:
            raise SystemExit("存在空帧，中止")
        soft_boxes.append(soft)
        solid_boxes.append(solid)
        # 狗本体 = 实心主体剔除道具（食盆等）后的部分
        solid_mask = alpha > SOLID_ALPHA
        props = prop_mask(arr[..., :3], solid_mask)
        dog_mask = solid_mask & ~props if props is not None else solid_mask
        dog = frame_bbox(dog_mask.astype(np.uint8) * 255, SOLID_ALPHA)
        if dog is None:
            raise SystemExit("狗本体分离后为空，中止")
        dog_boxes.append(dog)

    ground_y = max(b[3] for b in dog_boxes)
    ground_heights = [
        b[3] - b[1] + 1 for b in dog_boxes if b[3] >= ground_y - 4
    ]
    idle_height, target_base, target_cx, idle_frames = idle_metrics(args.idle)
    target_height = idle_height * args.height_ratio
    scale = target_height / float(np.median(ground_heights))
    canvas_size = idle_frames[0].shape[0] if idle_frames else 640
    # 宽度安全帽用**含道具**的整体实心宽（道具也要装进画布）
    max_width = max(b[2] - b[0] + 1 for b in solid_boxes)
    scale = min(scale, (canvas_size - 2 * MARGIN_PX) / max_width)
    mean_cx = float(np.mean([(b[0] + b[2]) / 2 for b in dog_boxes]))
    print(f"狗地面线={ground_y} 落地狗高median={int(np.median(ground_heights))} "
          f"idle高={int(idle_height)} ratio={args.height_ratio} 目标高={target_height:.0f} "
          f"底线={int(target_base)} 中心x={target_cx:.0f} SCALE={scale:.4f}")

    def dog_measure(canvas):
        """画布上重测狗本体：返回 (底边y, 实心bbox) 或 None。"""
        solid = canvas[..., 3] > SOLID_ALPHA
        props = prop_mask(canvas[..., :3], solid)
        dog = solid & ~props if props is not None else solid
        ys = np.where(dog.any(axis=1))[0]
        if len(ys) == 0:
            return None
        xs = np.where(dog.any(axis=0))[0]
        return int(ys.max()), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

    frames = []
    for cell, soft, dog in zip(cells, soft_boxes, dog_boxes):
        sx0, sy0, _sx1, _sy1 = soft
        kx0, ky0, kx1, ky1 = dog
        scaled = premult_scale(cell.crop((sx0, sy0, _sx1 + 1, _sy1 + 1)), scale)
        # 缩放后狗本体锚在裁剪图内的位置与尺寸
        solid_left = (kx0 - sx0) * scale
        solid_top = (ky0 - sy0) * scale
        solid_w = (kx1 - kx0 + 1) * scale
        solid_h = (ky1 - ky0 + 1) * scale
        frame_cx = (kx0 + kx1) / 2
        # 目标狗底边：自身底部在地面线上方 (ground_y-ky1)px → 目标也在
        # 基线上方同缩放距离（符号是减——写反空中帧会沉到地面以下）
        desired_bottom = round(target_base - (ground_y - ky1) * scale)
        tx = round(target_cx + (frame_cx - mean_cx) - solid_w / 2 - solid_left)
        ty = round(desired_bottom - solid_h - solid_top)
        h2, w2 = scaled.shape[:2]
        tx = max(MARGIN_PX, min(tx, canvas_size - MARGIN_PX - w2))
        ty = max(MARGIN_PX, ty)
        canvas = np.zeros((canvas_size, canvas_size, 4))
        _paste(canvas, scaled, tx, ty)
        # 落盘级精确校正：实测狗本体底边，差多少平移多少（消灭四舍五入残差）
        measured = dog_measure(canvas)
        if measured is not None:
            dy = desired_bottom - measured[0]
            if dy:
                shifted = np.zeros_like(canvas)
                _paste(shifted, canvas, 0, dy)
                canvas = shifted
        frames.append(np.clip(canvas, 0, 255).astype(np.uint8))

    # 对色统计只用狗本体像素（道具如食盆的棕色不参与，防污染）
    def dog_opaque_stats(frame_list):
        chunks = []
        for f in frame_list:
            solid = f[..., 3] > 200
            props = prop_mask(f[..., :3], solid)
            dog = solid & ~props if props is not None else solid
            chunks.append(f[..., :3][dog].astype(np.float64))
        px = np.concatenate(chunks)
        return px.mean(axis=0), px.std(axis=0)

    src_mean, src_std = dog_opaque_stats(frames)
    idle_mean, idle_std = dog_opaque_stats(idle_frames)
    gain = np.clip(idle_std / np.maximum(src_std, 1e-6), 0.95, 1.05)

    args.out.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        fixed = (frame[..., :3].astype(np.float64) - src_mean) * gain + idle_mean
        out = np.concatenate(
            [np.clip(fixed, 0, 255), frame[..., 3:4]], axis=-1
        ).astype(np.uint8)
        Image.fromarray(out, "RGBA").save(args.out / f"{index:03d}.png")

    check = [np.asarray(Image.open(args.out / f"{i:03d}.png")) for i in range(total)]
    after_mean, _ = dog_opaque_stats(check)
    diff = np.abs(after_mean - idle_mean)
    print(f"狗本体对色残差 ΔR={diff[0]:.1f} ΔG={diff[1]:.1f} ΔB={diff[2]:.1f} /255")
    problems = []
    dog_grounds = []
    for index, frame in enumerate(check):
        measured = dog_measure(frame)
        box = frame_bbox(frame[..., 3], SOLID_ALPHA)
        if measured is None or box is None:
            problems.append(f"帧{index}: 空")
            continue
        x0, y0, x1, _y1 = box
        if x0 < 2 or x1 > canvas_size - 3 or y0 < 2:
            problems.append(f"帧{index}: x[{x0},{x1}] y[{y0},..] 边界不足")
        if measured[0] >= target_base - 2:
            dog_grounds.append(measured[0])
    if problems:
        for line in problems:
            print("⚠", line)
        return 1
    print(f"全部 {total} 帧边界安全；落地帧狗本体底线 {sorted(set(dog_grounds))}（目标 {int(target_base)}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
