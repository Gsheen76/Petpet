# -*- coding: utf-8 -*-
"""棉花糖睡眠 v5:留白再扩大(62%→49% 体量,scale 1.84 补偿大小统一)。"""
import glob, json, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
BASE = 'assets/source/meowa/style-switch/marshmallow'
OUT = os.path.join(BASE, 'sleep_v5')
RUNTIME = 'assets/runtime/pets/marshmallow/desktop/animations'
ANCHOR = os.path.join(BASE, 'anchor_49.png')

PROMPT = (
    "A natural cozy sleep cycle for this cream-white watercolor rabbit. "
    "The rabbit stays SMALL in the frame - only about half the canvas "
    "height - centered with very generous empty margins on ALL sides. "
    "(1) The rabbit gently flops onto its side from sitting - relaxed "
    "side-lying, legs stretched, long ears resting on the ground. "
    "(2) It sleeps calmly in this side-lying pose for a LONG middle "
    "section - only slow gentle breathing, eyes closed, one ear tip "
    "twitching once. (3) It lifts its head, stretches, sits back up. "
    "The ENTIRE rabbit including longest ear tips stays well inside "
    "the canvas with large breathing room everywhere. Same character, "
    "colors, watercolor style as reference. Plain transparent "
    "background, no text, no hands.")

r = subprocess.run([sys.executable, API, 'meowa-animation-run',
    '--output-dir', OUT, '--image-file', ANCHOR,
    '--last-image-file', ANCHOR, '--style-mode', 'hd',
    '--resolution', '720p', '--output-frames', '32',
    '--quality-mode', 'medium', '--alpha-mode', 'soft',
    '--remove-bg-method', 'standard', '--no-optimize-prompt',
    '--prompt', PROMPT], capture_output=True, text=True, timeout=900)
ok = '"status": "success"' in r.stdout
print('gen:', 'OK' if ok else 'FAIL')
if not ok: print(r.stdout[-400:]); sys.exit(1)
src = sorted(glob.glob(os.path.join(OUT, '*', 'meowa_animation.webp')),
             key=os.path.getmtime)[-1]
im = Image.open(src)
n = getattr(im, 'n_frames', 1)
print('frames', n)
if n != 32: sys.exit(f'expect 32, got {n}')
frames_dir = os.path.join(OUT, 'frames')
os.makedirs(frames_dir, exist_ok=True)
worst = 999
for i in range(n):
    im.seek(i)
    fr = im.convert('RGBA')
    fr.save(os.path.join(frames_dir, f'{i:03d}.png'))
    al = np.array(fr)[:, :, 3]
    ys2, xs2 = np.where(al > 10)
    if len(ys2)==0: continue
    m2 = min(int(xs2.min()), 959-int(xs2.max()), int(ys2.min()), 959-int(ys2.max()))
    worst = min(worst, m2)
print(f'最差边距(alpha>10): {worst}px')

for name, (a2, b) in (('sleep_fall', (0,7)), ('sleep_loop', (8,23)),
                       ('sleep_wake', (24,31))):
    dst = os.path.join(RUNTIME, name)
    os.makedirs(dst, exist_ok=True)
    for old in os.listdir(dst):
        if old.endswith('.png'): os.remove(os.path.join(dst, old))
    for i in range(a2, b+1):
        shutil.copyfile(os.path.join(frames_dir, f'{i:03d}.png'),
                        os.path.join(dst, f'{i-a2:03d}.png'))
    print(name, b-a2+1)

tiles = []
for i in range(n):
    fr = Image.open(os.path.join(frames_dir, f'{i:03d}.png'))
    fr.thumbnail((200,200), Image.LANCZOS)
    tile = Image.new('RGB', (210,235), (250,244,235))
    tile.paste(fr, ((210-fr.width)//2,6), fr)
    ImageDraw.Draw(tile).text((6,212), str(i), fill=(120,70,40))
    tiles.append(tile)
sheet = Image.new('RGB', (210*8,235*4), (250,244,235))
for i,t in enumerate(tiles): sheet.paste(t, ((i%8)*210,(i//8)*235))
sheet.save(os.path.join(OUT,'audit_sheet.jpg'), quality=88)
concat = os.path.join(OUT,'concat.txt')
with open(concat,'w') as f:
    for _ in range(2):
        for i in range(n):
            f.write('file '+os.path.abspath(os.path.join(frames_dir,f'{i:03d}.png')).replace(chr(92),'/')+chr(10))
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-r','8','-i',concat,
                '-c:v','libx264','-pix_fmt','yuv420p',
                '-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2',
                os.path.join(OUT,'preview.mp4')], capture_output=True)
os.remove(concat)
print('V5 DONE')
