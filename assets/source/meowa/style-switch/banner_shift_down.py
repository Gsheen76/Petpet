# -*- coding: utf-8 -*-
"""背景重生成(2026-10-28 用户令:左上角标签往下移动一些)。
现背景为参照,同构图——仅标签/横幅块下移,其余元素(虚线圆/粉垫/边框)原位。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/banner_shift'
CUR = 'assets/runtime/ui/pet_profile_new/new_background.png'

PROMPT = (
    "Repaint this pet profile panel background keeping the exact same "
    "composition, colors and watercolor style, with ONE change: the "
    "coral-orange banner/tag block at the TOP-LEFT corner moves DOWN "
    "noticeably - shift it down so there is clear empty cream space "
    "above it (it no longer touches the top edge of the canvas), "
    "placing it lower into the page like a label pasted partway down "
    "the upper-left area. Keep the banner's same design and angle. All "
    "other elements - dashed circles, pink cushion, borders, rounded "
    "frames, all zones - stay exactly in their original positions. No "
    "text, no letters, no characters.")

r = subprocess.run([sys.executable, API, 'image-2.5-run',
    '--output-dir', OUT, '--quality', 'detailed', '--resolution', '1K',
    '--aspect-ratio', '3:4', '--remove-bg-method', 'none',
    '--reference-image', CUR, '--prompt', PROMPT],
    capture_output=True, text=True, timeout=300)
ok = '"status": "success"' in r.stdout
print('gen:', 'OK' if ok else 'FAIL')
if not ok:
    print(r.stdout[-300:]); sys.exit(1)
src = glob.glob(os.path.join(OUT, '*', 'result_images_0_url.png'))[0]
im = Image.open(src).convert('RGBA')
target_ratio = 1085 / 1450
crop_w = int(im.height * target_ratio)
x0 = (im.width - crop_w) // 2
im = im.crop((x0, 0, x0 + crop_w, im.height))
im = im.resize((1085, 1450), Image.LANCZOS)
bg = Image.new('RGBA', im.size, (255, 249, 238, 255))
bg.alpha_composite(im)
bg.convert('RGB').save(CUR)
print('IMPORT', bg.size)
