# -*- coding: utf-8 -*-
"""棉花糖睡眠 v3:自然侧躺设计(蜷球被否「诡异」)——侧身躺、
四肢放松、长耳贴地、轻呼吸。锚=idle 首帧。"""
import glob, json, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
BASE = 'assets/source/meowa/style-switch/marshmallow'
OUT = os.path.join(BASE, 'sleep_v3')
RUNTIME = 'assets/runtime/pets/marshmallow/desktop/animations'
ANCHOR = os.path.join(RUNTIME, 'idle', '000.png')

PROMPT = (
    "A natural cozy sleep cycle for this cream-white watercolor rabbit: "
    "(1) the rabbit gently flops onto its side from the sitting pose - "
    "a cute relaxed side-lying position with all four legs stretched "
    "out naturally and its long ears resting flat on the ground; "
    "(2) then it sleeps in this side-lying position for a LONG middle "
    "section - only the round body softly rising and falling in slow "
    "calm breathing, eyes closed peacefully, one ear tip twitching "
    "once; hold this relaxed sleeping pose for most of the animation; "
    "(3) finally it lifts its head, stretches briefly, and sits back "
    "up to the same sitting pose. The pose transition should look "
    "natural and graceful, like a real sleeping rabbit. Keep the exact "
    "same character, colors, watercolor storybook art style and facing "
    "direction as the reference image in every frame. The whole action "
    "stays fully inside the canvas with generous empty space. Plain "
    "transparent background, no ground shadow, no extra objects, no "
    "text, no human hands.")

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
edges = []
for i in range(n):
    im.seek(i)
    fr = im.convert('RGBA')
    fr.save(os.path.join(frames_dir, f'{i:03d}.png'))
    al = np.array(fr)[:, :, 3]
    ys, xs = np.where(al > 50)
    edges.append((int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))
touches = sum(1 for x0, x1, y0, y1 in edges
              if x0 <= 2 or x1 >= 957 or y0 <= 2 or y1 >= 957)
print(f'edge-touch={touches}/32')

for name, (a, b) in (('sleep_fall', (0, 7)), ('sleep_loop', (8, 23)),
                      ('sleep_wake', (24, 31))):
    dst = os.path.join(RUNTIME, name)
    os.makedirs(dst, exist_ok=True)
    for old in os.listdir(dst):
        if old.endswith('.png'): os.remove(os.path.join(dst, old))
    for i in range(a, b + 1):
        shutil.copyfile(os.path.join(frames_dir, f'{i:03d}.png'),
                        os.path.join(dst, f'{i - a:03d}.png'))
    print(name, b - a + 1, 'frames')

mpath = os.path.join(RUNTIME, 'manifest.json')
with open(mpath, encoding='utf-8') as fh:
    manifest = json.load(fh)
manifest.pop('sleep', None)
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
    ImageDraw.Draw(tile).text((6, 212), str(i), fill=(120, 70, 40))
    tiles.append(tile)
sheet = Image.new('RGB', (210*8, 235*4), (250, 244, 235))
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
print('MM SLEEP V3 DONE')
