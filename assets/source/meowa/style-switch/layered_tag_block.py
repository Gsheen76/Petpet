# -*- coding: utf-8 -*-
"""背景左上角标签块叠层化(2026-10-26 用户参考图定稿:叠层凸出=厚奶白
描边环+细暖棕轮廓+柔暖投影+骑跨边界,非 3D 厚度)。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/pet_panel_layered'
CUR = 'assets/runtime/ui/pet_profile_new/new_background.png'
USER_REF = r'C:\Users\sheen\Downloads\柴犬治愈系叠层界面示意 亚洲AV.png'

PROMPT = (
    "Repaint this pet profile panel background keeping the exact same "
    "composition and all elements in the same positions, with ONE change: "
    "the decorative tag/banner block in the TOP-LEFT corner must look "
    "like a floating layered sticker badge, exactly like the badge style "
    "in the second reference image - the block gets a thick cream-white "
    "border ring around it, a thin warm-brown outline outside that ring, "
    "and a soft warm low-opacity drop shadow underneath, and it rides "
    "slightly over the surrounding background edge as if pasted on top. "
    "Everything else (dashed circles, pink cushion, borders, zones) stays "
    "identical in place. Soft watercolor storybook style, cozy cream and "
    "coral palette, no text, no letters, no characters.")

r = subprocess.run([sys.executable, API, 'image-2.5-run',
    '--output-dir', OUT, '--quality', 'detailed', '--resolution', '1K',
    '--aspect-ratio', '3:4', '--remove-bg-method', 'none',
    '--reference-image', CUR, '--reference-image', USER_REF,
    '--prompt', PROMPT],
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
im.convert('RGB').save(CUR)
print('IMPORT', im.size)
