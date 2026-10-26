# -*- coding: utf-8 -*-
"""全游戏素材焕新批(2026-10-26 用户令:每功能至少一件 Meowa 重生)。
五件:商店大底图(覆盖 商店/成就/记录/每日/设置/小游戏/聊天公共底)、
面板改名名牌、家具沙发、宠物配饰(天空领结)、应用图标族。"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/refresh_batch'
STYLE_REF = 'assets/runtime/pets/marshmallow/avatar.png'

JOBS = [
    {
        'key': 'shop_bg',
        'target': 'assets/runtime/ui/shop/background.png',
        'aspect': '3:4',
        'prompt': (
            "A soft warm cream watercolor paper background for a cozy pet "
            "game panel, portrait orientation: gentle ivory-cream washes "
            "with a very subtle warm coral tint at the edges, faint "
            "watercolor paper texture, extremely subtle and plain - no "
            "objects, no text, no characters, nothing baked in, just a "
            "calm watercolor paper suitable as a UI background."),
    },
    {
        'key': 'rename_plate',
        'target': 'assets/runtime/ui/pet_profile_new/rename_bg.png',
        'aspect': '16:9',
        'prompt': (
            "A horizontal watercolor nameplate banner for a pet game: a "
            "long rounded cream ribbon banner with soft coral-pink edges "
            "and a tiny paw print accent on the left, soft watercolor "
            "storybook style, plain center area for a name to be drawn "
            "later, transparent background around the banner, no text, "
            "no characters."),
    },
    {
        'key': 'sofa',
        'target': 'assets/runtime/furniture/home/sofa.png',
        'aspect': '16:9',
        'ref': 'assets/runtime/furniture/home/sofa.png',
        'prompt': (
            "A cute watercolor sofa for a cozy pet home scene: a soft "
            "cream-yellow rounded two-seat sofa with warm coral cushion "
            "accents, side view, single furniture piece, gentle "
            "watercolor storybook style matching the reference image's "
            "shape and proportions, plain transparent background, no "
            "text, no characters."),
    },
    {
        'key': 'bow_tie',
        'target': 'assets/runtime/decorations/sky_bow_tie.png',
        'aspect': '1:1',
        'ref': 'assets/runtime/decorations/sky_bow_tie.png',
        'prompt': (
            "A single cute sky-blue bow tie pet accessory, watercolor "
            "storybook style with soft washes, centered, same bow shape "
            "as the reference image, plain transparent background, no "
            "text, no characters."),
    },
    {
        'key': 'app_icon',
        'target': 'assets/runtime/icons/icon-256.png',
        'aspect': '1:1',
        'ref': 'assets/runtime/pets/lunch_meat/avatar.png',
        'prompt': (
            "A cute round app icon: an orange-brown shiba-like watercolor "
            "puppy face peeking from a soft cream circle with a warm "
            "coral ring border, soft watercolor storybook style like the "
            "reference avatar, centered, filling most of the circle, "
            "plain background outside the circle, no text."),
    },
]


def run(job):
    cmd = [sys.executable, API, 'image-2.5-run',
           '--output-dir', os.path.join(OUT, job['key']),
           '--quality', 'detailed', '--resolution', '1K',
           '--remove-bg-method', 'standard',
           '--reference-image', job.get('ref', STYLE_REF),
           '--aspect-ratio', job['aspect'],
           '--prompt', job['prompt']]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    ok = '"status": "success"' in r.stdout
    print(('[OK] ' if ok else '[FAIL] ') + job['key'], flush=True)
    if not ok:
        print(r.stdout[-250:], flush=True)
    return ok


def import_job(job):
    src = glob.glob(os.path.join(OUT, job['key'], '*', 'result_images_0_url.png'))[0]
    orig = Image.open(job['target'])
    w, h = orig.size
    im = Image.open(src).convert('RGBA')
    if job['key'] == 'rename_plate':
        # 16:9 → 3.93:1 横幅:取中心条带
        im = im.crop((0, int(im.height * 0.30), im.width, int(im.height * 0.70)))
    im = im.resize((w, h), Image.LANCZOS)
    im.save(job['target'])
    print('[IMPORT]', job['key'], (w, h), flush=True)


for job in JOBS:
    if run(job):
        import_job(job)

# 应用图标族:从 256 母版重出各尺寸
master = Image.open('assets/runtime/icons/icon-256.png').convert('RGBA')
for f in os.listdir('assets/runtime/icons'):
    if f.startswith('icon-') and f.endswith('.png'):
        n = int(f.split('-')[1].split('.')[0])
        if n != 256:
            master.resize((n, n), Image.LANCZOS).save(
                'assets/runtime/icons/' + f)
            print('[ICON]', n, flush=True)
print('REFRESH BATCH DONE', flush=True)
