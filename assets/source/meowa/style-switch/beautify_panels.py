# -*- coding: utf-8 -*-
"""五面板素材美化(2026-10-26 用户令:设置/小游戏/成就/记录/每日)。
5 张专属水彩底图(同奶油纸系+各一层极淡主题色+右下角烘焙小装饰,
装饰烘进底图不加新控件)+2 枚共享水彩胶囊按钮皮肤(常规/悬浮)。"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/panel_beautify'
DST = 'assets/runtime/ui/panels'
os.makedirs(DST, exist_ok=True)

BG_TPL = (
    "A soft warm cream watercolor paper background for a cozy pet game "
    "panel, portrait orientation: gentle ivory washes with a very subtle "
    "{tint} tint, faint watercolor paper texture, and a small delicate "
    "watercolor decoration of tiny paw prints and a little flower sprig "
    "baked into the bottom-right corner only. The center stays extremely "
    "plain and calm - no objects, no text, no characters, suitable as a "
    "UI background with readable content on top.")

BGS = {
    'panel_bg_daily.png': 'soft rose-pink',
    'panel_bg_records.png': 'soft sage-green',
    'panel_bg_achievements.png': 'soft honey-gold',
    'panel_bg_games.png': 'soft coral-orange',
    'panel_bg_settings.png': 'warm sand-beige',
}

BTN_NORMAL = (
    "A single horizontal watercolor pill button skin: a rounded capsule "
    "shape filled with soft warm coral watercolor wash, slightly darker "
    "coral edge, gentle paper texture, stretching edge to edge of the "
    "wide frame, plain cream nothing else - no text, no icons, no "
    "characters.")
BTN_HOVER = (
    "A single horizontal watercolor pill button skin: a rounded capsule "
    "shape filled with a slightly deeper warm coral watercolor wash than "
    "the reference image, gentle paper texture, stretching edge to edge "
    "of the wide frame - no text, no icons, no characters.")


def gen(key, prompt, aspect, refs=()):
    out = os.path.join(OUT, key.replace('.png', ''))
    cmd = [sys.executable, API, 'image-2.5-run',
           '--output-dir', out, '--quality', 'detailed',
           '--resolution', '1K', '--remove-bg-method', 'standard'
           if key.endswith('.png') and key.startswith('btn') is False
           else '--remove-bg-method', 'none']
    # 简化:底图无需抠透明(整幅方图),按钮皮肤需要透明
    cmd = [sys.executable, API, 'image-2.5-run',
           '--output-dir', out, '--quality', 'detailed',
           '--resolution', '1K', '--aspect-ratio', aspect,
           '--remove-bg-method', ('none' if key.startswith('panel_bg')
                                  else 'standard'),
           '--prompt', prompt]
    for r in refs:
        cmd += ['--reference-image', r]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = '"status": "success"' in r.stdout
    print(('[OK] ' if ok else '[FAIL] ') + key, flush=True)
    if not ok:
        print(r.stdout[-250:], flush=True)
        return None
    return glob.glob(os.path.join(out, '*', 'result_images_0_url.png'))[0]


def main():
    for name, tint in BGS.items():
        src = gen(name, BG_TPL.format(tint=tint), '3:4')
        if not src:
            continue
        im = Image.open(src).convert('RGBA')
        # 底图不透明铺满(与 shop 底图同规格 1126×1359)
        bg = Image.new('RGBA', im.size, (255, 249, 238, 255))
        bg.alpha_composite(im)
        bg = bg.resize((1126, 1359), Image.LANCZOS)
        bg.convert('RGB').save(os.path.join(DST, name))
        print('[IMPORT]', name, bg.size, flush=True)

    n = gen('btn_pill_normal.png', BTN_NORMAL, '16:9')
    if n:
        im = Image.open(n).convert('RGBA')
        im = im.crop((0, int(im.height * 0.28), im.width, int(im.height * 0.72)))
        im = im.resize((360, 88), Image.LANCZOS)
        im.save(os.path.join(DST, 'btn_pill_normal.png'))
        print('[IMPORT] btn_pill_normal.png', im.size, flush=True)
    h = gen('btn_pill_hover.png', BTN_HOVER, '16:9',
            refs=(os.path.join(DST, 'btn_pill_normal.png'),))
    if h:
        im = Image.open(h).convert('RGBA')
        im = im.crop((0, int(im.height * 0.28), im.width, int(im.height * 0.72)))
        im = im.resize((360, 88), Image.LANCZOS)
        im.save(os.path.join(DST, 'btn_pill_hover.png'))
        print('[IMPORT] btn_pill_hover.png', im.size, flush=True)
    print('PANEL BEAUTIFY DONE', flush=True)


if __name__ == '__main__':
    main()
