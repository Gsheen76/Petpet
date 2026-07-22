"""Remove watermark from eat/happy/sad — v2.
Watermark is GRAYISH and high-alpha (text), at x[1335..1670] y[2161..2246].
Clear all grayish opaque pixels there; keep colorful ones (dog body)."""
import os, numpy as np
from PIL import Image

POSES_DIR = r"D:\opencode\desktop-pet\poses"
WM_X0, WM_X1 = 1320, 1672
WM_Y0, WM_Y1 = 2150, 2250

for name in ["eat", "happy", "sad"]:
    p = os.path.join(POSES_DIR, f"{name}.png")
    if not os.path.exists(p):
        print(f"skip {name}"); continue
    im = Image.open(p).convert("RGBA")
    arr = np.array(im)
    H, W = arr.shape[:2]
    sx = W / 1728; sy = H / 2304
    x0 = int(WM_X0 * sx); x1 = min(W, int(WM_X1 * sx))
    y0 = int(WM_Y0 * sy); y1 = min(H, int(WM_Y1 * sy))
    region = arr[y0:y1, x0:x1]
    r, g, b = region[:,:,0], region[:,:,1], region[:,:,2]
    a = region[:,:,3]
    # grayish = R,G,B close to each other (text/logo is gray, dog is colorful)
    grayish = (np.abs(r.astype(int)-g.astype(int)) < 30) & (np.abs(g.astype(int)-b.astype(int)) < 30)
    # clear grayish pixels that are semi-or-fully opaque (watermark)
    clear_mask = grayish & (a > 15)
    cleared = int(clear_mask.sum())
    region[clear_mask, 3] = 0
    region[clear_mask, :3] = 0
    arr[y0:y1, x0:x1] = region
    out = Image.fromarray(arr, "RGBA")
    out.save(os.path.join(POSES_DIR, f"{name}.png"))
    print(f"{name}: cleared {cleared} grayish watermark pixels")

print("done")
