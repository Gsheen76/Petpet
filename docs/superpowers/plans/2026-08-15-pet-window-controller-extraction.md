# Pet Window Controller Extraction

## Goal

Move the desktop pet runtime controller into `petpet.app.pet_window` while retaining `pet.PetWindow` as the exact compatibility object and preserving all root-level patch seams.

## Steps

1. Add a failing ownership test.
2. Extract the complete controller with explicit stable imports and a lazy compatibility resolver for entry-owned state, windows, flags, and signals.
3. Replace the root class with an exact package alias.
4. Run desktop behavior focused tests, full tests, source smoke, and Obsidian sync.
