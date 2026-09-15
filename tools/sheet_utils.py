# -*- coding: utf-8 -*-
"""素材表拆分共享工具（2026-09-09 精细抠图轮）。

核心：gutter 检测分割——先在非白投影上找整行/整列的纯白空隙，
把分割线放到空隙中心，再按格子内容 bbox 裁剪。等分网格对 AI 生成
图的栅格漂移没有免疫力（实测行边界可偏 37px：图标被切/混入邻居）。
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage


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


def soft_matte_from_white(cell: Image.Image, fill_thresh: int = 15,
                          band: int = 2, edge_t0: float = 10.0,
                          edge_t1: float = 60.0) -> Image.Image:
    """白底软抠图（2026-09-12 认真抠图轮）。

    两层：① 背景 = 与图角连通的近白（floodfill，thresh 15 防沿
    抗锯齿边渗进家具内部）——家具内部再浅的奶油色也不与边缘连通，
    不会被当背景误蚀；② 与背景接壤的 ``band`` 像素带内按「离白
    距离」给软 alpha，并按白底混合模型 C = a·F + (1-a)·白 反解
    F，消除硬阈值抠图的白毛边与锯齿。带外内容一律全不透明（奶油
    主体不会被洗淡），带外背景全透明。
    """
    from PIL import ImageDraw

    src = cell.convert("RGBA").copy()
    rgb = src.convert("RGB")
    width, height = rgb.size
    # ① 连通背景：四角灌洋红标记（奶油/木色系不含洋红，无碰撞）。
    for seed in ((0, 0), (width - 1, 0), (0, height - 1),
                 (width - 1, height - 1)):
        try:
            ImageDraw.floodfill(rgb, seed, (255, 0, 255),
                                thresh=fill_thresh)
        except Exception:
            pass
    arr = np.asarray(rgb).astype(np.int16)
    bg = (arr[..., 0] == 255) & (arr[..., 1] == 0) & (arr[..., 2] == 255)
    # ①b 白晕残留（2026-09-12 家具白月牙轮）：生成图在家具脚下常带
    # 一圈近纯白接触晕（实测均色 253,253,251、色度 2.5），既不与图角
    # 连通、也高于 fill_thresh——但定稿风格家具主体的色度 ≥25，低
    # 色度近白绝不可能是主体，直接并入背景。
    arr0 = np.asarray(src.convert("RGB")).astype(np.int16)
    # ①b2 接触阴影吸收（2026-09-13 用户定因轮：ChatGPT 生成图必然在
    # 物体底部画一层「比纯白略深」的软接触阴影——纯白抠图天然吃
    # 不掉）。从已确认背景出发沿渐变 BFS 吸收「亮度≥200 且色度≤25」
    # 的相邻像素，直到撞上彩色（色度>25）或深色（<200）屏障；被
    # 彩色轮廓包围的白色内衬（床垫绒面/画框衬纸）不与外部连通，
    # 自动保全。引擎已统一画接地软影，生成图自带阴影直接并入背景。
    # （旧 ①b「全局无条件清色度≤12 近白」已删——无连通判断会误杀
    # 家具内部纯白部分，月牙改由本条连通吸收兜底。）
    chroma0 = arr0.max(axis=2) - arr0.min(axis=2)
    absorbable = (arr0.min(axis=2) >= 200) & (chroma0 <= 25)
    frontier = bg & absorbable
    absorbed = bg.copy()
    while frontier.any():
        grown = absorbed.copy()
        grown[1:, :] |= absorbed[:-1, :]
        grown[:-1, :] |= absorbed[1:, :]
        grown[:, 1:] |= absorbed[:, :-1]
        grown[:, :-1] |= absorbed[:, 1:]
        frontier = grown & absorbable & ~absorbed
        absorbed |= frontier
    bg = absorbed
    # ①c 浅暖白残底（2026-09-12 深夜轮二：茶几腿间 3745px 撕边状白底
    # 色度 20 出头，逃过 ①b 的色度≤12；且与主体同处一行区间，行界
    # 判据无效）。判别式：**与彩色主体连通的浅白 = 家具白色部分
    # （保留）；不与彩色主体连通的孤立浅白块 = 背景残底（清除）**。
    light_warm = (
        (arr0.min(axis=2) >= 195)
        & (chroma0 <= 30)
        & ~bg
    )
    if light_warm.any():
        # 彩色种子：色度 > 45 的明确彩色主体像素
        colored = (chroma0 > 45) & ~bg
        # 把彩色区域膨胀 3px 作为「连通保护带」，浅白块与之相邻即保留
        protected = colored.copy()
        for _ in range(3):
            grown = protected.copy()
            grown[1:, :] |= protected[:-1, :]
            grown[:-1, :] |= protected[1:, :]
            grown[:, 1:] |= protected[:, :-1]
            grown[:, :-1] |= protected[:, 1:]
            protected = grown
        lab, cnt = ndimage.label(light_warm)
        for k in range(1, cnt + 1):
            block = lab == k
            if not (block & protected).any():
                bg |= block
    if bg.all():
        return Image.new("RGBA", cell.size, (0, 0, 0, 0))

    # ② 边缘带 = 背景的 band 圈膨胀再减去背景。
    dilated = bg.copy()
    for _ in range(band):
        grown = dilated.copy()
        grown[1:, :] |= dilated[:-1, :]
        grown[:-1, :] |= dilated[1:, :]
        grown[:, 1:] |= dilated[:, :-1]
        grown[:, :-1] |= dilated[:, 1:]
        dilated = grown
    edge_band = dilated & ~bg

    data = np.asarray(src).astype(np.float32)
    d_white = 255.0 - np.minimum(
        np.minimum(data[..., 0], data[..., 1]), data[..., 2])
    alpha = np.where(bg, 0.0, 1.0)
    ramp = np.clip((d_white - edge_t0) / (edge_t1 - edge_t0), 0.0, 1.0)
    alpha = np.where(edge_band, np.maximum(ramp, 0.05), alpha)
    alpha = np.where(data[..., 3] <= 12, 0.0, alpha)  # 尊重源透明

    a3 = alpha[..., None]
    foreground = (
        (data[..., :3] - (1.0 - a3) * 255.0) / np.maximum(a3, 1e-3)
    )
    foreground = np.clip(foreground, 0, 255)
    out = np.dstack([foreground, alpha * 255.0]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")
