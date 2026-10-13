# -*- coding: utf-8 -*-
"""同尺实测：旧 idle（git）vs 新 idle vs 全部动作动画——找共用垂直线。

指标两个：躯干核心质心（bbox x38-78%/y42-88% 窗，跨姿态可比）+ 整体实心质心。
结论要能回答：新 idle 应右移多少才能落回其他动画的共用线。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

BASE = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry")
ANIMS = ["idle", "pet", "eat", "play", "dig", "happy", "sleep",
         "drag", "drag_sway", "drag_hover", "drag_land"]


def bbox_of(a):
    m = a[..., 3] > 50
    ys, xs = np.where(m)
    return xs.min(), xs.max(), ys.min(), ys.max()


def metrics(a):
    m = a[..., 3] > 50
    x0, x1, y0, y1 = bbox_of(a)
    win = np.zeros_like(m)
    win[int(y0 + (y1 - y0) * 0.42): int(y0 + (y1 - y0) * 0.88),
        int(x0 + (x1 - x0) * 0.38): int(x0 + (x1 - x0) * 0.78)] = True
    win &= m
    wy, wx = np.where(win)
    ys, xs = np.where(m)
    return float(wx.mean()), float(xs.mean()), int(x1), int(ys.max())


def load_all(folder: Path):
    return [np.asarray(Image.open(p)) for p in sorted(folder.glob("*.png"))]


def extract_old_idle(dest: Path):
    prefix = "assets/runtime/pets/lunch_meat/desktop/animations/outfits/strawberry/idle"
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", "01bb21c~1", f"{prefix}/"],
        capture_output=True, text=True, cwd=r"D:\Agent_project\Petpet").stdout
    names = [ln.strip() for ln in listing.splitlines() if ln.strip().endswith(".png")]
    dest.mkdir(parents=True, exist_ok=True)
    for rel in names:
        out = subprocess.run(["git", "show", f"01bb21c~1:{rel}"],
                             capture_output=True, cwd=r"D:\Agent_project\Petpet")
        (dest / Path(rel).name).write_bytes(out.stdout)
    return len(names)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        old_dir = Path(td) / "old_idle"
        n = extract_old_idle(old_dir)
        print(f"旧 idle 提取 {n} 帧\n")
        print(f"{'来源':<14}{'核心质心':>9}{'整体质心':>9}{'右缘中位':>9}{'底线中位':>9}{'帧数':>5}")
        rows = {}
        old_frames = load_all(old_dir)
        mm = [metrics(a) for a in old_frames]
        rows["旧idle(git)"] = mm
        print(f"{'旧idle(git)':<14}{np.median([x[0] for x in mm]):>9.1f}"
              f"{np.median([x[1] for x in mm]):>9.1f}"
              f"{np.median([x[2] for x in mm]):>9.0f}"
              f"{np.median([x[3] for x in mm]):>9.0f}{len(mm):>5}")
        for anim in ANIMS:
            folder = BASE / anim
            if anim == "idle":
                label = "新idle(现行)"
            else:
                label = anim
            mm = [metrics(a) for a in load_all(folder)]
            rows[label] = mm
            print(f"{label:<14}{np.median([x[0] for x in mm]):>9.1f}"
                  f"{np.median([x[1] for x in mm]):>9.1f}"
                  f"{np.median([x[2] for x in mm]):>9.0f}"
                  f"{np.median([x[3] for x in mm]):>9.0f}{len(mm):>5}")
        # 动作族（不含 idle）核心质心中位
        action_rows = [rows[a] for a in rows if "idle" not in a]
        action_core = float(np.median([x[0] for mm in action_rows for x in mm]))
        new_core = float(np.median([x[0] for x in rows["新idle(现行)"]]))
        print(f"\n动作族核心质心总中位 = {action_core:.1f}")
        print(f"新 idle 核心质心 = {new_core:.1f} → 应右移 {action_core - new_core:+.1f}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
