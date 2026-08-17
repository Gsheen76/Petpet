# Desktop Surfaces Extraction

## Goal

Move desktop status, action, reward, interaction, and speech bubbles into `petpet.ui.desktop` without changing root imports or runtime patch points.

## Steps

1. Add failing package-ownership tests.
2. Extract shared pet-anchor geometry helpers and five bubble/menu classes.
3. Add a lazy compatibility dependency resolver for root dialogs, state writes, progression services, and patched bubble classes.
4. Run desktop/menu/reward/speech focused tests, full tests, source smoke, and Obsidian sync.

