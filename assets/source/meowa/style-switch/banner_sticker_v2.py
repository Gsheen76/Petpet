# -*- coding: utf-8 -*-
"""横幅贴纸 v2(2026-10-26 用户令:与原背景横幅一模一样的款式+角度,
仅加叠层贴纸边;文字由 App 幼圆渲染,不 AI 生成)。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/banner_sticker/sticker_v2'
REF = 'assets/source/meowa/style-switch/banner_sticker/orig_banner_ref.png'
DST = 'assets/runtime/ui/pet_profile_new/banner_sticker.png'

PROMPT = (
    "Extract the coral-orange banner from the reference image as a "
    "standalone sticker, keeping its EXACT same design, colors, watercolor "
    "texture and same angle/orientation as in the reference - same ribbon "
    "banner shape, same soft coral watercolor washes. Only add the layered "
    "sticker treatment: a thick cream-white border ring around the banner, "
    "a thin warm-brown outline outside the ring, and a soft warm drop "
    "shadow underneath. The inner face of the banner stays plain and "
    "empty (text will be added by the app). Plain transparent background, "
    "no text, no letters, no characters.")

r = subprocess.run([sys.executable, API, 'image-2.5-run',
    '--output-dir', OUT, '--quality', 'detailed', '--resolution', '1K',
    '--aspect-ratio', '3:4', '--remove-bg-method', 'standard',
    '--reference-image', REF, '--prompt', PROMPT],
    capture_output=True, text=True, timeout=300)
ok = '"status": "success"' in r.stdout
print('gen:', 'OK' if ok else 'FAIL')
if not ok:
    print(r.stdout[-300:]); sys.exit(1)
src = glob.glob(os.path.join(OUT, '*', 'result_images_0_url.png'))[0]
im = Image.open(src).convert('RGBA')
# 3:4 太方:取上带裁成横幅比例(与原横幅 420x200≈2.1:1)
band = im.crop((0, 0, im.width, int(im.height * 0.48)))
import numpy as np
a = np.array(band)
ys, xs = np.where(a[:, :, 3] > 40)
if len(ys):
    band = band.crop((max(0, xs.min()-6), max(0, ys.min()-6),
                      min(band.width, xs.max()+7), min(band.height, ys.max()+7)))
target_ratio = 420 / 200
if band.width / band.height > target_ratio:
    nw = int(band.height * target_ratio)
    x0 = (band.width - nw) // 2
    band = band.crop((x0, 0, x0 + nw, band.height))
else:
    nh = int(band.width / target_ratio)
    y0 = (band.height - nh) // 2
    band = band.crop((0, y0, band.width, y0 + nh))
band = band.resize((330, 157), Image.LANCZOS)
band.save(DST)
print('IMPORT', band.size)
