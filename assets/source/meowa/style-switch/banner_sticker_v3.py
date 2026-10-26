# -*- coding: utf-8 -*-
"""横幅贴纸 v3:修 v2 竖块问题——16:9 宽幅生成,中带裁切,严格 2.1:1
横条比例,内容 bbox 实测验证后才导入。"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/banner_sticker/sticker_v3'
REF = 'assets/source/meowa/style-switch/banner_sticker/orig_banner_ref.png'
DST = 'assets/runtime/ui/pet_profile_new/banner_sticker.png'

PROMPT = (
    "A single WIDE HORIZONTAL ribbon banner sticker: the exact same coral-"
    "orange watercolor ribbon banner from the reference image - same "
    "design, same colors, same orientation - as a long horizontal strip "
    "roughly twice as wide as it is tall, stretching edge to edge across "
    "the wide frame. Layered sticker treatment: thick cream-white border "
    "ring, thin warm-brown outline, soft warm drop shadow underneath. "
    "Inner face plain and empty. Plain transparent background, no text, "
    "no letters, no characters. IMPORTANT: it must be one single wide "
    "horizontal banner strip, NOT a square, NOT vertical.")

r = subprocess.run([sys.executable, API, 'image-2.5-run',
    '--output-dir', OUT, '--quality', 'detailed', '--resolution', '1K',
    '--aspect-ratio', '16:9', '--remove-bg-method', 'standard',
    '--reference-image', REF, '--prompt', PROMPT],
    capture_output=True, text=True, timeout=300)
ok = '"status": "success"' in r.stdout
print('gen:', 'OK' if ok else 'FAIL')
if not ok:
    print(r.stdout[-300:]); sys.exit(1)
src = glob.glob(os.path.join(OUT, '*', 'result_images_0_url.png'))[0]
im = Image.open(src).convert('RGBA')
a = np.array(im)
ys, xs = np.where(a[:, :, 3] > 40)
im = im.crop((max(0, xs.min()-6), max(0, ys.min()-6),
              min(im.width, xs.max()+7), min(im.height, ys.max()+7)))
ratio = im.width / im.height
print(f'内容 bbox {im.size} 比例 {ratio:.2f} (目标 2.1)')
# 比例不对则中带裁/补到 2.1
target = 2.1
if ratio < target:  # 太方→裁高(保中带)
    nh = int(im.width / target)
    y0 = (im.height - nh) // 2
    im = im.crop((0, y0, im.width, y0 + nh))
elif ratio > target:  # 太扁→裁宽
    nw = int(im.height * target)
    x0 = (im.width - nw) // 2
    im = im.crop((x0, 0, x0 + nw, im.height))
print(f'裁后 {im.size} 比例 {im.width/im.height:.2f}')
im = im.resize((330, 157), Image.LANCZOS)
im.save(DST)
a2 = np.array(im)
ys2, xs2 = np.where(a2[:, :, 3] > 40)
print(f'导入 {im.size} 内容比 {(xs2.max()-xs2.min())/(ys2.max()-ys2.min()):.2f} 不透明 {round((a2[:,:,3]>200).mean()*100,1)}%')
