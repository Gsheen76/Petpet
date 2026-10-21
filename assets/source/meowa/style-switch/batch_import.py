"""批产导入:14 条动画拆帧→QC(帧数/底线/内容)→runtime desktop_new→manifest→审计图/MP4。"""
import glob
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
BASE = os.path.join(ROOT, "assets", "source", "meowa", "style-switch")
RUNTIME = os.path.join(ROOT, "assets", "runtime", "pets")

SCALE = {"lunch_meat": 0.9366, "ice_cream": 0.8816}
LOOP_TRUE = {"sleep", "walk"}
DURATIONS = [125] * 16


def outdir(pet, action):
    return os.path.join(BASE, pet, f"{action}_v1")


def process(pet, action):
    src = glob.glob(os.path.join(outdir(pet, action), "*", "meowa_animation.webp"))
    if not src:
        return f"{pet}/{action}: NO WEBP"
    im = Image.open(src[0])
    n = getattr(im, "n_frames", 1)
    if n != 16:
        return f"{pet}/{action}: frame count {n} != 16"
    frames_dir = os.path.join(outdir(pet, action), "frames")
    os.makedirs(frames_dir, exist_ok=True)
    stats = []
    for i in range(n):
        im.seek(i)
        fr = im.convert("RGBA")
        fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
        a = np.array(fr)[:, :, 3]
        ys, xs = np.where(a > 50)
        stats.append((ys.max(), xs.min(), xs.max()) if len(ys) else (-1, -1, -1))

    dst = os.path.join(RUNTIME, pet, "desktop_new", "animations", action)
    os.makedirs(dst, exist_ok=True)
    for i in range(n):
        with open(os.path.join(frames_dir, f"{i:03d}.png"), "rb") as fh:
            with open(os.path.join(dst, f"{i:03d}.png"), "wb") as out:
                out.write(fh.read())

    # 审计图 + MP4(两循环 8fps)
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
    sheet.save(os.path.join(outdir(pet, action), "audit_sheet.jpg"), quality=88)
    concat = os.path.join(outdir(pet, action), "concat.txt")
    with open(concat, "w") as f:
        for _ in range(2):
            for i in range(n):
                f.write("file " + os.path.join(frames_dir, f"{i:03d}.png").replace("\\", "/") + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8", "-i", concat,
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
         os.path.join(outdir(pet, action), "preview.mp4")],
        capture_output=True)
    os.remove(concat)

    bots = [s[0] for s in stats]
    return (f"{pet}/{action}: OK bottom {min(bots)}-{max(bots)} "
            f"left {min(s[1] for s in stats)}-{max(s[1] for s in stats)} "
            f"right {min(s[2] for s in stats)}-{max(s[2] for s in stats)}")


def write_manifests():
    for pet, scale in SCALE.items():
        path = os.path.join(RUNTIME, pet, "desktop_new", "animations", "manifest.json")
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        for action in os.listdir(os.path.join(RUNTIME, pet, "desktop_new", "animations")):
            d = os.path.join(RUNTIME, pet, "desktop_new", "animations", action)
            if not os.path.isdir(d) or action == "idle":
                continue
            frames = [f for f in os.listdir(d) if f.endswith(".png")]
            if len(frames) != 16:
                continue
            manifest[action] = {
                "folder": action,
                "fps": 8,
                "loop": action in LOOP_TRUE,
                "fallback": "idle",
                "scale": scale,
                "anchor_bottom": False,
                "saturation": 1.0,
                "brightness": 1.0,
                "frame_durations_ms": DURATIONS,
            }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"manifest {pet}: keys={sorted(manifest)}")


if __name__ == "__main__":
    for pet, spec in (("lunch_meat", None), ("ice_cream", None)):
        actions = ["pet", "eat", "play", "happy", "dig_reward", "drag"]
        if pet == "lunch_meat":
            actions += ["sleep", "walk"]
        for action in actions:
            print(process(pet, action), flush=True)
    write_manifests()
    print("IMPORT DONE")
