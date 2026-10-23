"""五节图标第三版:软粉彩但要带色(上版'极低饱和'成灰白,用户打回)。"""
import glob, os, subprocess, sys
import numpy as np
from PIL import Image
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
OUT = 'assets/source/meowa/style-switch/section_icons_v3'
JOBS = {'icon_heart_affection.png': 'heart', 'icon_paw_attributes.png': 'round paw print',
        'icon_leaf_personality.png': 'small leaf', 'icon_star_level.png': 'five-pointed star',
        'icon_brush_style.png': 'paintbrush'}
STYLE = ("A single small {} icon for a pet profile section, painted in soft pastel watercolor "
 "with clearly visible gentle color: dusty coral-pink and warm cream for warm shapes, soft "
 "sage green for the leaf, muted golden apricot for the star and paintbrush. Soft watercolor "
 "washes, rounded cute shape, colors present but gentle (not gray, not neon, not saturated). "
 "Centered on plain transparent background, no text, no border, matte.")
for fn, shape in JOBS.items():
    r = subprocess.run([sys.executable, API, 'image-2.5-run', '--output-dir', os.path.join(OUT, shape.replace(' ', '_')),
     '--quality', 'detailed', '--resolution', '1K', '--remove-bg-method', 'standard',
     '--reference-image', 'assets/runtime/ui/pet_profile_new/icon_heart_affection.png',
     '--prompt', STYLE.format(shape)], capture_output=True, text=True, timeout=300)
    ok = '"status": "success"' in r.stdout
    print(('OK ' if ok else 'FAIL ') + shape, flush=True)
    if not ok: continue
    src = glob.glob(os.path.join(OUT, shape.replace(' ', '_'), '*', 'result_images_0_url.png'))[0]
    im = Image.open(src).convert('RGBA')
    a = np.array(im)[:, :, 3]; ys, xs = np.where(a > 40)
    content = im.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
    sc = 64 / max(content.size); nw, nh = int(content.width*sc), int(content.height*sc)
    content = content.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGBA', (72, 72), (0, 0, 0, 0))
    canvas.paste(content, ((72-nw)//2, (72-nh)//2), content)
    canvas.save(f'assets/runtime/ui/pet_profile_new/{fn}')
    print('IMPORT', fn, flush=True)
print('DONE', flush=True)
