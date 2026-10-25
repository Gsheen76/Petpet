"""冰淇淋 v2 四动作重做:pet/eat/dig_reward/drag——软糯甜妹独特设计。"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
RUNTIME = os.path.join("assets", "runtime", "pets")
ANCHOR = os.path.join(BASE, "ice_cream", "anchor_v3b.png")

COMMON = (
    " Keep the exact same character, colors, watercolor storybook art "
    "style and facing direction as the reference image in every frame. "
    "The whole action stays fully inside the canvas with generous empty "
    "space around the character - nothing is ever cut off by the canvas "
    "edge. Plain transparent background, no ground shadow, no extra "
    "objects, no text, no human hands."
)
NECK = " The small green neck scarf stays on in every frame."
CLOSED = " The mouth stays gently closed in a soft smile."

ACTIONS = {
    "pet": (
        "A melting-into-the-touch moment, slow and gentle: as an unseen "
        "hand pats its head, the puppy's ears slowly go soft and floppy, "
        "its head tilts gently sideways leaning into the touch, cheek "
        "nestling blissfully, eyes closing with a content little sigh, "
        "tail tip swaying in tiny sweet sweeps, then slowly returns to "
        "the same sitting pose." + CLOSED),
    "eat": (
        "A dainty tasting ritual in three beats: the puppy first taps "
        "the small cream food bowl in front of it softly with one front "
        "paw (a curious little test), then lowers its head and takes one "
        "small delicate bite, chewing slowly with eyes closed savoring "
        "the flavor, then takes a second bite, finally lifts its head, "
        "licks its lips and squints in sweet contentment."),
    "dig_reward": (
        "A treasure-wish discovery, soft and dreamy: the puppy paws the "
        "ground gently twice, then gasps softly with round surprised "
        "eyes and brings both front paws to its cheeks, then carefully "
        "cradles a tiny glowing treasure against its chest, eyes "
        "squinting warmly as if making a quiet wish over it." + CLOSED),
    "drag": (
        "An aerial cradle ride, calm and dreamy: held up in the air by "
        "an unseen gentle grip, the puppy hangs with all four legs "
        "relaxed and dangling, swaying very slowly like rocking in a "
        "tiny swing, long ears floating like soft ribbons, eyes gently "
        "closed enjoying the ride with a peaceful smile." + CLOSED),
}


def run(cmd):
    return subprocess.run([sys.executable, API] + cmd,
                          capture_output=True, text=True, timeout=900)


def gen(action):
    out = os.path.join(BASE, "ice_cream", f"{action}_v2")
    r = run(["meowa-animation-run", "--output-dir", out,
             "--image-file", ANCHOR, "--last-image-file", ANCHOR,
             "--style-mode", "hd", "--resolution", "720p",
             "--output-frames", "16", "--quality-mode", "medium",
             "--alpha-mode", "soft", "--remove-bg-method", "standard",
             "--no-optimize-prompt",
             "--prompt", ACTIONS[action] + NECK + COMMON])
    ok = '"status": "success"' in r.stdout
    print(f"[{'OK' if ok else 'FAIL'}] {action}", flush=True)
    if not ok:
        print(r.stdout[-300:], flush=True)
    return ok


def import_action(action):
    src = sorted(glob.glob(os.path.join(
        BASE, "ice_cream", f"{action}_v2", "*", "meowa_animation.webp")),
        key=os.path.getmtime)[-1]
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    if n != 16:
        print(f"[SKIP] {action} frames={n}", flush=True)
        return
    frames_dir = os.path.join(BASE, "ice_cream", f"{action}_v2", "frames")
    os.makedirs(frames_dir, exist_ok=True)
    dst = os.path.join(RUNTIME, "ice_cream", "desktop_new", "animations", action)
    os.makedirs(dst, exist_ok=True)
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
    sheet = Image.new("RGB", (960, 1080), (250, 244, 235))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 4) * 240, (i // 4) * 270))
    sheet.save(os.path.join(BASE, "ice_cream", f"{action}_v2", "audit_sheet.jpg"),
               quality=88)
    concat = os.path.join(BASE, "ice_cream", f"{action}_v2", "concat.txt")
    with open(concat, "w") as f:
        for _ in range(2):
            for i in range(n):
                f.write("file " + os.path.abspath(
                    os.path.join(frames_dir, f"{i:03d}.png")).replace("\\", "/") + "\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                    "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    os.path.join(BASE, "ice_cream", f"{action}_v2", "preview.mp4")],
                   capture_output=True)
    os.remove(concat)
    print(f"[IMPORT] {action} edge-touch={touches}/16 "
          f"bbox x{min(e[0] for e in edges)}-{max(e[1] for e in edges)} "
          f"y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}", flush=True)


if __name__ == "__main__":
    for action in ("pet", "eat", "dig_reward", "drag"):
        if not gen(action):
            sys.exit(f"gen failed {action}")
    for action in ("pet", "eat", "dig_reward", "drag"):
        import_action(action)
    print("ICE V2 DONE", flush=True)
