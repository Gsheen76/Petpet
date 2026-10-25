"""商店套装参考图水彩化(2026-10-25):恐龙/草莓 preview.png 重生成
(参照=现参考图内容+午餐肉新装锚,软水彩风),覆盖原文件。"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/outfit_previews'
DST = 'assets/runtime/pets/lunch_meat/desktop/outfits'
ANCHOR = 'assets/source/meowa/style-switch/lunch_meat/anchor_v3b.png'

JOBS = {
    'dinosaur': (
        "A product preview illustration of a cute puppy wearing a green "
        "dinosaur costume with small spikes along the back and a dinosaur "
        "hood, shown as a single full-body side-view character. Keep the "
        "costume design and pose similar to the first reference image, but "
        "repaint everything in the soft warm watercolor storybook style of "
        "the second reference image (same puppy identity: orange-brown "
        "shiba-like fur, cream chest, red plaid collar with golden tag). "
        "Generous empty margins, plain transparent background, no text, "
        "no frame."),
    'strawberry': (
        "A product preview illustration of a cute puppy wearing a strawberry "
        "hooded suit with a leaf collar and strawberry decorations, shown as "
        "a single full-body side-view character. Keep the costume design and "
        "pose similar to the first reference image, but repaint everything "
        "in the soft warm watercolor storybook style of the second reference "
        "image (same puppy identity: orange-brown shiba-like fur, cream "
        "chest, red plaid collar with golden tag). Generous empty margins, "
        "plain transparent background, no text, no frame."),
}

for key, prompt in JOBS.items():
    cur = os.path.join(DST, key, 'preview.png')
    r = subprocess.run([sys.executable, API, 'image-2.5-run',
        '--output-dir', os.path.join(OUT, key), '--quality', 'detailed',
        '--resolution', '1K', '--remove-bg-method', 'standard',
        '--reference-image', cur, '--reference-image', ANCHOR,
        '--prompt', prompt], capture_output=True, text=True, timeout=300)
    ok = '"status": "success"' in r.stdout
    print(('OK ' if ok else 'FAIL ') + key, flush=True)
    if not ok:
        print(r.stdout[-300:], flush=True)
        continue
    src = glob.glob(os.path.join(OUT, key, '*', 'result_images_0_url.png'))[0]
    im = Image.open(src).convert('RGBA')
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 40)
    content = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    # 目标高 900(显示框 210x150 等比,保留高清余量)
    scale = 900 / content.height
    content = content.resize((max(1, int(content.width * scale)), 900),
                             Image.LANCZOS)
    canvas = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    canvas.paste(content, ((1024 - content.width) // 2, 62), content)
    canvas.save(cur)
    print('IMPORT', key, canvas.size, flush=True)
print('PREVIEWS DONE', flush=True)
