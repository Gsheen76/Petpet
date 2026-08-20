# Task 2 Report: 价格标签图片资源与工厂

## Delivered files

- `assets/runtime/ui/shop-price-normal-v1.png`
- `assets/runtime/ui/shop-price-sale-v1.png`
- `assets/runtime/ui/shop-price-discount-v1.png`
- `assets/runtime/ui/shop-price-gift-v1.png`
- `petpet/progression/ui.py`
- `tests/test_progression_ui_boundary.py`

All four runtime PNGs are RGBA and retain transparent alpha (verified alpha
range `0..255`). Final dimensions are 240x120 (normal), 213x120 (sale),
180x120 (discount), and 213x120 (gift).

## Asset generation

Built-in image generation produced four transparent assets. The common prompt
requirements were: warm coral and cream handmade paper, fine stitched edge,
small paw-print accent, glossy highlight, a ribbon bow, an empty central text
area, and no words, digits, currency symbols, logo, watermark, character, or
background.

- `normal`: horizontal rounded price tag with the paw-print accent at the left
  and bow at the right.
- `sale`: horizontal rounded price tag with a brighter coral border and sale
  ribbon treatment.
- `discount`: compact rounded discount badge with a blank center for dynamic
  percentage text.
- `gift`: horizontal rounded gift tag with a subtle wrapped-gift flourish.

Source generated images were copied from
`C:\Users\sheen\.codex\generated_images\01a01e48-30dc-74b3-b344-f438a0070ce9`
and downscaled with Lanczos resampling while preserving alpha.

## TDD evidence

RED:

`python -m pytest -q tests/test_progression_ui_boundary.py` produced 14 pass,
2 fail. The expected failures were the old `1000 Pet币` text instead of
`原价：1000 Pet币`, and missing runtime image files.

GREEN:

The minimal implementation added `_price_tag(text, role, object_name)`, binds
all four assets through `priceTagRole` in `PANEL_STYLE`, preserves the original
price strikethrough, and derives the displayed percentage with
`round((1 - price / original_price) * 100)`. The focused test then passed:
16 passed in 1.68s.

## Full verification

`python -m pytest -q` passed: 608 passed in 73.54s.

`git diff --check` completed without whitespace errors.

## Commit

`feat: add illustrated shop price tags`.

## Self-review and concerns

- The implementation uses only Qt's existing stylesheet mechanism and no new
  dependency or shop-layout restructuring.
- Dynamic text remains in `QLabel`; no price text is baked into the PNGs.
- The PNGs are generated artwork, so their exact visual appearance is best
  reviewed in the running shop UI at the target display scale; automated tests
  cover the asset presence, text, roles, and strikethrough behavior.
