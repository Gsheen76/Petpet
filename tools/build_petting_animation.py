"""Build the deterministic 24-frame left-click petting animation.

The dog frames reuse the most consistent seated poses from the eat animation.
Only the hand is AI-generated; motion, alignment, timing, and easing are
calculated here so the character never drifts between frames.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


PROJECT_DIR = Path(__file__).resolve().parent.parent
ANIMATIONS_DIR = PROJECT_DIR / "assets" / "animations"
OUTPUT_DIR = ANIMATIONS_DIR / "pet"
HAND_PATH = ANIMATIONS_DIR / "sources" / "pet_hand.png"
DOG_OPEN_PATH = ANIMATIONS_DIR / "eat" / "007.png"
DOG_CLOSED_PATHS = (
    ANIMATIONS_DIR / "eat" / "004.png",
    ANIMATIONS_DIR / "eat" / "005.png",
)

FRAME_COUNT = 24
CANVAS_SIZE = (512, 512)
DOG_TARGET_SIZE = (270, 380)
DOG_BASELINE = 448
HAND_TARGET_WIDTH = 230


def _ease_out_cubic(value: float) -> float:
    return 1.0 - (1.0 - value) ** 3


def _ease_in_cubic(value: float) -> float:
    return value ** 3


def _load_dog(path: Path) -> Image.Image:
    dog = Image.open(path).convert("RGBA")
    # The original eat sequence contains a separate food morsel below the
    # paws. Keep only the connected alpha component containing the dog's
    # torso; a coordinate cutoff can leave a few antialiased orange pixels.
    alpha = dog.getchannel("A")
    connected = alpha.point(lambda value: 255 if value else 0)
    seed = (dog.width // 2, dog.height // 2)
    if connected.getpixel(seed) == 0:
        raise RuntimeError(f"Dog source seed is transparent: {path}")
    ImageDraw.floodfill(connected, seed, 128, thresh=0)
    keep = connected.point(lambda value: 255 if value == 128 else 0)
    dog.putalpha(ImageChops.multiply(alpha, keep))
    bounds = dog.getchannel("A").getbbox()
    if not bounds:
        raise RuntimeError(f"Dog source has no visible pixels: {path}")
    return dog.crop(bounds)


def _prepare_hand() -> Image.Image:
    hand = Image.open(HAND_PATH).convert("RGBA")
    bounds = hand.getchannel("A").getbbox()
    if not bounds:
        raise RuntimeError(f"Hand source has no visible pixels: {HAND_PATH}")
    hand = hand.crop(bounds)
    height = max(1, round(hand.height * HAND_TARGET_WIDTH / hand.width))
    return hand.resize(
        (HAND_TARGET_WIDTH, height),
        Image.Resampling.LANCZOS,
    )


def _dog_for_frame(
        frame_index: int,
        dog_open: Image.Image,
        dogs_closed: tuple[Image.Image, Image.Image],
) -> Image.Image:
    if 3 <= frame_index <= 20:
        return dogs_closed[((frame_index - 3) // 3) % 2]
    return dog_open


def _render_frame(
        frame_index: int,
        dog_source: Image.Image,
        hand_source: Image.Image,
) -> Image.Image:
    frame = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))

    touching = 3 <= frame_index <= 20
    if touching:
        phase = (frame_index - 3) / 17.0
        sway = math.sin(phase * math.tau * 2.0)
        pressure = 0.5 + 0.5 * math.sin(
            (frame_index - 3) / 4.0 * math.tau - math.pi / 2.0
        )
    else:
        sway = 0.0
        pressure = 0.0

    dog_width = round(DOG_TARGET_SIZE[0] * (1.0 + 0.008 * sway))
    dog_height = round(DOG_TARGET_SIZE[1] * (1.0 - 0.015 * pressure))
    dog = dog_source.resize(
        (dog_width, dog_height),
        Image.Resampling.LANCZOS,
    )
    dog_x = round((CANVAS_SIZE[0] - dog_width) / 2 + 3.0 * sway)
    dog_y = DOG_BASELINE - dog_height
    frame.alpha_composite(dog, (dog_x, dog_y))

    if frame_index <= 3:
        progress = _ease_out_cubic(frame_index / 3.0)
        hand_y = round(-205 + 135 * progress)
        hand_x = round(220 + 4 * progress)
        angle = -2.0 + 2.0 * progress
    elif frame_index <= 19:
        phase = (frame_index - 4) / 8.0 * math.tau
        hand_x = round(224 + 21 * (0.5 + 0.5 * math.sin(phase)))
        hand_y = round(-70 + 5 * abs(math.sin(phase)))
        angle = 2.2 * math.sin(phase)
    else:
        progress = _ease_in_cubic((frame_index - 20) / 3.0)
        hand_y = round(-70 - 145 * progress)
        hand_x = round(224 + 8 * progress)
        angle = 2.0 * progress

    hand = hand_source.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    frame.alpha_composite(hand, (hand_x, hand_y))
    return frame


def main() -> None:
    dog_open = _load_dog(DOG_OPEN_PATH)
    dogs_closed = tuple(_load_dog(path) for path in DOG_CLOSED_PATHS)
    hand = _prepare_hand()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for frame_index in range(FRAME_COUNT):
        dog_source = _dog_for_frame(
            frame_index, dog_open, dogs_closed
        )
        frame = _render_frame(frame_index, dog_source, hand)
        output_path = OUTPUT_DIR / f"{frame_index:03d}.png"
        frame.save(output_path, optimize=True)
        print(output_path)


if __name__ == "__main__":
    main()
