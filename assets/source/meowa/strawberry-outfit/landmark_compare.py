# -*- coding: utf-8 -*-
"""Phase 1 取证：解剖学锚点逐像素比对（禁止代理指标）。

锚点定义：
- nose_x  头带（实心 bbox 上 45%）内最靠右的深色像素（鼻头是头部最前深色特征）
- eye_band_cx  头带深色像素质心（眼+鼻簇）
- paw_cx  底部 8% 实心行质心（前爪）
- hat_tip_x  最顶实心像素 x（帽尖）
- body_cx  剔尾身体质心（右侧 65% 实心——尾巴在左）
对照：旧 idle（git 真身）vs 新 idle（现行）vs 动作族。
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(r"D:\Agent_project\Petpet")
BASE = REPO / "assets/runtime/pets/lunch_meat/desktop/animations/outfits/strawberry"
ANIMS = ["pet", "eat", "play", "dig", "happy", "sleep",
         "drag", "drag_sway", "drag_hover", "drag_land"]


def load_all(folder: Path):
    return [np.asarray(Image.open(p)) for p in sorted(folder.glob("*.png"))]


def extract_old_idle(dest: Path) -> int:
    prefix = "assets/runtime/pets/lunch_meat/desktop/animations/outfits/strawberry/idle"
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", "01bb21c~1", f"{prefix}/"],
        capture_output=True, text=True, cwd=REPO).stdout
    names = [ln.strip() for ln in listing.splitlines() if ln.strip().endswith(".png")]
    dest.mkdir(parents=True, exist_ok=True)
    for rel in names:
        out = subprocess.run(["git", "show", f"01bb21c~1:{rel}"],
                             capture_output=True, cwd=REPO)
        (dest / Path(rel).name).write_bytes(out.stdout)
    return len(names)


def landmarks(a: np.ndarray) -> dict | None:
    m = a[..., 3] > 50
    ys, xs = np.where(m)
    if len(ys) == 0:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h = y1 - y0
    rgb = a[..., :3].astype(float)
    lum = rgb.mean(axis=-1)
    solid = m & (lum < 95)  # 深色像素（鼻头/眼）
    head = np.zeros_like(m)
    head[y0: y0 + int(h * 0.45), :] = True
    head_dark = solid & head
    if head_dark.any():
        hy, hx = np.where(head_dark)
        # nose = 头带内最右深色像素带的质心（右缘 6px 带，防单噪点）
        edge = hx >= hx.max() - 6
        nose = float(hx[edge].mean())
        eye_cx = float(hx.mean())
    else:
        nose = eye_cx = float("nan")
    foot = np.zeros_like(m)
    foot[y1 - max(2, int(h * 0.08)):, :] = True
    foot &= m
    fy, fx = np.where(foot)
    paw = float(fx.mean()) if len(fx) else float("nan")
    ty, tx = np.where(m)
    hat = float(tx[ty == ty.min()].mean())
    body = np.zeros_like(m)
    body[:, int(x0 + (x1 - x0) * 0.35):] = True
    body &= m
    by, bx = np.where(body)
    body_cx = float(bx.mean())
    return dict(nose=nose, eye=eye_cx, paw=paw, hat=hat, body=body_cx,
                right=int(x1), left=int(x0), bottom=int(y1), top=int(y0))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        old_dir = Path(td) / "old"
        n_old = extract_old_idle(old_dir)
        groups = [("旧idle(git)", load_all(old_dir)),
                  ("新idle(现行)", load_all(BASE / "idle"))]
        for anim in ANIMS:
            groups.append((anim, load_all(BASE / anim)))
        keys = ["nose", "eye", "paw", "hat", "body", "right", "left"]
        print(f"{'来源':<12}" + "".join(f"{k:>8}" for k in keys))
        table = {}
        for name, frames in groups:
            lms = [l for l in (landmarks(f) for f in frames) if l]
            med = {k: float(np.median([l[k] for l in lms])) for k in keys}
            table[name] = med
            print(f"{name:<12}" + "".join(f"{med[k]:>8.1f}" for k in keys))
        # 动作族中位（不含 sleep——睡姿解剖完全不同；含 pet/eat/play/dig/happy/drag 族）
        act_names = [n for n in table if n not in ("旧idle(git)", "新idle(现行)", "sleep")]
        fam = {k: float(np.median([table[n][k] for n in act_names])) for k in keys}
        print(f"{'动作族中位':<12}" + "".join(f"{fam[k]:>8.1f}" for k in keys))
        print()
        for k in keys:
            print(f"{k:>6}: 旧idle-vs族 {table['旧idle(git)'][k] - fam[k]:+7.1f} | "
                  f"新idle-vs族 {table['新idle(现行)'][k] - fam[k]:+7.1f} | "
                  f"新-vs旧 {table['新idle(现行)'][k] - table['旧idle(git)'][k]:+7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
