"""冰淇淋新装睡眠补全:32 帧三段式(温柔恬静设计)→拆 fall/loop/wake→manifest。
drag 已设 loop=true(与午餐肉统一)。
"""
import glob
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
RUNTIME = os.path.join("assets", "runtime", "pets")
ANCHOR = os.path.join(BASE, "ice_cream", "anchor_v3b.png")

PROMPT = (
    "A long gentle sleep cycle: (1) the puppy softly curls down into a "
    "round fluffy ball beside its sitting spot, fluffy tail wrapping over "
    "its nose; (2) then it stays asleep in this curled ball for a LONG "
    "middle section - only the body slowly rising and falling in calm "
    "breathing, an ear tip twitching once softly; hold this sleeping ball "
    "pose for most of the animation; (3) finally it stretches delicately "
    "and uncurls back to the same sitting pose. The mouth stays gently "
    "closed. The small green neck scarf stays on in every frame. Keep the "
    "exact same character, colors, watercolor storybook art style and "
    "facing direction as the reference image in every frame. The whole "
    "action stays fully inside the canvas with generous empty space around "
    "the character - nothing is ever cut off by the canvas edge. Plain "
    "transparent background, no ground shadow, no extra objects, no text, "
    "no human hands."
)

SCALE = 1.2229


def main():
    out = os.path.join(BASE, "ice_cream", "sleep_v1")
    r = subprocess.run(
        [sys.executable, API, "meowa-animation-run",
         "--output-dir", out, "--image-file", ANCHOR,
         "--last-image-file", ANCHOR, "--style-mode", "hd",
         "--resolution", "720p", "--output-frames", "32",
         "--quality-mode", "medium", "--alpha-mode", "soft",
         "--remove-bg-method", "standard", "--no-optimize-prompt",
         "--prompt", PROMPT],
        capture_output=True, text=True, timeout=900)
    ok = '"status": "success"' in r.stdout
    print("gen:", "OK" if ok else "FAIL")
    if not ok:
        print(r.stdout[-400:])
        sys.exit(1)
    src = sorted(glob.glob(os.path.join(out, "*", "meowa_animation.webp")),
                 key=os.path.getmtime)[-1]
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    print("frames", n)
    if n != 32:
        sys.exit(f"expect 32 frames, got {n}")
    frames_dir = os.path.join(out, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    edges = []
    for i in range(n):
        im.seek(i)
        fr = im.convert("RGBA")
        fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
        al = np.array(fr)[:, :, 3]
        ys, xs = np.where(al > 50)
        edges.append((int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))
    touches = sum(1 for x0, x1, y0, y1 in edges
                  if x0 <= 2 or x1 >= 957 or y0 <= 2 or y1 >= 957)
    print(f"edge-touch={touches}/32 bbox x{min(e[0] for e in edges)}-"
          f"{max(e[1] for e in edges)} y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}")

    base = os.path.join(RUNTIME, "ice_cream", "desktop_new", "animations")
    for name, (a, b) in (("sleep_fall", (0, 7)), ("sleep_loop", (8, 23)),
                         ("sleep_wake", (24, 31))):
        dst = os.path.join(base, name)
        os.makedirs(dst, exist_ok=True)
        for old in os.listdir(dst):
            if old.endswith(".png"):
                os.remove(os.path.join(dst, old))
        for i in range(a, b + 1):
            shutil.copyfile(os.path.join(frames_dir, f"{i:03d}.png"),
                            os.path.join(dst, f"{i - a:03d}.png"))
        print(name, b - a + 1, "frames")

    mpath = os.path.join(base, "manifest.json")
    with open(mpath, encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["sleep_fall"] = {"folder": "sleep_fall", "fps": 8, "loop": False,
                              "fallback": "idle", "scale": SCALE,
                              "anchor_bottom": False, "saturation": 1.0,
                              "brightness": 1.0, "frame_durations_ms": [125] * 8}
    manifest["sleep_loop"] = {"folder": "sleep_loop", "fps": 8, "loop": True,
                              "fallback": "idle", "scale": SCALE,
                              "anchor_bottom": False, "saturation": 1.0,
                              "brightness": 1.0, "frame_durations_ms": [125] * 16}
    manifest["sleep_wake"] = {"folder": "sleep_wake", "fps": 8, "loop": False,
                              "fallback": "idle", "scale": SCALE,
                              "anchor_bottom": False, "saturation": 1.0,
                              "brightness": 1.0, "frame_durations_ms": [125] * 8}
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("manifest keys:", sorted(manifest))

    tiles = []
    for i in range(n):
        fr = Image.open(os.path.join(frames_dir, f"{i:03d}.png"))
        fr.thumbnail((230, 230), Image.LANCZOS)
        tile = Image.new("RGB", (240, 270), (250, 244, 235))
        tile.paste(fr, ((240 - fr.width) // 2, 8), fr)
        ImageDraw.Draw(tile).text((8, 244), str(i), fill=(120, 70, 40))
        tiles.append(tile)
    sheet = Image.new("RGB", (240 * 8, 270 * 4), (250, 244, 235))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 8) * 240, (i // 8) * 270))
    sheet.save(os.path.join(out, "audit_sheet.jpg"), quality=88)
    concat = os.path.join(out, "concat.txt")
    with open(concat, "w") as f:
        for _ in range(2):
            for i in range(n):
                f.write("file " + os.path.abspath(
                    os.path.join(frames_dir, f"{i:03d}.png")).replace("\\", "/") + "\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                    "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    os.path.join(out, "preview.mp4")], capture_output=True)
    os.remove(concat)
    print("ICE SLEEP DONE")


if __name__ == "__main__":
    main()
