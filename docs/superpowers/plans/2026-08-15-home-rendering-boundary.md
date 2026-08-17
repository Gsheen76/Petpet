# Home Rendering Boundary

## Goal

Move home visual constants and pure rendering helpers into `petpet.home.rendering`, keeping `home_scene` exports stable for the window controller and tests.

## Steps

1. Add failing ownership tests for the status-card renderer and pet-frame geometry.
2. Move paths, dimensions, card rendering, sprite source rectangles, contacts, shadow, fade, and board geometry.
3. Import the package contract into the legacy controller module.
4. Run focused/full tests, source smoke, and Obsidian sync.

