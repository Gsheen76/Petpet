"""pet v4b:去手心意象(引擎画成实体占满画布),改纯享受表情+轻蹭头。"""
import glob, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
BASE = 'assets/source/meowa/style-switch'
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
ANCHOR = os.path.join(BASE, 'lunch_meat', 'anchor_v3b.png')
PROMPT = (
    "A blissful enjoyed-pat reaction with no objects at all: the sitting "
    "puppy slowly tilts its head up and slightly to the side, eyes "
    "closing in pure contentment, one ear flopping over, cheeks looking "
    "warmly squished, tail thumping happily against the ground beside "
    "it, then settles back to the same sitting pose. The mouth stays "
    "gently closed in a soft smile. The red plaid collar with a small "
    "round golden tag stays around the puppy's neck in every frame. "
    "Keep the exact same character, colors, watercolor storybook art "
    "style and facing direction as the reference image in every frame. "
    "Only the single puppy exists - no hands, no paws from above, no "
    "props, no extra objects. The whole action stays fully inside the "
    "canvas with generous empty space around the character - nothing is "
    "ever cut off by the canvas edge. Plain transparent background, no "
    "ground shadow, no text."
)
out = os.path.join(BASE, 'lunch_meat', 'pet_v4')
r = subprocess.run([sys.executable, API, 'meowa-animation-run',
    '--output-dir', out, '--image-file', ANCHOR, '--last-image-file', ANCHOR,
    '--style-mode', 'hd', '--resolution', '720p', '--output-frames', '16',
    '--quality-mode', 'medium', '--alpha-mode', 'soft',
    '--remove-bg-method', 'standard', '--no-optimize-prompt',
    '--prompt', PROMPT], capture_output=True, text=True, timeout=900)
ok = '"status": "success"' in r.stdout
print('gen pet v4b:', 'OK' if ok else 'FAIL')
if not ok:
    print(r.stdout[-300:]); sys.exit(1)
src = sorted(glob.glob(os.path.join(out, '*', 'meowa_animation.webp')), key=os.path.getmtime)[-1]
im = Image.open(src)
n = getattr(im, 'n_frames', 1)
print('frames', n)
frames_dir = os.path.join(out, 'frames')
os.makedirs(frames_dir, exist_ok=True)
dst = 'assets/runtime/pets/lunch_meat/desktop_new/animations/pet'
edges = []
for i in range(n):
    im.seek(i)
    fr = im.convert('RGBA')
    fr.save(os.path.join(frames_dir, f'{i:03d}.png'))
    with open(os.path.join(frames_dir, f'{i:03d}.png'), 'rb') as fh:
        data = fh.read()
    with open(os.path.join(dst, f'{i:03d}.png'), 'wb') as fo:
        fo.write(data)
    al = np.array(fr)[:, :, 3]
    ys, xs = np.where(al > 50)
    edges.append((int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))
touches = sum(1 for x0, x1, y0, y1 in edges if x0 <= 2 or x1 >= 957 or y0 <= 2 or y1 >= 957)
print(f'edge-touch={touches}/16 bbox x{min(e[0] for e in edges)}-{max(e[1] for e in edges)} y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}')
tiles = []
for i in range(n):
    fr = Image.open(os.path.join(frames_dir, f'{i:03d}.png'))
    fr.thumbnail((230, 230), Image.LANCZOS)
    tile = Image.new('RGB', (240, 270), (250, 244, 235))
    tile.paste(fr, ((240 - fr.width) // 2, 8), fr)
    ImageDraw.Draw(tile).text((8, 244), str(i), fill=(120, 70, 40))
    tiles.append(tile)
sheet = Image.new('RGB', (960, 1080), (250, 244, 235))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 4) * 240, (i // 4) * 270))
sheet.save(os.path.join(out, 'audit_sheet.jpg'), quality=88)
concat = os.path.join(out, 'concat.txt')
with open(concat, 'w') as f:
    for _ in range(2):
        for i in range(n):
            f.write('file ' + os.path.abspath(os.path.join(frames_dir, f'{i:03d}.png')).replace(chr(92), '/') + chr(10))
subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-r', '8', '-i', concat,
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                os.path.join(out, 'preview.mp4')], capture_output=True)
os.remove(concat)
print('reimport done')
