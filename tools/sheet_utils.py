# -*- coding: utf-8 -*-
"""素材表拆分共享工具（2026-09-09 精细抠图轮）。

核心：gutter 检测分割——先在非白投影上找整行/整列的纯白空隙，
把分割线放到空隙中心，再按格子内容 bbox 裁剪。等分网格对 AI 生成
图的栅格漂移没有免疫力（实测行边界可偏 37px：图标被切/混入邻居）。
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def nonwhite_mask(rgba: Image.Image, threshold: int = 240) -> np.ndarray:
    data = np.asarray(rgba.convert("RGBA"))
    r, g, b, a = (data[..., i] for i in range(4))
    return (~((r >= threshold) & (g >= threshold) & (b >= threshold))
            & (a > 12))


def _gaps(proj: np.ndarray, min_gap: int = 6) -> list[tuple[int, int]]:
    """投影上整段为零的空隙区间（起止含端）。"""
    runs = []
    start = None
    for x in range(len(proj)):
        if proj[x] == 0:
            if start is None:
                start = x
        else:
            if start is not None:
                if x - start >= min_gap:
                    runs.append((start, x - 1))
                start = None
    if start is not None and len(proj) - start >= min_gap:
        runs.append((start, len(proj) - 1))
    return runs


def axis_bounds(mask: np.ndarray, parts: int, axis: int,
                min_gap: int = 6) -> list[tuple[int, int]]:
    """沿某轴把画布分成 parts 段：优先 gutter 中心分割；空隙数量
    不足（AI 图粘连/漂移极端）时回退等分。返回每段 [start, end)。"""
    total = mask.shape[axis]
    proj = mask.sum(axis=1 - axis)
    gaps = _gaps(proj, min_gap)
    # 去掉首尾贴边空隙，只取内部 gutter 作分割候选。
    inner = [g for g in gaps if g[0] > 2 and g[1] < total - 3]
    if len(inner) >= parts - 1:
        # 取空隙最宽的 parts-1 条，按位置排序后在其中线下刀。
        chosen = sorted(
            sorted(inner, key=lambda g: g[1] - g[0], reverse=True)[:parts - 1],
        )
        cuts = [(g[0] + g[1]) // 2 for g in chosen]
    else:
        cuts = [total * k // parts for k in range(1, parts)]
    bounds = []
    prev = 0
    for cut in cuts + [total]:
        bounds.append((prev, cut))
        prev = cut
    return bounds


def cell_to_icon(cell: Image.Image, threshold: int, size: int,
                 pad_ratio: float = 0.92) -> tuple[Image.Image, int]:
    """近白转透明 + 内容 bbox + 方形画布居中。返回 (图标, 不透明像素数)。"""
    data = np.asarray(cell.convert("RGBA")).astype(np.int16)
    r, g, b, a = (data[..., i] for i in range(4))
    near_white = (r >= threshold) & (g >= threshold) & (b >= threshold)
    alpha = np.where(near_white, 0, a).astype(np.uint8)
    cleaned = np.dstack([data[..., :3].astype(np.uint8), alpha])
    ys, xs = np.nonzero(alpha > 12)
    if len(xs) == 0:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0)), 0
    cropped = Image.fromarray(
        cleaned[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA",
    )
    limit = round(size * pad_ratio)
    if cropped.width > limit or cropped.height > limit:
        cropped = cropped.copy()
        cropped.thumbnail((limit, limit), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(cropped, ((size - cropped.width) // 2,
                           (size - cropped.height) // 2), cropped)
    opaque = int((np.asarray(canvas)[..., 3] > 12).sum())
    return canvas, opaque
