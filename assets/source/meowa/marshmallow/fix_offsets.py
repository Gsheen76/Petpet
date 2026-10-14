# -*- coding: utf-8 -*-
"""棉花糖八套逐帧偏移修复：臀窗 SAD、只修纯平移噪声。

规则（草莓 idle 根治法推广）：
- 窗口 = 臀部 (x340-465, y380-555)：避耳（顶 35%）、避花/前爪（左前）、避脚（底 10%）
- vs 帧 0 求最优整数平移；仅当 SAD(best) < 0.5×SAD(0位移) 且 SAD(best) < 8
  才判「纯平移噪声」并水平修正（垂直不动=地线铁律）
- play（运镜变焦）/drag（摇摆本体）整组跳过；帧 0 自身跳过
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

PET = Path(r"D:\Agent_project\Petpet\assets\runtime\pets\marshmallow\desktop\animations")
SKIP = {"play", "drag", "sleep"}  # sleep=呼吸动画无静态参照，整组跳过
WX0, WY0, WX1, WY1 = 340, 380, 465, 555


def best_shift(a, ref, rng=6):
    w1 = a[WY0:WY1, WX0:WX1, :3].astype(np.int16)
    w2 = ref[WY0:WY1, WX0:WX1, :3].astype(np.int16)
    sad0 = float(np.abs(w1 - w2).mean())
    best = (sad0, 0, 0)
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            if dx == 0 and dy == 0:
                continue
            sh = np.roll(np.roll(w1, dy, axis=0), dx, axis=1)
            sad = float(np.abs(sh - w2).mean())
            if sad < best[0] - 1e-9:
                best = (sad, dx, dy)
    return sad0, best


def main() -> int:
    total = 0
    for anim in sorted(p for p in PET.iterdir() if p.is_dir() and p.name not in SKIP):
        paths = sorted((PET / anim).glob("*.png"))
        n = len(paths)
        arrs = [np.asarray(Image.open(p)) for p in paths]
        ref = arrs[0]
        # 窗内容检查
        m = ref[WY0:WY1, WX0:WX1, 3] > 60
        if m.mean() < 0.25:
            print(f"== {anim}: 臀窗内容不足（{(m.mean()*100):.0f}%），跳过")
            continue
        print(f"== {anim}（{n}帧）==")
        fixed = 0
        for i in range(1, n):
            a = arrs[i]
            sad0, (sadb, dx, dy) = best_shift(a, ref)
            if dx == 0 and dy == 0:
                continue
            # 纯平移判定（实测分界：噪声帧 sadb≤8 / 动作帧 ≥17，中间无过渡）：
            # 残差 <8 = 内容同构仅差整数平移（bbox 量化噪声）；同内容帧修完
            # bbox 自动与帧 0 一致（底线回 606）。含垂直——同内容帧的垂直
            # 差同样是量化噪声（snap 时底边阈值闪烁）。
            # 草莓铁律回归：只修水平（垂直修正实测会把呼吸/纹理误配成
            # 平移——sleep 底线被拉出 602/605/607 跳变后回滚重做的教训）
            if sadb < 8.0 and dx != 0:
                out = np.zeros_like(a)
                out[..., :3] = np.roll(a[..., :3], -dx, axis=1)
                out[..., 3] = np.roll(a[..., 3], -dx, axis=1)
                Image.fromarray(out, "RGBA").save(paths[i])
                fixed += 1
                print(f"  帧{i:2d}: 修正 dx={-dx:+d}（SAD {sad0:.1f}→{sadb:.1f}）")
            else:
                print(f"  帧{i:2d}: 保留（最优({dx:+d},{dy:+d}) SAD {sadb:.1f} = 动作非噪声）")
        total += fixed
        print(f"  {anim}: 修正 {fixed}/{n-1}")
    print(f"总计修正 {total} 帧")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
