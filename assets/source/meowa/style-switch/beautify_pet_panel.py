# -*- coding: utf-8 -*-
"""宠物面板背景优化(2026-10-26 用户令「布局不错但整体差点意思」):
同构图换画法——现背景为唯一参照,严格保位重绘(横幅/虚线圆/粉垫/
左栏等所有元素位置尺寸不变), richer 水彩细节+柔和层次。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/pet_panel_bg'
CUR = 'assets/runtime/ui/pet_profile_new/new_background.png'

PROMPT = (
    "Repaint this exact pet profile panel background in a richer, softer "
    "watercolor storybook style. KEEP THE EXACT SAME COMPOSITION: every "
    "element stays in exactly the same position and same size - the "
    "decorative banner near the top, the dashed circles, the soft pink "
    "cushion area at the bottom, the left column zone, all borders and "
    "rounded frames. Only improve the painting: gentler watercolor "
    "gradients, more delicate paper texture, soft warm shadows, subtle "
    "cream-and-coral palette with a touch more color depth and cozy "
    "atmosphere. Keep all zones calm and readable for UI content on top. "
    "No text, no letters, no characters, no new objects.")

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
# 3:4(0.75)→目标 0.748(1085/1450):横向微裁
target_ratio = 1085 / 1450
crop_w = int(im.height * target_ratio)
x0 = (im.width - crop_w) // 2
im = im.crop((x0, 0, x0 + crop_w, im.height))
im = im.resize((1085, 1450), Image.LANCZOS)
im.convert('RGB').save(CUR)
print('IMPORT', im.size)
