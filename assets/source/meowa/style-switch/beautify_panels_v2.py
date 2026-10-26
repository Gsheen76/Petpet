# -*- coding: utf-8 -*-
"""五面板主题化背景 v2(2026-10-26 用户令:背景要讲功能故事,如小游戏=
三只小宠物一起玩耍;小而柔和,画风一致)+聊天界面专属背景。
三宠 avatar 作参照锚定身份;角落小景占幅<1/4,中心素净可读。"""
import glob
import os
import subprocess
import sys

from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/panel_beautify_v2'
DST = 'assets/runtime/ui/panels'
REFS = [
    'assets/runtime/pets/lunch_meat/avatar.png',
    'assets/runtime/pets/ice_cream/avatar.png',
    'assets/runtime/pets/marshmallow/avatar.png',
]

BASE = (
    "A soft warm cream watercolor paper background for a cozy pet game "
    "panel, portrait orientation. In the bottom-right corner ONLY there is "
    "a small delicate watercolor vignette (taking less than a quarter of "
    "the canvas, small and subtle) of the three cute pets from the "
    "reference images playing together: {scene}. The rest of the canvas "
    "is plain calm ivory watercolor paper - no other objects, no text, "
    "no letters, no numbers anywhere.")

SCENES = {
    'panel_bg_games.png': (
        "the three tiny pets chasing one small coral ball, mid-play with "
        "joyful poses"),
    'panel_bg_daily.png': (
        "the three tiny pets gathered around a tiny blank wall calendar "
        "sheet, one paw stamping a paw print on it"),
    'panel_bg_records.png': (
        "the three tiny pets sitting beside one small open blank diary "
        "book, with a short trail of tiny paw prints leading to it"),
    'panel_bg_achievements.png': (
        "the three tiny pets wearing tiny gold medals, with a few small "
        "stars floating around them"),
    'panel_bg_settings.png': (
        "the three tiny pets resting cozily beside a few small rounded "
        "switches and a tiny heart"),
    'panel_bg_chat.png': (
        "the three tiny pets with small EMPTY rounded speech bubbles "
        "above their heads and one tiny heart between two of them"),
}


def main():
    for name, scene in SCENES.items():
        out = os.path.join(OUT, name.replace('.png', ''))
        cmd = [sys.executable, API, 'image-2.5-run',
               '--output-dir', out, '--quality', 'detailed',
               '--resolution', '1K', '--aspect-ratio', '3:4',
               '--remove-bg-method', 'none']
        for r in REFS:
            cmd += ['--reference-image', r]
        cmd += ['--prompt', BASE.format(scene=scene)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = '"status": "success"' in result.stdout
        print(('[OK] ' if ok else '[FAIL] ') + name, flush=True)
        if not ok:
            print(result.stdout[-250:], flush=True)
            continue
        src = glob.glob(os.path.join(out, '*', 'result_images_0_url.png'))[0]
        im = Image.open(src).convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 249, 238, 255))
        bg.alpha_composite(im)
        bg = bg.resize((1126, 1359), Image.LANCZOS)
        bg.convert('RGB').save(os.path.join(DST, name))
        print('[IMPORT]', name, flush=True)
    print('THEMED BG DONE', flush=True)


if __name__ == '__main__':
    main()
