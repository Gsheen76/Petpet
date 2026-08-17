# Home Geometry Boundary

## Goal

Move the pure home viewport, furniture transform, and scene geometry API into `petpet.home.geometry`, leaving `scene_system.py` as a legacy facade.

## Steps

1. Add a failing ownership test.
2. Move the complete dependency-free geometry module.
3. Re-export its public contract from the root module.
4. Run scene/home focused tests, full tests, source smoke, and Obsidian sync.
