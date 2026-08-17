# Progression Core Boundary

## Goal

Move progression, affection, coins, upgrades, furniture ownership, and achievements into `petpet.progression.core`, leaving `progression.py` as a compatibility facade.

## Steps

1. Add a failing ownership test.
2. Move the complete pure state/rules module into the package.
3. Re-export its public API and constants from the root facade.
4. Run progression/home/minigame focused tests, full tests, source smoke, and Obsidian sync.

