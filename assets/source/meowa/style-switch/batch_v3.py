"""风格切换 v3:留白根治+性格化设计批。
画布:定妆照 v2 内容压到 62%(高约 600/1024),底留白 130/顶 290/侧 300+——
弹跳摆动不再出框;16 条全量重做,动作语言按宠物性格分化(设计表已交用户)。
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
BASE = os.path.join(ROOT, "assets", "source", "meowa", "style-switch")
RUNTIME = os.path.join(ROOT, "assets", "runtime", "pets")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"

LOOP_TRUE = {"sleep", "walk"}
DURATIONS = [125] * 16

COMMON = (
    "Keep the exact same character, colors, watercolor storybook art style "
    "and facing direction as the reference image in every frame. The whole "
    "action stays fully inside the canvas with generous empty space around "
    "the character - nothing is ever cut off by the canvas edge. Plain "
    "transparent background, no added ground shadow, no extra objects, "
    "no text, no human hands."
)
CLOSED = " The mouth stays gently closed in a soft smile."
SCARF = " The small green neck scarf stays on in every frame."

IDLE = (
    "A gentle idle loop animation of this sitting puppy. The body, torso, "
    "head and all four paws stay locked in one fixed position like a "
    "photograph. Only two subtle motions: the tail sways softly side to "
    "side, and the puppy blinks briefly once in the middle of the loop."
    + CLOSED
)

# 性格化动作设计(2026-10-22 用户令:按性格设计,拒绝流水线)
ACTIONS = {
    "lunch_meat": {
        "pet": "An energetic affectionate head-bump: the sitting puppy actively pushes the top of its head into an invisible palm, ears flying back, tail whirling like a propeller, eyes squeezed happy, then springs back to the same sitting pose." + CLOSED,
        "eat": "A hungry little foodie moment: the puppy pounces its head into a cream food bowl that appears in front, munching fast and eagerly, nudging the bowl forward slightly, then lifts its head with a crumb on its muzzle and a deeply satisfied grin.",
        "play": "A playful triple bounce: the puppy lowers into a sprinter crouch, then hops in place three quick bounces with ears flapping up and down, landing in a wiggly penguin-step shuffle, then back to the same sitting pose." + CLOSED,
        "happy": "A joyful body-wiggle dance: quick tiny steps in place, hips shimmying side to side, head swinging left and right, tail spinning circles, mouth open in a big happy grin.",
        "dig_reward": "A digging-machine burst: front paws alternate scratching the ground rapidly, then the puppy freezes with huge sparkling star eyes at what it found, sits up tall and proud with chest puffed." + CLOSED,
        "drag": "An airborne runner: held suspended by an unseen gentle grip, the puppy pedals all four legs in the air like running, body tilting side to side, thrilled flying expression." + CLOSED,
        "sleep": "A tumbled-out nap: the playful puppy flops onto its back with all four paws in the air, belly rising and falling in snoozy breaths, one paw twitching from a dream, then rolls back over and returns to the same sitting pose." + CLOSED,
        "walk": "A proud light trot: head held high, tail up, cheerful quick little steps in place, ears bouncing with each step." + CLOSED,
    },
    "ice_cream": {
        "pet": "A shy gentle nuzzle: the puppy slowly leans its head sideways into an invisible palm, eyes closing contentedly, ear tips drooping softly, tail tip swaying in tiny slow sweeps, then returns to the same sitting pose." + CLOSED,
        "eat": "A dainty little eater: the puppy lowers its head, takes one small delicate bite from a cream food bowl, chews slowly and carefully, then licks its lips and squints in quiet contentment.",
        "play": "A classic play bow: the puppy stretches its front paws low and forward in an invitation-to-play bow with bottom up, does one soft little hop, tail wagging in slow elegant sweeps, then sits back down." + CLOSED,
        "happy": "A sweet head tilt: the puppy tilts its head to one side with softly squinting eyes and a warm shy smile, ears going gently floppy, tail drawing slow happy circles, then returns to the same sitting pose." + CLOSED,
        "dig_reward": "A curious gentle discovery: the puppy paws the ground softly twice, looks surprised with round wide eyes and paws at its own mouth, then carefully holds a tiny treasure against its chest and admires it." + CLOSED,
        "drag": "A calm floating ride: held suspended by an unseen gentle grip, the puppy hangs with relaxed dangling legs swaying very gently, ears drifting like a slow swing ride, serene trusting smile." + CLOSED,
    },
}


def run(cmd):
    return subprocess.run([sys.executable, API] + cmd,
                          capture_output=True, text=True, timeout=900)


def pad_anchor(pet):
    src = glob.glob(os.path.join(BASE, pet, "stills_v2", "*", "result_images_0_url.png"))[0]
    im = Image.open(src).convert("RGBA")
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 40)
    content = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    scale = 600 / content.height
    cw, ch = int(content.width * scale), 600
    content = content.resize((cw, ch), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.paste(content, ((1024 - cw) // 2, 1024 - 130 - ch), content)
    out = os.path.join(BASE, pet, "anchor_v3.png")
    canvas.save(out)
    print(f"[ANCHOR] {pet} content {cw}x{ch} bottom 130 top {1024-130-ch} sides {(1024-cw)//2}", flush=True)
    return out


def gen(pet, action, anchor):
    out = os.path.join(BASE, pet, f"{action}_v3")
    prompt = IDLE if action == "idle" else ACTIONS[pet][action]
    if pet == "ice_cream":
        prompt += SCARF
    result = run([
        "meowa-animation-run", "--output-dir", out,
        "--image-file", anchor, "--last-image-file", anchor,
        "--style-mode", "hd", "--resolution", "720p",
        "--output-frames", "16", "--quality-mode", "medium",
        "--alpha-mode", "soft", "--remove-bg-method", "standard",
        "--no-optimize-prompt", "--prompt", prompt + " " + COMMON,
    ])
    ok = '"status": "success"' in result.stdout
    print(f"[{'OK' if ok else 'FAIL'}] {pet}/{action}", flush=True)
    if not ok:
        print(result.stdout[-400:], flush=True)
    return ok


def body_stats(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 50)
    return im.size, ys.max() - ys.min() + 1


def import_all():
    scales = {}
    for pet in ("lunch_meat", "ice_cream"):
        classic = sorted(glob.glob(
            os.path.join(RUNTIME, pet, "desktop", "animations", "idle", "*.png")))[0]
        c_size, c_h = body_stats(classic)
        new = os.path.join(BASE, pet, "idle_v3", "frames", "000.png")
        n_size, n_h = body_stats(new)
        scales[pet] = round((c_h / c_size[1]) / (n_h / n_size[1]), 4)
        print(f"[SCALE] {pet} {scales[pet]}", flush=True)

    for pet in ("lunch_meat", "ice_cream"):
        actions = ["idle", "pet", "eat", "play", "happy", "dig_reward", "drag"]
        if pet == "lunch_meat":
            actions += ["sleep", "walk"]
        for action in actions:
            src = glob.glob(os.path.join(BASE, pet, f"{action}_v3", "*", "meowa_animation.webp"))
            if not src:
                print(f"[MISS] {pet}/{action}", flush=True)
                continue
            im = Image.open(src[0])
            n = getattr(im, "n_frames", 1)
            if n != 16:
                print(f"[SKIP] {pet}/{action} frames={n}", flush=True)
                continue
            frames_dir = os.path.join(BASE, pet, f"{action}_v3", "frames")
            os.makedirs(frames_dir, exist_ok=True)
            dst = os.path.join(RUNTIME, pet, "desktop_new", "animations", action)
            os.makedirs(dst, exist_ok=True)
            edges = []
            for i in range(n):
                im.seek(i)
                fr = im.convert("RGBA")
                fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
                with open(os.path.join(frames_dir, f"{i:03d}.png"), "rb") as fh:
                    data = fh.read()
                with open(os.path.join(dst, f"{i:03d}.png"), "wb") as out:
                    out.write(data)
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
            sheet.save(os.path.join(BASE, pet, f"{action}_v3", "audit_sheet.jpg"), quality=88)
            concat = os.path.join(BASE, pet, f"{action}_v3", "concat.txt")
            with open(concat, "w") as f:
                for _ in range(2):
                    for i in range(n):
                        f.write("file " + os.path.join(frames_dir, f"{i:03d}.png").replace("\\", "/") + "\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                 "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                 os.path.join(BASE, pet, f"{action}_v3", "preview.mp4")],
                capture_output=True)
            os.remove(concat)
            print(f"[IMPORT] {pet}/{action} edge-touch frames={touches}/16 "
                  f"bbox x{min(e[0] for e in edges)}-{max(e[1] for e in edges)} "
                  f"y{min(e[2] for e in edges)}-{max(e[3] for e in edges)}", flush=True)

        pose_src = os.path.join(BASE, pet, "idle_v3", "frames", "000.png")
        if os.path.isfile(pose_src):
            with open(pose_src, "rb") as fh:
                data = fh.read()
            with open(os.path.join(RUNTIME, pet, "desktop_new", "poses", "idle.png"), "wb") as out:
                out.write(data)

        path = os.path.join(RUNTIME, pet, "desktop_new", "animations", "manifest.json")
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        for key, spec in manifest.items():
            if isinstance(spec, dict):
                spec["scale"] = scales[pet]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"[MANIFEST] {pet} scale={scales[pet]}", flush=True)


if __name__ == "__main__":
    for pet in ("lunch_meat", "ice_cream"):
        anchor = pad_anchor(pet)
        if not gen(pet, "idle", anchor):
            sys.exit(f"idle failed {pet}")
        idle_frame = os.path.join(BASE, pet, "idle_v3", "frames", "000.png")
        os.makedirs(os.path.dirname(idle_frame), exist_ok=True)
        src = glob.glob(os.path.join(BASE, pet, "idle_v3", "*", "meowa_animation.webp"))[0]
        Image.open(src).convert("RGBA").save(idle_frame)
        for action in ACTIONS[pet]:
            gen(pet, action, idle_frame)
    import_all()
    print("V3 BATCH DONE", flush=True)
