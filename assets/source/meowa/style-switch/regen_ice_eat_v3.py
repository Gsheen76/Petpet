"""冰淇淋 eat v3 单条重做:禁地面/地毯纹理(引擎曾擅加满幅地毯)。"""
import os
import subprocess
import sys

BASE = os.path.join("assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"
anchor = os.path.join(BASE, "ice_cream", "anchor_v3b.png")
prompt = (
    "A dainty little eater: the puppy lowers its head, takes one small "
    "delicate bite from a small cream food bowl placed right in front of "
    "its front paws, chews slowly and carefully, then licks its lips and "
    "squints in quiet contentment. The small green neck scarf stays on in "
    "every frame. The mouth may open naturally while eating. Keep the "
    "exact same character, colors, watercolor storybook art style and "
    "facing direction as the reference image in every frame. The whole "
    "action stays fully inside the canvas with generous empty space around "
    "the character - nothing is ever cut off by the canvas edge. Only the "
    "puppy and the small bowl exist on a plain fully transparent "
    "background - no floor, no ground, no rug, no carpet, no ground "
    "texture, no shadow, no extra objects, no text, no human hands."
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
print("regen ice eat:", "OK" if ok else "FAIL")
