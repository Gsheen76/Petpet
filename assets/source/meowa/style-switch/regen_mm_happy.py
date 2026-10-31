# -*- coding: utf-8 -*-
"""棉花糖 happy(登场/开机)动画重做:62% 锚+雕像级锁位根治水平漂移 54px。"""
import glob, json, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
BASE = 'assets/source/meowa/style-switch/marshmallow'
OUT = os.path.join(BASE, 'happy_v2')
RUNTIME = 'assets/runtime/pets/marshmallow/desktop/animations'

# 62% 垫边锚(与 sleep v4 同规格,用户已认可该比例)
im = Image.open(os.path.join(RUNTIME, 'idle', '000.png')).convert('RGBA')
a = np.array(im)[:, :, 3]
ys, xs = np.where(a > 40)
content = im.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
scale = 600 / content.height
cw, ch = int(content.width*scale), 600
content = content.resize((cw, ch), Image.LANCZOS)
ANCHOR = os.path.join(BASE, 'anchor_62.png')
canvas = Image.new('RGBA', (1024, 1024), (0,0,0,0))
canvas.paste(content, ((1024-cw)//2, 1024-212-ch), content)
canvas.save(ANCHOR)

PROMPT = (
    "A joyful happy animation for this cream-white watercolor rabbit. "
    "The body, torso, head and all four paws stay LOCKED in one fixed "
    "position like a photograph - zero horizontal drift, zero shifting, "
    "zero bouncing. Only these motions are allowed: the ears perk up "
    "and wiggle happily, the eyes squeeze into happy crescents, the "
    "nose twitches, and the round tail gives a tiny excited wiggle. "
    "The rabbit stays in the exact same centered position throughout "
    "the entire animation. Same character, colors, watercolor style as "
    "the reference. Generous empty margins around the character. Plain "
    "transparent background, no text, no hands, no extra objects.")

r = subprocess.run([sys.executable, API, 'meowa-animation-run',
    '--output-dir', OUT, '--image-file', ANCHOR,
    '--last-image-file', ANCHOR, '--style-mode', 'hd',
    '--resolution', '720p', '--output-frames', '16',
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

frames_dir = os.path.join(OUT, 'frames')
os.makedirs(frames_dir, exist_ok=True)
cxs, bots = [], []
for i in range(n):
    im.seek(i)
    fr = im.convert('RGBA')
    fr.save(os.path.join(frames_dir, f'{i:03d}.png'))
    al = np.array(fr)[:, :, 3]
    ys2, xs2 = np.where(al > 50)
    cxs.append((xs2.min()+xs2.max())/2)
    bots.append(ys2.max())
print(f'cx 极差: {max(cxs)-min(cxs):.0f}px  底极差: {max(bots)-min(bots):.0f}px')

# 导入 runtime(替换旧 happy)
dst = os.path.join(RUNTIME, 'happy')
os.makedirs(dst, exist_ok=True)
for old in os.listdir(dst):
    if old.endswith('.png'): os.remove(os.path.join(dst, old))
for i in range(n):
    shutil.copyfile(os.path.join(frames_dir, f'{i:03d}.png'),
                    os.path.join(dst, f'{i:03d}.png'))
print('happy', n, 'frames imported')

# manifest 更新帧数
mpath = os.path.join(RUNTIME, 'manifest.json')
with open(mpath, encoding='utf-8') as fh:
    manifest = json.load(fh)
manifest['happy']['frame_durations_ms'] = [125] * n
manifest['happy']['scale'] = 1.54  # 与 sleep 同补偿(62% 锚)
with open(mpath, 'w', encoding='utf-8') as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=2)
print('manifest updated')

tiles = []
for i in range(n):
    fr = Image.open(os.path.join(frames_dir, f'{i:03d}.png'))
    fr.thumbnail((200,200), Image.LANCZOS)
    tile = Image.new('RGB', (210,235), (250,244,235))
    tile.paste(fr, ((210-fr.width)//2,6), fr)
    ImageDraw.Draw(tile).text((6,212), str(i), fill=(120,70,40))
    tiles.append(tile)
sheet = Image.new('RGB', (210*4,235*4), (250,244,235))
for i,t in enumerate(tiles): sheet.paste(t, ((i%4)*210,(i//4)*235))
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
print('HAPPY V2 DONE')
