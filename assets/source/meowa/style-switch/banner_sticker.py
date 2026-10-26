# -*- coding: utf-8 -*-
"""左上角横幅贴纸化(2026-10-26 用户令:横幅像贴纸覆盖在左上角,可超出
页面边界,页面跳出规整矩形;不动任何部件)。
A:背景重生成(横幅移除,顶部素净) B:横幅叠层贴纸(奶白环+棕线+柔投影)。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/banner_sticker'
BG = 'assets/runtime/ui/pet_profile_new/new_background.png'
REF = 'assets/source/meowa/style-switch/pet_panel_layered/bg_topleft_now.png'

BG_PROMPT = (
    "Repaint this pet profile panel background keeping the exact same "
    "composition, colors and all elements in place, with ONE change: "
    "REMOVE the coral-orange banner strip from the top-left corner "
    "completely - the top area becomes plain calm cream watercolor "
    "paper with nothing on it, flowing seamlessly into the rest. Keep "
    "dashed circles, pink cushion, borders and all other zones exactly "
    "as they are. No text, no characters.")

STICKER_PROMPT = (
    "A single horizontal coral-orange watercolor banner sticker, like a "
    "label pasted on a scrapbook page: a rounded-corner elongated coral "
    "watercolor strip matching the banner style in the reference image, "
    "with a thick cream-white border ring around it, a thin warm-brown "
    "outline outside the ring, and a soft warm low-opacity drop shadow "
    "underneath - clearly a floating sticker badge. Plain transparent "
    "background around it, no text, no letters, no characters.")

for key, prompt, aspect, refs in (
    ('bg_nobanner', BG_PROMPT, '3:4', [BG]),
    ('banner_sticker', STICKER_PROMPT, '16:9', [REF]),
):
    out = os.path.join(OUT, key)
    cmd = [sys.executable, API, 'image-2.5-run',
           '--output-dir', out, '--quality', 'detailed',
           '--resolution', '1K', '--aspect-ratio', aspect,
           '--remove-bg-method', ('none' if key == 'bg_nobanner' else 'standard'),
           '--prompt', prompt]
    for r in refs:
        cmd += ['--reference-image', r]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = '"status": "success"' in res.stdout
    print(('[OK] ' if ok else '[FAIL] ') + key, flush=True)
    if not ok:
        print(res.stdout[-250:], flush=True)
        sys.exit(1)
    src = glob.glob(os.path.join(out, '*', 'result_images_0_url.png'))[0]
    im = Image.open(src).convert('RGBA')
    if key == 'bg_nobanner':
        target_ratio = 1085 / 1450
        crop_w = int(im.height * target_ratio)
        x0 = (im.width - crop_w) // 2
        im = im.crop((x0, 0, x0 + crop_w, im.height))
        im = im.resize((1085, 1450), Image.LANCZOS)
        bg = Image.new('RGBA', im.size, (255, 249, 238, 255))
        bg.alpha_composite(im)
        bg.convert('RGB').save(BG)
        print('[IMPORT] bg_nobanner', bg.size, flush=True)
    else:
        im = im.crop((0, int(im.height * 0.30), im.width, int(im.height * 0.70)))
        im = im.resize((320, 104), Image.LANCZOS)
        im.save('assets/runtime/ui/pet_profile_new/banner_sticker.png')
        print('[IMPORT] banner_sticker', im.size, flush=True)
print('BANNER STICKER DONE', flush=True)
