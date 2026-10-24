"""午餐肉 v4 四动作重做:pet/eat/sleep 重做 + drag 制作。
锚=anchor_v3b(62% 留白);项圈/闭嘴/防出框条款全套;导入+QC+审计/MP4。
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
DURATIONS = [125] * 16

COMMON = (
    " Keep the exact same character, colors, watercolor storybook art "
    "style and facing direction as the reference image in every frame. "
    "The whole action stays fully inside the canvas with generous empty "
    "space around the character - nothing is ever cut off by the canvas "
    "edge. Plain transparent background, no added ground shadow, no "
    "extra objects, no text, no human hands."
)
NECK = (" The red plaid collar with a small round golden tag stays around "
        "the puppy's neck in every frame.")
CLOSED = " The mouth stays gently closed in a soft smile."

ACTIONS = {
    "pet": (
        "A blissful head-pat moment: the sitting puppy tilts its head up "
        "and pushes gently into an invisible palm above its head, one ear "
        "flopping over, eyes closing in contentment, tail thumping happily "
        "against the ground, then settles back to the same sitting pose."
        + CLOSED),
    "eat": (
        "A happy meal moment: the sitting puppy leans down to a small "
        "cream food bowl right in front of its paws and eats in a steady "
        "rhythm - head bobbing down for bites and up to chew, tail "
        "wagging steadily, tiny happy paw stomps, then lifts its head and "
        "swallows with a satisfied smile."),
    "sleep": (
        "A cozy curl-up nap: the puppy curls into a round fluffy ball "
        "beside its sitting spot, tail wrapped over its nose, breathing "
        "in a slow gentle rise-and-fall loop, one ear twitching softly, "
        "then stretches and uncurls back to the same sitting pose."
        + CLOSED),
    "drag": (
        "A lifted-and-dangling moment: the puppy is held up in the air by "
        "an unseen gentle grip - body hanging with all four legs waving "
        "and kicking in small cute motions, swaying gently left and "
        "right, wide curious eyes looking around, calm and trusting."
        + CLOSED),
}


def run(cmd):
    return subprocess.run([sys.executable, API] + cmd,
                          capture_output=True, text=True, timeout=900)


def gen(action):
    out = os.path.join(BASE, "lunch_meat", f"{action}_v4")
    r = run(["meowa-animation-run", "--output-dir", out,
             "--image-file", ANCHOR, "--last-image-file", ANCHOR,
             "--style-mode", "hd", "--resolution", "720p",
             "--output-frames", "16", "--quality-mode", "medium",
             "--alpha-mode", "soft", "--remove-bg-method", "standard",
             "--no-optimize-prompt",
             "--prompt", ACTIONS[action] + NECK + COMMON])
    ok = '"status": "success"' in r.stdout
    print(f"[{'OK' if ok else 'FAIL'}] lunch/{action}", flush=True)
    if not ok:
        print(r.stdout[-300:], flush=True)
    return ok


def import_action(action, scale):
    src = sorted(glob.glob(os.path.join(
        BASE, "lunch_meat", f"{action}_v4", "*", "meowa_animation.webp")),
        key=os.path.getmtime)[-1]
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    if n != 16:
        print(f"[SKIP] {action} frames={n}", flush=True)
        return
    frames_dir = os.path.join(BASE, "lunch_meat", f"{action}_v4", "frames")
    os.makedirs(frames_dir, exist_ok=True)
    dst = os.path.join(RUNTIME, "lunch_meat", "desktop_new", "animations", action)
    os.makedirs(dst, exist_ok=True)
    edges = []
    for i in range(n):
        im.seek(i)
        fr = im.convert("RGBA")
        fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
        with open(os.path.join(frames_dir, f"{i:03d}.png"), "rb") as fh:
            data = fh.read()
        with open(os.path.join(dst, f"{i:03d}.png"), "wb") as fo:
            fo.write(data)
        a = np.array(fr)[:, :, 3]
        ys, xs = np.where(a > 50)
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
    sheet = Image.new("RGB", (960, 1080), (250, 244, 235))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 4) * 240, (i // 4) * 270))
    sheet.save(os.path.join(BASE, "lunch_meat", f"{action}_v4", "audit_sheet.jpg"), quality=88)
    concat = os.path.join(BASE, "lunch_meat", f"{action}_v4", "concat.txt")
    with open(concat, "w") as f:
        for _ in range(2):
            for i in range(n):
                f.write("file " + os.path.abspath(
                    os.path.join(frames_dir, f"{i:03d}.png")).replace("\\", "/") + "\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                    "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    os.path.join(BASE, "lunch_meat", f"{action}_v4", "preview.mp4")],
                   capture_output=True)
    os.remove(concat)
    print(f"[IMPORT] lunch/{action} edge-touch={touches}/16 "
          f"bbox x{min(e[0] for e in edges)}-{max(e[1] for e in edges)} "
          f"y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}", flush=True)


if __name__ == "__main__":
    for action in ("pet", "eat", "sleep", "drag"):
        if not gen(action):
            sys.exit(f"gen failed {action}")
    # scale 沿用现行 manifest(lunch 0.9377/或最新)——读回保持一致
    mpath = os.path.join(RUNTIME, "lunch_meat", "desktop_new", "animations", "manifest.json")
    with open(mpath, encoding="utf-8") as fh:
        manifest = json.load(fh)
    scale = manifest.get("idle", {}).get("scale", 1.0)
    for action in ("pet", "eat", "sleep", "drag"):
        import_action(action, scale)
    # manifest 键已有,不动
    print("V4 DONE", flush=True)
