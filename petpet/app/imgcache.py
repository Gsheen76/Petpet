# -*- coding: utf-8 -*-
"""图片加载缓存与后台预解码（2026-09-28 商店加载轮）。

- ``pixmap(path, height=None)``：GUI 线程取图——优先命中 QPixmap 缓存；
  其次从后台预解码好的 QImage 转 QPixmap（廉价）；最后磁盘回退并
  入缓存。 ``(path, height)`` 双键（scaledToHeight 的结果直接缓存）。
- ``predecode_async(paths)``：后台线程 QImage 解码（QImage 是 Qt 唯一
  允许离开 GUI 线程的图像类型）——磁盘 IO+解码离开 UI 线程，GUI 线程
  只做 QImage→QPixmap 的轻转换。重复调用自动去重。
- 动机：``_shop_pixmap`` 每次页面重建都磁盘加载+平滑缩放（无缓存），
  商店各页首建 0.3-2.6s 的大头即此处；商店全部相关素材仅 ~8.6MB，
  一次预解码全热。
"""
import os
import threading

_PIXMAP_CACHE = {}      # (path, height|None) -> QPixmap
_IMAGE_CACHE = {}       # path -> QImage（后台预解码产物）
_PENDING = set()
_LOCK = threading.Lock()
_WORKERS = []           # 持线程引用防 GC


def pixmap(path, height=None):
    """GUI 线程取 QPixmap（缓存优先；height 为 None 原尺寸）。"""
    key = (str(path), None if height is None else int(height))
    cached = _PIXMAP_CACHE.get(key)
    if cached is not None:
        return cached
    result = _load_qpixmap(path, height)
    if not result.isNull():
        _PIXMAP_CACHE[key] = result
    return result


def _load_qpixmap(path, height):
    from PyQt5.QtGui import QImage, QPixmap

    img = _IMAGE_CACHE.get(str(path))
    if img is None:
        pm = QPixmap(str(path))
        if height is not None and not pm.isNull():
            pm = pm.scaledToHeight(int(height))
        return pm
    pm = QPixmap.fromImage(img)
    if height is not None and not pm.isNull():
        pm = pm.scaledToHeight(int(height))
    return pm


def predecode_async(paths):
    """后台线程批量 QImage 解码（自动去重；非 GUI 线程安全）。"""
    todo = []
    with _LOCK:
        for p in paths:
            p = str(p)
            if p and p not in _IMAGE_CACHE and p not in _PENDING:
                _PENDING.add(p)
                todo.append(p)
    if not todo:
        return

    def _worker():
        from PyQt5.QtGui import QImage
        try:
            for p in todo:
                if not os.path.exists(p):
                    continue
                img = QImage(p)
                if not img.isNull():
                    with _LOCK:
                        _IMAGE_CACHE[p] = img
                        _PENDING.discard(p)
        finally:
            with _LOCK:
                for p in todo:
                    _PENDING.discard(p)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    _WORKERS.append(t)
    del _WORKERS[:-4]  # 只留引用防 GC，不累积


def shop_asset_paths():
    """商店窗口全部相关素材路径（预解码清单）。"""
    import glob
    from petpet.app.paths import (
        DECORATIONS_DIR, PETS_MANIFEST_PATH, POSES_DIR, SHOP_UI_DIR,
    )

    paths = list(glob.glob(os.path.join(SHOP_UI_DIR, "*.png")))
    paths += list(glob.glob(
        os.path.join(DECORATIONS_DIR, "**", "*.png"), recursive=True))
    # 套装预览 + 套装待机动画帧（商店套装卡的两类图——首建冷读的
    # 大头曾漏在清单外）；帧图小（190×160 级），量可控。
    pets_root = os.path.dirname(os.path.dirname(SHOP_UI_DIR))  # assets/runtime
    pets_root = os.path.join(pets_root, "pets")
    paths += list(glob.glob(os.path.join(
        pets_root, "*", "desktop", "outfits", "**", "*.png"),
        recursive=True))
    paths += list(glob.glob(os.path.join(
        pets_root, "*", "desktop", "animations", "outfits", "*",
        "idle", "*.png")))
    try:
        import json
        with open(PETS_MANIFEST_PATH, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        root = os.path.dirname(PETS_MANIFEST_PATH)
        for definition in manifest.values():
            for key in ("preview", "avatar"):
                rel = definition.get(key)
                if rel:
                    candidate = os.path.normpath(os.path.join(root, rel))
                    if os.path.exists(candidate):
                        paths.append(candidate)
            for rel in (definition.get("desktop", {}) or {}).values():
                if isinstance(rel, str):
                    candidate = os.path.normpath(os.path.join(root, rel))
                    if os.path.exists(candidate):
                        paths.append(candidate)
    except Exception:
        pass
    paths.append(os.path.join(POSES_DIR, "idle.png"))
    return paths
