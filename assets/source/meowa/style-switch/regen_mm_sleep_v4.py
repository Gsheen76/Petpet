# -*- coding: utf-8 -*-
"""棉花糖睡眠 v4:大留白锚重生成(微调被否「没用」)。
62% 体量锚+大留白提示词,从源头保证零触边。"""
import glob, json, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
BASE = 'assets/source/meowa/style-switch/marshmallow'
OUT = os.path.join(BASE, 'sleep_v4')
RUNTIME = 'assets/runtime/pets/marshmallow/desktop/animations'
ANCHOR_SRC = os.path.join(RUNTIME, 'idle', '000.png')

# 62% 垫边锚
im = Image.open(ANCHOR_SRC).convert('RGBA')
a = np.array(im)[:, :, 3]
ys, xs = np.where(a > 40)
content = im.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
scale = 600 / content.height
cw, ch = int(content.width*scale), 600
content = content.resize((cw, ch), Image.LANCZOS)
ANCHOR = os.path.join(BASE, 'anchor_62.png')
canvas = Image.new('RGBA', (1024, 1024), (0,0,0,0))
canvas.paste(content, ((1024-cw)//2, (1024-212-ch)), content)
canvas.save(ANCHOR)
print(f'62% anchor: content {cw}x{ch} 底距212 顶距{212} 侧距{(1024-cw)//2}')

PROMPT = (
    "A natural cozy sleep cycle for this cream-white watercolor rabbit, "
    "keeping the character SMALL in the frame with very generous empty "
    "margins all around (the rabbit takes up only about 60% of the "
    "canvas height, centered, with large breathing room on all sides): "
    "(1) the rabbit gently flops onto its side from the sitting pose - "
    "a relaxed side-lying position with legs stretched naturally and "
    "long ears resting on the ground; (2) then it sleeps calmly in "
    "this side-lying pose for a LONG middle section - only the body "
    "softly rising and falling in slow breathing, eyes closed, one ear "
    "tip twitching once; hold this for most of the animation; (3) "
    "finally it lifts its head, stretches, and sits back up. The "
    "ENTIRE rabbit including the longest ear tips must stay well "
    "inside the canvas edges at all times - nothing ever touches or "
    "goes beyond the canvas boundary. Same character, colors, "
    "watercolor style as the reference. Plain transparent background, "
    "no text, no hands.")

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
    m = min(int(xs2.min()), 959-int(xs2.max()), int(ys2.min()), 959-int(ys2.max()))
    worst = min(worst, m)
print(f'全帧最差边距(alpha>10): {worst}px')
if worst < 15:
    print('!! 留白不足,缩95%兜底')
    for i in range(n):
        p = os.path.join(frames_dir, f'{i:03d}.png')
        fr = Image.open(p).convert('RGBA')
        nw, nh = int(fr.width*0.95), int(fr.height*0.95)
        sc = fr.resize((nw, nh), Image.LANCZOS)
        c = Image.new('RGBA', fr.size, (0,0,0,0))
        c.paste(sc, ((fr.width-nw)//2, (fr.height-nh)//2), sc)
        c.save(p)

for name, (a2, b) in (('sleep_fall', (0, 7)), ('sleep_loop', (8, 23)),
                       ('sleep_wake', (24, 31))):
    dst = os.path.join(RUNTIME, name)
    os.makedirs(dst, exist_ok=True)
    for old in os.listdir(dst):
        if old.endswith('.png'): os.remove(os.path.join(dst, old))
    for i in range(a2, b + 1):
        shutil.copyfile(os.path.join(frames_dir, f'{i:03d}.png'),
                        os.path.join(dst, f'{i - a2:03d}.png'))
    print(name, b - a2 + 1, 'frames')

mpath = os.path.join(RUNTIME, 'manifest.json')
with open(mpath, encoding='utf-8') as fh:
    manifest = json.load(fh)
idle_scale = manifest.get('idle', {}).get('scale', 1.0)
for name, count, loop in (('sleep_fall', 8, False), ('sleep_loop', 16, True),
                          ('sleep_wake', 8, False)):
    manifest[name] = {"folder": name, "fps": 8, "loop": loop,
                      "fallback": "idle", "scale": idle_scale,
                      "anchor_bottom": False, "saturation": 1.0,
                      "brightness": 1.0, "frame_durations_ms": [125]*count}
with open(mpath, 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=2)

tiles = []
for i in range(n):
    fr = Image.open(os.path.join(frames_dir, f'{i:03d}.png'))
    fr.thumbnail((200, 200), Image.LANCZOS)
    tile = Image.new('RGB', (210, 235), (250, 244, 235))
    tile.paste(fr, ((210-fr.width)//2, 6), fr)
    ImageDraw.Draw(tile).text((6, 212), str(i), fill=(120,70,40))
    tiles.append(tile)
sheet = Image.new('RGB', (210*8, 235*4), (250,244,235))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i%8)*210, (i//8)*235))
sheet.save(os.path.join(OUT, 'audit_sheet.jpg'), quality=88)
concat = os.path.join(OUT, 'concat.txt')
with open(concat, 'w') as f:
    for _ in range(2):
        for i in range(n):
            f.write('file ' + os.path.abspath(
                os.path.join(frames_dir, f'{i:03d}.png')).replace(chr(92),'/') + chr(10))
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-r','8','-i',concat,
                '-c:v','libx264','-pix_fmt','yuv420p',
                '-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2',
                os.path.join(OUT, 'preview.mp4')], capture_output=True)
os.remove(concat)
print('MM SLEEP V4 DONE')
