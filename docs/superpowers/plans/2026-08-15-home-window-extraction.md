# Home Window Extraction

## Goal

Move the complete home scene window into `petpet.home.window`, turning `home_scene.py` into a compatibility facade.

## Steps

1. Add a failing ownership test.
2. Move the current controller module unchanged into the home package.
3. Re-export rendering and window contracts from the root facade, retaining the shared `time` module patch seam.
4. Run focused/full tests, source smoke, and Obsidian sync.
