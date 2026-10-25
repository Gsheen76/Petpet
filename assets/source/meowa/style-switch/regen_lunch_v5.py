"""午餐肉 v5 两动作:①进食重做(真吃:碗+张嘴咬+咀嚼,上版被指没吃东西)
②睡觉加长 32 帧保留长睡眠平台段(用户后续分割循环)。
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
RUNTIME = os.path.join("assets", "runtime", "pets")
ANCHOR = os.path.join(BASE, "lunch_meat", "anchor_v3b.png")

COMMON = (
    " Keep the exact same character, colors, watercolor storybook art "
    "style and facing direction as the reference image in every frame. "
    "The whole action stays fully inside the canvas with generous empty "
    "space around the character - nothing is ever cut off by the canvas "
    "edge. Plain transparent background, no ground shadow, no extra "
    "objects, no text, no human hands."
)
NECK = (" The red plaid collar with a small round golden tag stays around "
        "the puppy's neck in every frame.")

EAT = (
    "A clearly visible eating animation: a small cream food bowl sits "
    "directly in front of the sitting puppy's front paws on the ground. "
    "The puppy lowers its head all the way down into the bowl, opens its "
    "mouth and takes real bites of food, then lifts its head slightly "
    "and chews with clear jaw movement, then dips its head down into the "
    "bowl again for the next bite - three visible bite-and-chew cycles, "
    "tail wagging happily throughout, ending with head up and a satisfied "
    "smile with tiny crumbs on its muzzle."
)
SLEEP = (
    "A long cozy sleep cycle: (1) the puppy curls down into a round "
    "fluffy ball beside its sitting spot, tail wrapping over its nose; "
    "(2) then it stays asleep in this curled ball for a LONG middle "
    "section - only the body gently rising and falling in slow breathing, "
    "one ear twitching occasionally; hold this sleeping ball pose for "
    "most of the animation; (3) finally it stretches and uncurls back to "
    "the same sitting pose. The mouth stays gently closed."
)


def run(cmd):
    return subprocess.run([sys.executable, API] + cmd,
                          capture_output=True, text=True, timeout=900)


def gen(action, frames, prompt):
    out = os.path.join(BASE, "lunch_meat", f"{action}_v5")
    r = run(["meowa-animation-run", "--output-dir", out,
             "--image-file", ANCHOR, "--last-image-file", ANCHOR,
             "--style-mode", "hd", "--resolution", "720p",
             "--output-frames", str(frames), "--quality-mode", "medium",
             "--alpha-mode", "soft", "--remove-bg-method", "standard",
             "--no-optimize-prompt",
             "--prompt", prompt + NECK + COMMON])
    ok = '"status": "success"' in r.stdout
    print(f"[{'OK' if ok else 'FAIL'}] {action}", flush=True)
    if not ok:
        print(r.stdout[-300:], flush=True)
    return ok


def import_action(action, durations):
    src = sorted(glob.glob(os.path.join(
        BASE, "lunch_meat", f"{action}_v5", "*", "meowa_animation.webp")),
        key=os.path.getmtime)[-1]
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    print(f"[{action}] frames={n}", flush=True)
    frames_dir = os.path.join(BASE, "lunch_meat", f"{action}_v5", "frames")
    os.makedirs(frames_dir, exist_ok=True)
    dst = os.path.join(RUNTIME, "lunch_meat", "desktop_new", "animations", action)
    os.makedirs(dst, exist_ok=True)
    # 清旧帧(帧数可能不同)
    for old in os.listdir(dst):
        if old.endswith(".png"):
            os.remove(os.path.join(dst, old))
    edges = []
    for i in range(n):
        im.seek(i)
        fr = im.convert("RGBA")
        fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
        with open(os.path.join(frames_dir, f"{i:03d}.png"), "rb") as fh:
            data = fh.read()
        with open(os.path.join(dst, f"{i:03d}.png"), "wb") as fo:
            fo.write(data)
        al = np.array(fr)[:, :, 3]
        ys, xs = np.where(al > 50)
        edges.append((int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))
    touches = sum(1 for x0, x1, y0, y1 in edges
                  if x0 <= 2 or x1 >= 957 or y0 <= 2 or y1 >= 957)
    tiles = []
    for i in range(n):
        fr = Image.open(os.path.join(frames_dir, f"{i:03d}.png"))
        fr.thumbnail((230, 230), Image.LANCZOS)
        tile = Image.new("RGB", (240, 270), (250, 244, 235))
        tile.paste(fr, ((240 - fr.width) // 2, 8), fr)
        ImageDraw.Draw(tile).text((8, 244), str(i), fill=(120, 70, 40))
        tiles.append(tile)
    sheet = Image.new("RGB", (240 * ((n + 3) // 4), 270 * 4), (250, 244, 235))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % ((n + 3) // 4)) * 240, (i // ((n + 3) // 4)) * 270))
    sheet.save(os.path.join(BASE, "lunch_meat", f"{action}_v5", "audit_sheet.jpg"), quality=88)
    concat = os.path.join(BASE, "lunch_meat", f"{action}_v5", "concat.txt")
    with open(concat, "w") as f:
        for _ in range(2):
            for i in range(n):
                f.write("file " + os.path.abspath(
                    os.path.join(frames_dir, f"{i:03d}.png")).replace("\\", "/") + "\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                    "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    os.path.join(BASE, "lunch_meat", f"{action}_v5", "preview.mp4")],
                   capture_output=True)
    os.remove(concat)
    print(f"[IMPORT] {action} edge-touch={touches}/{n} "
          f"bbox x{min(e[0] for e in edges)}-{max(e[1] for e in edges)} "
          f"y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}", flush=True)
    return n


if __name__ == "__main__":
    if not gen("eat", 16, EAT):
        sys.exit("eat failed")
    if not gen("sleep", 32, SLEEP):
        sys.exit("sleep failed")
    n_eat = import_action("eat", [125] * 16)
    n_sleep = import_action("sleep", [125] * 32)
    mpath = os.path.join(RUNTIME, "lunch_meat", "desktop_new", "animations", "manifest.json")
    with open(mpath, encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["eat"]["frame_durations_ms"] = [125] * n_eat
    manifest["sleep"]["frame_durations_ms"] = [125] * n_sleep
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("V5 DONE", flush=True)
