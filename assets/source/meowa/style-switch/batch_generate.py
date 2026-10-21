"""风格切换阶段三批产驱动:双犬其余 14 条动画顺序生成(仅生成+下载,
导入/六查/manifest 由后续会话处理;每动画子进程——Qt 竞态无关,CLI 顺序即可)。
锚图=各自打样 idle 首帧(960²,底距 86px 达垫边量级)。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
BASE = os.path.join(ROOT, "assets", "source", "meowa", "style-switch")
API = r"C:\Users\sheen\.agents\skills\game-assets\meowart_api.py"

COMMON = (
    "Keep the exact same character, colors, watercolor storybook art style "
    "and facing direction as the reference image in every frame. Plain "
    "transparent background, no added ground shadow, no extra objects, "
    "no text, no human hands."
)

JOBS = {
    "lunch_meat": {
        "anchor": os.path.join(BASE, "lunch_meat", "idle_v1", "frames", "000.png"),
        "actions": {
            "pet": "A short gentle petting interaction with an invisible touch: the sitting puppy leans slightly into the touch, eyes closing contentedly, tail wagging softly, then returns to the same sitting pose. Head and body stay low-motion.",
            "eat": "The sitting puppy lowers its head to eat from a small cream-colored food bowl that appears in front of it, chews gently several times, then lifts its head back up to the same sitting pose.",
            "play": "A playful bounce in place: from the same sitting pose the puppy does two small happy hops with ears flapping and tail spinning, then settles back to the same sitting pose.",
            "happy": "An excited happy wiggle: the sitting puppy tilts its head side to side, ears bouncing, tail wagging fast, big smile, then returns to the same sitting pose.",
            "dig_reward": "The sitting puppy reaches forward and scratches the ground lightly with front paws a few times, then sits back up with sparkling excited eyes and a proud smile.",
            "drag": "The puppy is held suspended in the air by an unseen gentle grip: body hanging with legs dangling, swaying slightly left and right, calm trusting expression. Same framing, character stays centered.",
            "sleep": "The puppy curls into a soft sleeping ball beside its sitting spot, closes its eyes and breathes in a slow gentle loop, then uncurls back to the same sitting pose.",
            "walk": "A natural side-view dog walk in place: four legs alternating in a calm trot while staying centered in frame, head steady, then stops back at the same sitting pose.",
        },
    },
    "ice_cream": {
        "anchor": os.path.join(BASE, "ice_cream", "idle_v1", "frames", "000.png"),
        "actions": {
            "pet": "A soft tender moment with an invisible touch: the sitting puppy leans gently into the touch with a shy sweet smile, eyes half closing, tail swaying slowly, then returns to the same sitting pose. Slow calm motion.",
            "eat": "The sitting puppy lowers its head to eat from a small cream-colored food bowl that appears in front of it, chews slowly and delicately, then lifts its head back with a content smile.",
            "play": "A gentle playful invitation: from the same sitting pose the puppy does one soft little hop with front paws lowered in a play bow, tail wagging sweetly, then returns to sitting.",
            "happy": "A quiet happy moment: the sitting puppy does a small sweet head tilt with soft squinting eyes and a slow tail wag, like a warm smile, then returns to the same sitting pose.",
            "dig_reward": "The sitting puppy paws the ground softly a couple of times, then looks up with round sparkling gentle eyes and a small proud smile.",
            "drag": "The puppy is held suspended in the air by an unseen gentle grip: body hanging with legs dangling, swaying very slightly, calm and trusting. Same framing, character stays centered.",
        },
    },
}


def main():
    for pet, spec in JOBS.items():
        anchor = spec["anchor"]
        if not os.path.isfile(anchor):
            print(f"[SKIP] anchor missing for {pet}: {anchor}")
            continue
        for action, motion in spec["actions"].items():
            out = os.path.join(BASE, pet, f"{action}_v1")
            prompt = f"{motion} {COMMON}"
            print(f"[RUN] {pet}/{action}", flush=True)
            result = subprocess.run(
                [sys.executable, API, "meowa-animation-run",
                 "--output-dir", out,
                 "--image-file", anchor,
                 "--last-image-file", anchor,
                 "--style-mode", "hd", "--resolution", "720p",
                 "--output-frames", "16", "--quality-mode", "medium",
                 "--alpha-mode", "soft", "--remove-bg-method", "standard",
                 "--no-optimize-prompt", "--prompt", prompt],
                capture_output=True, text=True, timeout=900,
            )
            ok = '"status": "success"' in result.stdout
            print(f"[{'OK' if ok else 'FAIL'}] {pet}/{action} rc={result.returncode}",
                  flush=True)
            if not ok:
                print(result.stdout[-600:], result.stderr[-300:], flush=True)
    print("BATCH DONE", flush=True)


if __name__ == "__main__":
    main()
