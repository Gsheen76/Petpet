"""Precisely remove watermark text from eat/happy/sad PNGs.
Only clears semi-transparent text pixels (alpha 30-230, grayish),
leaving the dog body (alpha~255) untouched."""
import os, numpy as np
from PIL import Image

POSES_DIR = r"D:\opencode\desktop-pet\poses"
# detected watermark region for these 1728x2304 images
WM_X0, WM_X1 = 1330, 1672
WM_Y0, WM_Y1 = 2150, 2250

for name in ["eat", "happy", "sad"]:
    p = os.path.join(POSES_DIR, f"{name}.png")
    if not os.path.exists(p):
        print(f"skip {name}: missing"); continue
    im = Image.open(p).convert("RGBA")
    arr = np.array(im)
    H, W = arr.shape[:2]
    # scale to actual size
    sx = W / 1728; sy = H / 2304
    x0 = int(WM_X0 * sx); x1 = min(W, int(WM_X1 * sx))
    y0 = int(WM_Y0 * sy); y1 = min(H, int(WM_Y1 * sy))
    # only clear text-like pixels within this region
    region = arr[y0:y1, x0:x1]
    alpha = region[:, :, 3]
    gray = region[:, :, :3].mean(axis=2)
    # watermark text: semi-transparent (not fully opaque like dog) + light/gray colored
    text_mask = (alpha > 20) & (alpha < 235) & (gray > 60) & (gray < 235)
    cleared = int(text_mask.sum())
    # set those pixels to fully transparent
    region[text_mask, 3] = 0
    region[text_mask, :3] = 0
    # write back (region is a view)
    arr[y0:y1, x0:x1] = region
    out = Image.fromarray(arr, "RGBA")
    # also clean up any fringe: slight blur on alpha channel of the cleared region
    op = os.path.join(POSES_DIR, f"{name}.png")
    out.save(op)
    print(f"{name}: cleared {cleared} watermark pixels in x[{x0}..{x1}] y[{y0}..{y1}]")

print("done")
