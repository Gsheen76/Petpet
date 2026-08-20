"""Prepare user-supplied home furniture images for the runtime scene."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


DOWNLOADS = Path(r"C:\Users\sheen\Downloads")
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "scenes" / "home"

# These mappings retain the exact shop identifiers used by saves and the UI.
FURNITURE = {
    "rug.png": (DOWNLOADS / "ChatGPT Image 2026年8月7日 17_14_04.png", (440, 270), "dark"),
    "sofa.png": (DOWNLOADS / "generated-image-1.png", (360, 225), "checkerboard"),
    "plant.png": (DOWNLOADS / "ChatGPT Image 2026年8月7日 17_01_31.png", (190, 340), "green"),
    "wall-art.png": (DOWNLOADS / "image-1786086652512-tbskax0zjg.png", (220, 285), "checkerboard"),
}


def _is_checkerboard_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, _alpha = pixel
    return min(red, green, blue) >= 220 and max(red, green, blue) - min(red, green, blue) <= 20


def _is_background_pixel(pixel: tuple[int, int, int, int], mode: str) -> bool:
    red, green, blue, _alpha = pixel
    if mode == "green":
        return green >= 110 and green - red >= 35 and green - blue >= 30
    if mode == "dark":
        brightness = (red + green + blue) / 3
        return brightness < 238 and max(red, green, blue) - min(red, green, blue) < 105
    return _is_checkerboard_pixel(pixel)


def _transparent_background(image: Image.Image, mode: str) -> Image.Image:
    """Remove edge-connected generated background without damaging the subject."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    if mode == "green":
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = pixels[x, y]
                if _is_background_pixel((red, green, blue, alpha), mode):
                    pixels[x, y] = (red, green, blue, 0)
        bounds = rgba.getchannel("A").getbbox()
        return rgba.crop(bounds) if bounds is not None else rgba
    queued = deque()
    background = set()

    for x in range(width):
        queued.append((x, 0))
        queued.append((x, height - 1))
    for y in range(1, height - 1):
        queued.append((0, y))
        queued.append((width - 1, y))

    while queued:
        x, y = queued.popleft()
        if (x, y) in background or not _is_background_pixel(pixels[x, y], mode):
            continue
        background.add((x, y))
        if x > 0:
            queued.append((x - 1, y))
        if x + 1 < width:
            queued.append((x + 1, y))
        if y > 0:
            queued.append((x, y - 1))
        if y + 1 < height:
            queued.append((x, y + 1))

    for x, y in background:
        red, green, blue, _alpha = pixels[x, y]
        pixels[x, y] = (red, green, blue, 0)

    bounds = rgba.getchannel("A").getbbox()
    return rgba.crop(bounds) if bounds is not None else rgba


def _render(source: Path, target_size: tuple[int, int], mode: str) -> Image.Image:
    subject = _transparent_background(Image.open(source), mode)
    subject.thumbnail(target_size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", target_size)
    x = (target_size[0] - subject.width) // 2
    y = (target_size[1] - subject.height) // 2
    output.alpha_composite(subject, (x, y))
    return output


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (source, target_size, mode) in FURNITURE.items():
        if not source.is_file():
            if (OUTPUT_DIR / filename).is_file():
                continue
            raise FileNotFoundError(source)
        _render(source, target_size, mode).save(OUTPUT_DIR / filename)


if __name__ == "__main__":
    main()
