"""Build the deterministic 24-frame front-facing fetch/pounce sequence."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parent.parent
ANIMATIONS_DIR = PROJECT_DIR / "assets" / "animations"
SOURCE_SHEET = (
    ANIMATIONS_DIR / "sources" / "fetch-pounce-keyframes-v1.png"
)
OUTPUT_DIR = ANIMATIONS_DIR / "play"

FRAME_COUNT = 24
KEYFRAME_COUNT = 8
GRID_COLUMNS = 4
GRID_ROWS = 2
CANVAS_SIZE = (512, 512)
BASELINE = 440
CELL_SCALE = 0.88

# The interaction ends at the catch.  Landing/settling is handled by returning
# to the normal pet, so the final five frames hold and refine the catch pose.
KEYFRAME_ORDER = (
    0, 0, 0,              # alert
    1, 1, 1, 1,           # crouch
    2, 2, 2, 2,           # launch
    3, 3, 3, 3,           # airborne
    4, 4, 4, 4,           # maximum reach
    5, 5, 5, 5, 5,        # catch on the final frame
)


def _load_keyframes() -> list[Image.Image]:
    sheet = Image.open(SOURCE_SHEET).convert("RGBA")
    keyframes = []
    for index in range(KEYFRAME_COUNT):
        column = index % GRID_COLUMNS
        row = index // GRID_COLUMNS
        cell = sheet.crop((
            round(column * sheet.width / GRID_COLUMNS),
            round(row * sheet.height / GRID_ROWS),
            round((column + 1) * sheet.width / GRID_COLUMNS),
            round((row + 1) * sheet.height / GRID_ROWS),
        ))
        if not cell.getchannel("A").getbbox():
            raise RuntimeError(f"Empty fetch keyframe {index}")
        keyframes.append(cell)
    return keyframes


def _frame_transform(frame_index: int) -> tuple[float, float, float]:
    """Return x scale, y scale and a small local lift for each in-between."""
    keyframe_index = KEYFRAME_ORDER[frame_index]
    segment_start = KEYFRAME_ORDER.index(keyframe_index)
    segment_length = KEYFRAME_ORDER.count(keyframe_index)
    progress = (
        0.0 if segment_length <= 1
        else (frame_index - segment_start) / (segment_length - 1)
    )

    if keyframe_index == 0:  # alert
        return 1.0 + 0.01 * progress, 1.0 - 0.015 * progress, 0.0
    if keyframe_index == 1:  # crouch deeper
        return 1.0 + 0.04 * progress, 1.0 - 0.06 * progress, 0.0
    if keyframe_index == 2:  # push off
        return 1.0 - 0.025 * progress, 1.0 + 0.07 * progress, 8.0 * progress
    if keyframe_index in (3, 4):  # fly forward and reach
        return (
            1.0 + 0.05 * progress,
            1.0 + 0.035 * progress,
            8.0 + 7.0 * progress,
        )
    # Catch: paws draw in slightly while the open mouth stays at the target.
    return 1.04 - 0.025 * progress, 1.03 - 0.035 * progress, 9.0


def _render_frame(source: Image.Image, frame_index: int) -> Image.Image:
    scale_x, scale_y, local_lift = _frame_transform(frame_index)
    width = max(1, round(source.width * CELL_SCALE * scale_x))
    height = max(1, round(source.height * CELL_SCALE * scale_y))
    dog = source.resize((width, height), Image.Resampling.LANCZOS)

    bounds = dog.getchannel("A").getbbox()
    if not bounds:
        raise RuntimeError(f"Empty fetch frame {frame_index}")
    visible_center_x = (bounds[0] + bounds[2]) / 2.0
    x = round(CANVAS_SIZE[0] / 2.0 - visible_center_x)
    y = round(BASELINE - local_lift - bounds[3])

    frame = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    frame.alpha_composite(dog, (x, y))
    return frame


def main() -> None:
    keyframes = _load_keyframes()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for frame_index, keyframe_index in enumerate(KEYFRAME_ORDER):
        frame = _render_frame(keyframes[keyframe_index], frame_index)
        output_path = OUTPUT_DIR / f"{frame_index:03d}.png"
        frame.save(output_path, optimize=True)
        print(output_path)


if __name__ == "__main__":
    main()
