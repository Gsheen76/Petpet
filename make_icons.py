"""Regenerate app icons from poses/idle.png with WHITE rounded background."""
import os
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
POSES_DIR = os.path.join(HERE, "poses")
ICON_DIR = os.path.join(HERE, "icons")
os.makedirs(ICON_DIR, exist_ok=True)

src = os.path.join(POSES_DIR, "idle.png")
im = Image.open(src).convert("RGBA")
W, H = im.size

import numpy as np
arr = np.array(im)
a = arr[:, :, 3]
ys, xs = np.where(a > 20)
x0, x1 = xs.min(), xs.max()
y0, y1 = ys.min(), ys.max()

crop = im.crop((x0, y0, x1 + 1, y1 + 1))
cw, ch = crop.size
# make square
side = max(cw, ch)

for size in [16, 32, 48, 64, 128, 256, 512, 1024]:
    # white rounded background
    bg = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = int(size * 0.18)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)
    white = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    white.putalpha(mask)
    bg = Image.alpha_composite(bg, white)

    # scale dog to fit inside (with small padding)
    pad = int(size * 0.08)
    inner = size - pad * 2
    dog = crop.resize((inner, int(inner * ch / cw)), Image.LANCZOS) if cw > ch else crop.resize((int(inner * cw / ch), inner), Image.LANCZOS)
    dw, dh = dog.size
    bg.paste(dog, ((size - dw) // 2, (size - dh) // 2), dog)

    # re-apply rounded mask so corners stay transparent
    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(bg, (0, 0), mask)
    path = os.path.join(ICON_DIR, f"icon-{size}.png")
    final.save(path)
    print(f"saved {path}")

print("done")
