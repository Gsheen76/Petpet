# Chat Window Extraction

## Goal

Move the complete chat window implementation into `petpet.ui.chat` while keeping `pet.ChatWindow` as a patch-compatible facade for existing callers and tests.

## Steps

1. Add a failing ownership test.
2. Copy the complete window class and inject legacy bridge/dialog/state dependencies.
3. Replace the root implementation with a thin subclass that resolves compatibility globals lazily.
4. Run chat/profile/menu focused tests, full tests, source smoke, and Obsidian sync.

