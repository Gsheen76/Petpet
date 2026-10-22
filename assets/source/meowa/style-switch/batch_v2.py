"""风格切换 v2 修正批:①双犬定妆照重生成(冰淇淋点名绿丝巾/双嘴闭)
②以新定妆照为锚重做双犬全部 16 条动画(idle 先行,动作锚 idle 首帧)
③导入 runtime+标定 scale+manifest+审计图/MP4。
修正在案问题:idle 嘴巴常张(呆)、冰淇淋绿丝巾未保持。
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
    "and facing direction as the reference image in every frame. Plain "
    "transparent background, no added ground shadow, no extra objects, "
    "no text, no human hands."
)
CLOSED_MOUTH = (
    " The mouth stays gently closed in a soft relaxed smile - never open, "
    "no tongue visible, except where the action naturally requires it "
    "(such as eating)."
)

STILL_PROMPTS = {
    "lunch_meat": (
        "Full-body side-view character art of the same puppy as in the first "
        "reference image: an orange-brown shiba-like puppy with cream muzzle "
        "and chest, white brow dots above the eyes, dark round eyes. Keep "
        "exactly the same identity, colors and soft watercolor storybook art "
        "style as the first reference. The puppy sits in the same sitting "
        "pose and same facing direction as the puppy in the second reference "
        "image. The mouth is gently closed in a soft relaxed smile. Single "
        "character only, complete body with all four paws fully visible "
        "resting on the ground, tail visible, generous empty margins around "
        "the character, plain transparent background, no frame, no border, "
        "no decorations, no text, matte soft colors."
    ),
    "ice_cream": (
        "Full-body side-view character art of the same puppy as in the first "
        "reference image: a soft cream-apricot puppy with deeper golden-brown "
        "ears, pale milk-white muzzle and chest, gentle dark round eyes. The "
        "puppy wears a small soft green scarf tied around its neck, exactly "
        "like the green neck scarf seen on the puppy in the second reference "
        "image - keep this green scarf clearly visible on the chest. Keep "
        "exactly the same identity, colors and soft watercolor storybook art "
        "style as the first reference. The puppy sits in the same sitting "
        "pose and same facing direction as the puppy in the second reference "
        "image. The mouth is gently closed in a soft relaxed smile. Single "
        "character only, complete body with all four paws fully visible "
        "resting on the ground, fluffy curled tail visible, generous empty "
        "margins around the character, plain transparent background, no "
        "frame, no border, no decorations, no text, matte soft colors."
    ),
}

IDLE_MOTION = (
    "A gentle idle loop animation of this sitting puppy. The body, torso, "
    "head and all four paws stay locked in one fixed position like a "
    "photograph - zero body movement, no bouncing, no drifting, no shifting. "
    "Only two subtle motions: the tail sways softly side to side, and the "
    "puppy blinks its eyes briefly once in the middle of the loop."
)

ACTIONS = {
    "lunch_meat": {
        "pet": "A short gentle petting interaction with an invisible touch: the sitting puppy leans slightly into the touch, eyes closing contentedly, tail wagging softly, then returns to the same sitting pose. Head and body stay low-motion.",
        "eat": "The sitting puppy lowers its head to eat from a small cream-colored food bowl that appears in front of it, chews gently several times, then lifts its head back up to the same sitting pose.",
        "play": "A playful bounce in place: from the same sitting pose the puppy does two small happy hops with ears flapping and tail spinning, then settles back to the same sitting pose.",
        "happy": "An excited happy wiggle: the sitting puppy tilts its head side to side, ears bouncing, tail wagging fast, then returns to the same sitting pose.",
        "dig_reward": "The sitting puppy reaches forward and scratches the ground lightly with front paws a few times, then sits back up with sparkling excited eyes and a proud smile.",
        "drag": "The puppy is held suspended in the air by an unseen gentle grip: body hanging with legs dangling, swaying slightly left and right, calm trusting expression. Same framing, character stays centered.",
        "sleep": "The puppy curls into a soft sleeping ball beside its sitting spot, closes its eyes and breathes in a slow gentle loop, then uncurls back to the same sitting pose.",
        "walk": "A natural side-view dog walk in place: four legs alternating in a calm trot while staying centered in frame, head steady, then stops back at the same sitting pose.",
    },
    "ice_cream": {
        "pet": "A soft tender moment with an invisible touch: the sitting puppy leans gently into the touch with a shy sweet smile, eyes half closing, tail swaying slowly, then returns to the same sitting pose. Slow calm motion.",
        "eat": "The sitting puppy lowers its head to eat from a small cream-colored food bowl that appears in front of it, chews slowly and delicately, then lifts its head back with a content smile.",
        "play": "A gentle playful invitation: from the same sitting pose the puppy does one soft little hop with front paws lowered in a play bow, tail wagging sweetly, then returns to sitting.",
        "happy": "A quiet happy moment: the sitting puppy does a small sweet head tilt with soft squinting eyes and a slow tail wag, like a warm smile, then returns to the same sitting pose.",
        "dig_reward": "The sitting puppy paws the ground softly a couple of times, then looks up with round sparkling gentle eyes and a small proud smile.",
        "drag": "The puppy is held suspended in the air by an unseen gentle grip: body hanging with legs dangling, swaying very slightly, calm and trusting. Same framing, character stays centered.",
    },
}

KEEP_SCARF = (
    " The small green neck scarf stays on in every frame."
)


def run(cmd, timeout=900):
    return subprocess.run([sys.executable, API] + cmd,
                          capture_output=True, text=True, timeout=timeout)


def gen_still(pet):
    out = os.path.join(BASE, pet, "stills_v2")
    result = run([
        "image-2.5-run", "--output-dir", out, "--quality", "detailed",
        "--resolution", "1K", "--remove-bg-method", "standard",
        "--reference-image", os.path.join(RUNTIME, pet, "avatar.png"),
        "--reference-image", os.path.join(BASE, pet, "ref_idle_classic.png"),
        "--prompt", STILL_PROMPTS[pet],
    ])
    ok = '"status": "success"' in result.stdout
    print(f"[{'OK' if ok else 'FAIL'}] still {pet}", flush=True)
    if not ok:
        print(result.stdout[-500:], flush=True)
        return None
    path = glob.glob(os.path.join(out, "*", "result_images_0_url.png"))[0]

    im = Image.open(path).convert("RGBA")
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 40)
    content = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    scale = 874 / content.height
    cw, ch = int(content.width * scale), 874
    content = content.resize((cw, ch), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.paste(content, ((1024 - cw) // 2, 1024 - 90 - ch), content)
    padded = os.path.join(BASE, pet, "still_padded_v2.png")
    canvas.save(padded)
    compare = Image.new("RGB", (700, 460), (255, 250, 240))
    classic = Image.open(os.path.join(BASE, pet, "ref_idle_classic.png")).convert("RGBA")
    classic.thumbnail((220, 420), Image.LANCZOS)
    newim = canvas.copy(); newim.thumbnail((220, 420), Image.LANCZOS)
    compare.paste(classic, (10, 20), classic)
    compare.paste(newim, (250, 20), newim)
    v1 = os.path.join(BASE, pet, "still_padded.png")
    if os.path.isfile(v1):
        old = Image.open(v1).convert("RGBA"); old.thumbnail((220, 420), Image.LANCZOS)
        compare.paste(old, (480, 20), old)
    compare.save(os.path.join(BASE, pet, "still_compare_v2.jpg"), quality=90)
    print(f"[PAD] {pet} content {cw}x874 bottom margin 90", flush=True)
    return padded


def gen_animation(pet, action, anchor, out_name):
    out = os.path.join(BASE, pet, out_name)
    prompt = IDLE_MOTION if action == "idle" else ACTIONS[pet][action]
    extra = CLOSED_MOUTH if action in ("idle", "pet", "happy", "drag", "sleep", "walk", "dig_reward") else " The mouth may open naturally while eating."
    if pet == "ice_cream":
        extra += KEEP_SCARF
    result = run([
        "meowa-animation-run", "--output-dir", out,
        "--image-file", anchor, "--last-image-file", anchor,
        "--style-mode", "hd", "--resolution", "720p",
        "--output-frames", "16", "--quality-mode", "medium",
        "--alpha-mode", "soft", "--remove-bg-method", "standard",
        "--no-optimize-prompt", "--prompt", prompt + extra + " " + COMMON,
    ])
    ok = '"status": "success"' in result.stdout
    print(f"[{'OK' if ok else 'FAIL'}] {pet}/{action}", flush=True)
    if not ok:
        print(result.stdout[-500:], flush=True)
    return ok


def body_stats(path):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[:, :, 3]
    ys, xs = np.where(a > 50)
    return im.size, ys.max() - ys.min() + 1


def import_all():
    # scale 标定:新 idle 帧体高比对经典 idle 帧
    scales = {}
    for pet in ("lunch_meat", "ice_cream"):
        classic_frames = sorted(glob.glob(
            os.path.join(RUNTIME, pet, "desktop", "animations", "idle", "*.png")))
        c_size, c_h = body_stats(classic_frames[0])
        new_frame = sorted(glob.glob(
            os.path.join(BASE, pet, "idle_v2", "frames", "000.png")))
        n_size, n_h = body_stats(new_frame[0])
        scales[pet] = round((c_h / c_size[1]) / (n_h / n_size[1]), 4)
        print(f"[SCALE] {pet} {scales[pet]}", flush=True)

    for pet in ("lunch_meat", "ice_cream"):
        actions = ["idle", "pet", "eat", "play", "happy", "dig_reward", "drag"]
        if pet == "lunch_meat":
            actions += ["sleep", "walk"]
        for action in actions:
            src = glob.glob(os.path.join(
                BASE, pet, f"{action}_v2", "*", "meowa_animation.webp"))
            if not src:
                print(f"[MISS] {pet}/{action}", flush=True)
                continue
            im = Image.open(src[0])
            n = getattr(im, "n_frames", 1)
            if n != 16:
                print(f"[SKIP] {pet}/{action} frames={n}", flush=True)
                continue
            frames_dir = os.path.join(BASE, pet, f"{action}_v2", "frames")
            os.makedirs(frames_dir, exist_ok=True)
            dst = os.path.join(RUNTIME, pet, "desktop_new", "animations", action)
            os.makedirs(dst, exist_ok=True)
            bots = []
            for i in range(n):
                im.seek(i)
                fr = im.convert("RGBA")
                fr.save(os.path.join(frames_dir, f"{i:03d}.png"))
                with open(os.path.join(frames_dir, f"{i:03d}.png"), "rb") as fh:
                    data = fh.read()
                with open(os.path.join(dst, f"{i:03d}.png"), "wb") as out:
                    out.write(data)
                a = np.array(fr)[:, :, 3]
                ys, _ = np.where(a > 50)
                bots.append(int(ys.max()))
            # 审计图+MP4
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
            sheet.save(os.path.join(BASE, pet, f"{action}_v2", "audit_sheet.jpg"), quality=88)
            concat = os.path.join(BASE, pet, f"{action}_v2", "concat.txt")
            with open(concat, "w") as f:
                for _ in range(2):
                    for i in range(n):
                        f.write("file " + os.path.join(frames_dir, f"{i:03d}.png").replace("\\", "/") + "\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-r", "8",
                 "-i", concat, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                 os.path.join(BASE, pet, f"{action}_v2", "preview.mp4")],
                capture_output=True)
            os.remove(concat)
            print(f"[IMPORT] {pet}/{action} bottom {min(bots)}-{max(bots)}", flush=True)

        # poses idle.png 用新 idle 首帧
        pose_src = os.path.join(BASE, pet, "idle_v2", "frames", "000.png")
        if os.path.isfile(pose_src):
            with open(pose_src, "rb") as fh:
                data = fh.read()
            with open(os.path.join(RUNTIME, pet, "desktop_new", "poses", "idle.png"), "wb") as out:
                out.write(data)

        # manifest 全键刷 scale
        path = os.path.join(RUNTIME, pet, "desktop_new", "animations", "manifest.json")
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        for key, spec in manifest.items():
            if isinstance(spec, dict):
                spec["scale"] = scales[pet]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"[MANIFEST] {pet} scale={scales[pet]} keys={sorted(manifest)}", flush=True)


if __name__ == "__main__":
    for pet in ("lunch_meat", "ice_cream"):
        anchor = gen_still(pet)
        if not anchor:
            sys.exit(f"still failed for {pet}")
        ok = gen_animation(pet, "idle", anchor, "idle_v2")
        if not ok:
            sys.exit(f"idle failed for {pet}")
        idle_frame = os.path.join(BASE, pet, "idle_v2", "frames", "000.png")
        src = glob.glob(os.path.join(BASE, pet, "idle_v2", "*", "meowa_animation.webp"))[0]
        os.makedirs(os.path.join(BASE, pet, "idle_v2", "frames"), exist_ok=True)
        Image.open(src).convert("RGBA").save(idle_frame)
        for action in ACTIONS[pet]:
            gen_animation(pet, action, idle_frame, f"{action}_v2")
    import_all()
    print("V2 BATCH DONE", flush=True)
