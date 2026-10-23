"""四节图标水彩化(2026-10-23 用户令:前四节也换水彩画笔风格)。
参照=新画风水彩画笔图标;逐个生成 heart/paw/leaf/star 同风格件,
裁 72² 居中替换 runtime 原文件(文件名不变,引用链零改动)。
"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
REF = os.path.join("assets", "runtime", "ui", "pet_profile_new", "icon_brush_style.png")
OUT_DIR = os.path.join(BASE, "section_icons")

JOBS = {
    "icon_heart_affection.png": "heart",
    "icon_paw_attributes.png": "round paw print",
    "icon_leaf_personality.png": "small green leaf",
    "icon_star_level.png": "five-pointed star",
}

STYLE = (
    "A single small {} icon for a pet profile section, drawn in exactly "
    "the same soft warm watercolor painting art style, same warm cream "
    "and coral-orange watercolor palette, same rounded cute shapes and "
    "gentle brush texture as the paintbrush in the reference image. "
    "Centered, plain transparent background, no text, no border, "
    "no frame, matte finish."
)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for filename, shape in JOBS.items():
        out = os.path.join(OUT_DIR, shape.replace(" ", "_"))
        result = subprocess.run(
            [sys.executable, API, "image-2.5-run",
             "--output-dir", out, "--quality", "detailed",
             "--resolution", "1K", "--remove-bg-method", "standard",
             "--reference-image", REF,
             "--prompt", STYLE.format(shape)],
            capture_output=True, text=True, timeout=300)
        ok = '"status": "success"' in result.stdout
        print(f"[{'OK' if ok else 'FAIL'}] {shape}", flush=True)
        if not ok:
            print(result.stdout[-300:], flush=True)
            continue
        src = glob.glob(os.path.join(out, "*", "result_images_0_url.png"))[0]
        im = Image.open(src).convert("RGBA")
        a = np.array(im)[:, :, 3]
        ys, xs = np.where(a > 40)
        content = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
        scale = 66 / max(content.size)
        nw, nh = max(1, int(content.width * scale)), max(1, int(content.height * scale))
        content = content.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        canvas.paste(content, ((72 - nw) // 2, (72 - nh) // 2), content)
        dst = os.path.join("assets", "runtime", "ui", "pet_profile_new", filename)
        canvas.save(dst)
        print(f"[IMPORT] {filename} content {nw}x{nh}", flush=True)
    print("ICONS DONE")


if __name__ == "__main__":
    main()
