# -*- coding: utf-8 -*-
"""Phase 1 取证 II：红/蓝通道叠加目视比对（逐像素差异直接可见）。

红=参照（应在其右/左的基准），蓝绿=比较对象。身体重合处显灰黑，
水平错位处显红/蓝描边——描边方向即偏移方向。
产出四张：①旧idle vs 新idle ②新idle vs eat ③新idle vs drag_hover ④新idle vs pet
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(r"D:\Agent_project\Petpet")
BASE = REPO / "assets/runtime/pets/lunch_meat/desktop/animations/outfits/strawberry"
OUT = REPO / "assets/source/meowa/strawberry-outfit/v3-idle/overlay"
OUT.mkdir(parents=True, exist_ok=True)


def extract_old_idle(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    prefix = "assets/runtime/pets/lunch_meat/desktop/animations/outfits/strawberry/idle"
    listing = subprocess.run(
        ["git", "ls-tree", "--name-only", "01bb21c~1", f"{prefix}/"],
        capture_output=True, text=True, cwd=REPO).stdout
    for rel in [ln.strip() for ln in listing.splitlines() if ln.strip().endswith(".png")]:
        out = subprocess.run(["git", "show", f"01bb21c~1:{rel}"],
                             capture_output=True, cwd=REPO)
        (dest / Path(rel).name).write_bytes(out.stdout)


def overlay(a_ref: np.ndarray, a_cmp: np.ndarray) -> Image.Image:
    """参照→红通道，比较→蓝通道，共同→白。"""
    s = 480
    def prep(a):
        im = Image.fromarray(a, "RGBA").resize((s, s), Image.LANCZOS)
        return np.asarray(im)
    r, c = prep(a_ref), prep(a_cmp)
    canvas = np.full((s, s, 3), 255, dtype=np.uint8)
    rm = r[..., 3] > 60
    cm = c[..., 3] > 60
    canvas[rm & ~cm] = [220, 60, 60]     # 仅参照 → 红
    canvas[cm & ~rm] = [50, 90, 220]     # 仅比较 → 蓝
    canvas[rm & cm] = [170, 170, 170]    # 共同 → 灰
    return Image.fromarray(canvas)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        old_dir = Path(td) / "old"
        extract_old_idle(old_dir)
        old0 = np.asarray(Image.open(sorted(old_dir.glob("*.png"))[8]))  # 旧 idle 中段帧
        new0 = np.asarray(Image.open(BASE / "idle" / "000.png"))
        eat0 = np.asarray(Image.open(sorted((BASE / "eat").glob("*.png"))[0]))
        pet5 = np.asarray(Image.open(sorted((BASE / "pet").glob("*.png"))[5]))
        hov0 = np.asarray(Image.open(sorted((BASE / "drag_hover").glob("*.png"))[0]))
        pairs = [
            ("cmp_old_vs_new.png", old0, new0, "红=旧idle 蓝=新idle"),
            ("cmp_new_vs_eat.png", new0, eat0, "红=新idle 蓝=eat"),
            ("cmp_new_vs_pet.png", new0, pet5, "红=新idle 蓝=pet"),
            ("cmp_new_vs_hover.png", new0, hov0, "红=新idle 蓝=drag_hover"),
        ]
        # 并排+叠加三联图
        for name, ref, cmp_, label in pairs:
            ov = overlay(ref, cmp_)
            w = ov.width
            sheet = Image.new("RGB", (w * 3 + 20, ov.height), (250, 250, 250))
            sheet.paste(Image.fromarray(np.asarray(Image.fromarray(ref, "RGBA").resize((w, w)))[..., :3]), (0, 0))
            sheet.paste(Image.fromarray(np.asarray(Image.fromarray(cmp_, "RGBA").resize((w, w)))[..., :3]), (w + 10, 0))
            sheet.paste(ov, (2 * w + 20, 0))
            sheet.save(OUT / name)
            print(name, "<-", label)
    print("overlay 目录:", OUT)


if __name__ == "__main__":
    main()
