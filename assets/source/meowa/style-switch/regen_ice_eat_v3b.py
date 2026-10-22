"""冰淇淋 eat 第三次重做:前两版吃食时身体侧移出框(边带采样=狗毛色)。
本版硬约束:身体位置钉参照位,只做低头动作,盆小且在正前方下巴处。
"""
import os
import subprocess
import sys

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
anchor = os.path.join(BASE, "ice_cream", "anchor_v3b.png")
prompt = (
    "A tiny nibble animation with almost no body movement: the sitting "
    "puppy keeps its body locked in exactly the same centered position as "
    "the reference image, and only lowers its head straight down to take "
    "one small delicate bite from a tiny cream bowl sitting directly under "
    "its chin, chews slowly, then lifts its head back up. The body never "
    "leans, stretches or moves toward the canvas edge, the puppy never "
    "moves off its centered spot. The small green neck scarf stays on in "
    "every frame. Keep the exact same character, colors, watercolor "
    "storybook art style and facing direction as the reference image in "
    "every frame. Only the puppy and the tiny bowl on a plain fully "
    "transparent background - no floor, no ground, no rug, no carpet, no "
    "ground texture, no shadow, no extra objects, no text, no human hands."
)
out = os.path.join(BASE, "ice_cream", "eat_v3")
r = subprocess.run(
    [sys.executable, API, "meowa-animation-run",
     "--output-dir", out, "--image-file", anchor,
     "--last-image-file", anchor, "--style-mode", "hd",
     "--resolution", "720p", "--output-frames", "16",
     "--quality-mode", "medium", "--alpha-mode", "soft",
     "--remove-bg-method", "standard", "--no-optimize-prompt",
     "--prompt", prompt],
    capture_output=True, text=True, timeout=900)
ok = '"status": "success"' in r.stdout
print("regen ice eat v3b:", "OK" if ok else "FAIL")
