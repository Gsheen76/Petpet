# -*- coding: utf-8 -*-
"""eat 逐帧偏移测量+修复：臀部冻区 SAD 整数对齐（同 idle 追记 22 方法学）。

窗口 = 全帧实心交集的底部带（自动剔头部/前爪/尾巴活动区）。
对齐参照 = 帧 0（其绝对位已与 idle 共线：顶 32/底 606）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

EAT = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\lunch_meat\desktop\animations\outfits\strawberry\eat")
DRY_RUN = "--dry" in sys.argv


def solid(a):
    return a[..., 3] > 60


def main() -> int:
    paths = sorted(EAT.glob("*.png"))
    arrs = [np.asarray(Image.open(p)) for p in paths]
    n = len(arrs)

    # 物理接地锚修正：坐姿接触 patch（后爪底带质心 x200-290）相位内钉
    # 常量，过渡帧 3 取插值——喂食是重心后移的换姿动画，逐帧刚体对齐
    # 无意义；要 planted 的是接触点。垂直不动（底 606 全帧已恒定）。
    def anchor_of(a):
        m = solid(a)
        ys2, xs2 = np.where(m)
        y0b, y1b = ys2.min(), ys2.max()
        foot = np.zeros_like(m)
        foot[y1b - max(2, int((y1b - y0b) * 0.08)):, :290] = True
        foot &= m
        fy, fx = np.where(foot)
        return float(fx[(fx >= 200) & (fx < 290)].mean())

    anchors = [anchor_of(a) for a in arrs]
    seated_idx = [0, 1, 2, 18, 19, 20, 21]
    held_idx = list(range(4, 18))
    t_seated = float(np.median([anchors[i] for i in seated_idx]))
    t_held = float(np.median([anchors[i] for i in held_idx]))
    print(f"接地锚目标: 坐姿 {t_seated:.1f}  举莓 {t_held:.1f}（真实重心后移 {t_held-t_seated:+.1f} 保留）")
    shifts = {i: (0, 0) for i in range(n)}
    print("\n帧  锚实测  目标  平移")
    for i in range(n):
        if i == 3:
            target = (t_seated + t_held) / 2
        elif i in seated_idx:
            target = t_seated
        else:
            target = t_held
        dx = int(round(target - anchors[i]))
        if abs(target - anchors[i]) < 0.5:
            dx = 0
        shifts[i] = (dx, 0)
        print(f"{i:2d}  {anchors[i]:7.1f} {target:7.1f}  {shifts[i]}")

    moved = [(i, s) for i, s in sorted(shifts.items()) if s != (0, 0)]
    print(f"\n需平移 {len(moved)}/{n} 帧: {moved}")
    if DRY_RUN:
        return 0

    for i, (dx, dy) in moved:
        a = arrs[i]
        out = np.zeros_like(a)
        out[..., :3] = np.roll(np.roll(a[..., :3], dy, axis=0), dx, axis=1)
        out[..., 3] = np.roll(np.roll(a[..., 3], dy, axis=0), dx, axis=1)
        Image.fromarray(out, "RGBA").save(paths[i])
    print("已应用")

    # 复测：臀锚曲线（相位内极差）+ bbox
    arrs2 = [np.asarray(Image.open(p)) for p in paths]
    anchors, bots, tops = [], [], []
    for a in arrs2:
        m = solid(a)
        ys2, xs2 = np.where(m)
        y0b, y1b = ys2.min(), ys2.max()
        bots.append(int(y1b)); tops.append(int(y0b))
        foot = np.zeros_like(m)
        foot[y1b - max(2, int((y1b - y0b) * 0.08)):, :290] = True
        foot &= m
        fy, fx = np.where(foot)
        anchors.append(float(fx[(fx >= 200) & (fx < 290)].mean()))
    seated = [anchors[i] for i in (0, 1, 2, 18, 19, 20, 21)]
    held = [anchors[i] for i in range(4, 18)]
    print(f"复测 臀锚: 坐姿极差 {max(seated)-min(seated):.2f}  举莓极差 {max(held)-min(held):.2f}")
    print(f"复测 底 {sorted(set(bots))}  顶 {sorted(set(tops))}")
    ok = (max(seated) - min(seated)) <= 1.5 and (max(held) - min(held)) <= 2.0
    print("PASS" if ok else "STILL_JITTER")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
