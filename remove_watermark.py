"""Remove watermark from bottom-right corner of pose PNGs.
Samples surrounding background and inpaints (fills) the watermark region."""
import os
from PIL import Image, ImageFilter
import numpy as np

POSES_DIR = r"D:\opencode\desktop-pet\poses"
OUT_DIR = os.path.join(POSES_DIR, "clean")
os.makedirs(OUT_DIR, exist_ok=True)

# Watermark region detected: x[1278..1671] y[2054..2245] for 1728x2304 images.
# Give some margin to fully cover it.
WM_X0, WM_X1 = 1250, 1728
WM_Y0, WM_Y1 = 2020, 2304

for name in ["idle","happy","sad","eat","sleep","drag"]:
    p = os.path.join(POSES_DIR, f"{name}.png")
    if not os.path.exists(p):
        print(f"skip {name}: missing"); continue
    im = Image.open(p).convert("RGBA")
    W, H = im.size
    arr = np.array(im)
    # scale watermark box to actual image size (in case resolution differs)
    sx = W / 1728; sy = H / 2304
    x0 = int(WM_X0 * sx); x1 = min(W, int(WM_X1 * sx))
    y0 = int(WM_Y0 * sy); y1 = min(H, int(WM_Y1 * sy))
    # sample background from a strip just above the watermark (transparent / bg color)
    # We'll fill the watermark region with fully transparent pixels, since these
    # are PNGs with transparency and the watermark sits on the alpha=0 background.
    # Easiest: set alpha=0 in the watermark region (make it transparent).
    arr[y0:y1, x0:x1, 3] = 0  # zero alpha
    # also clear any RGB there to avoid fringe
    arr[y0:y1, x0:x1, :3] = 0
    out = Image.fromarray(arr, "RGBA")
    # soft edge so it doesn't look like a hard rectangle
    out = out.filter(ImageFilter.GaussianBlur(radius=0))  # no blur; keep crisp
    op = os.path.join(OUT_DIR, f"{name}.png")
    out.save(op)
    print(f"cleaned {name} -> {op}")

print("done")
