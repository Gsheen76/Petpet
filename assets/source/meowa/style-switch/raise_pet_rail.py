# -*- coding: utf-8 -*-
"""宠物面板左栏板立体化(2026-10-26 用户令:左上角那块立体凸出来)。
现板为参照,同形重绘为浮起水彩卡片:顶/左受光提亮,底/右压暗+柔投影。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/pet_rail_raised'
CUR = 'assets/runtime/ui/pet_profile_new/pet_avatar_rail.png'

PROMPT = (
    "Repaint this vertical pet panel board as a RAISED three-dimensional "
    "watercolor card that floats above the background: keep the same "
    "vertical rounded-board shape and size, but paint it with clear "
    "thickness - a soft bright highlight along the top and left edges as "
    "if lit from above-left, gently darkened bottom and right edges "
    "showing the board's side thickness, and a soft warm drop shadow "
    "spilling onto the lower-right outside the board. The board face "
    "stays soft plain cream watercolor paper, calm and empty (no slots, "
    "no objects, no text) - avatar icons will be placed on it later by "
    "the app. Cozy watercolor storybook style, transparent background "
    "outside the board and its shadow.")

r = subprocess.run([sys.executable, API, 'image-2.5-run',
    '--output-dir', OUT, '--quality', 'detailed', '--resolution', '1K',
    '--aspect-ratio', '9:16', '--remove-bg-method', 'standard',
    '--reference-image', CUR, '--prompt', PROMPT],
    capture_output=True, text=True, timeout=300)
ok = '"status": "success"' in r.stdout
print('gen:', 'OK' if ok else 'FAIL')
if not ok:
    print(r.stdout[-300:]); sys.exit(1)
src = glob.glob(os.path.join(OUT, '*', 'result_images_0_url.png'))[0]
im = Image.open(src).convert('RGBA')
# 9:16(0.5625)→目标 250/1326(0.1885):竖向比例远比目标更方,横向裁切
target_ratio = 250 / 1326
crop_w = int(im.height * target_ratio)
if crop_w <= im.width:
    x0 = (im.width - crop_w) // 2
    im = im.crop((x0, 0, x0 + crop_w, im.height))
else:
    crop_h = int(im.width / target_ratio)
    y0 = (im.height - crop_h) // 2
    im = im.crop((0, y0, im.width, y0 + crop_h))
im = im.resize((250, 1326), Image.LANCZOS)
im.save(CUR)
print('IMPORT', im.size)
