"""冰淇淋 eat v3 地毯手术:5 个坏帧(1/2/3/8/9)抹除粉红黄点圆形地毯。
分割:地毯色域(粉红高 R 低 G-B / 黄点高 R 高 G 低 B)且与边框连通;
狗体奶油色(R~G~B 平衡)与食盆豁免。逐帧修完重导入+复测。
"""
import os

import numpy as np
from PIL import Image

BASE = os.path.join("assets", "source", "meowa", "style-switch")
RUNTIME = os.path.join("assets", "runtime", "pets")
FRAMES = os.path.join(BASE, "ice_cream", "eat_v3", "frames")
BAD = [1, 2, 3, 8, 9]


def rug_mask(rgb):
    r, g, b = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
    # 粉红:R 明显高于 G/B
    pink = (r - g > 18) & (r - b > 10) & (r > 150)
    # 黄点:R/G 高 B 低
    yellow = (r > 150) & (g > 120) & (r - b > 60) & (g - b > 45)
    final = rug_full & (rug | near_white | True)
    final = rug_full  # 贴边地毯+3px 膨胀(吃软边,不深咬爪部接触)
    arr[:, :, 3] = np.where(final, 0, arr[:, :, 3])
    out = Image.fromarray(arr)
    out.save(path)
    dst = os.path.join(RUNTIME, "ice_cream", "desktop_new", "animations", "eat", f"{i:03d}.png")
    with open(path, "rb") as fh:
        data = fh.read()
    with open(dst, "wb") as fo:
        fo.write(data)
    a = np.array(out)[:, :, 3]
    ys, xs = np.where(a > 50)
    print(f"frame {i}: removed {int(final.sum())} px, new bbox "
          f"x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}", flush=True)

print("RUG SURGERY DONE")
