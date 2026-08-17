# Chat Knowledge Boundary Plan

**Goal:** Move versioned gameplay knowledge lookup into `petpet.chat.knowledge` while retaining the root import.

## Tasks

- [x] Add a failing ownership test for the package module.
- [x] Move validation, loading, version, and relevance ranking unchanged.
- [x] Convert root `game_knowledge.py` into a compatibility facade.
- [x] Update tests to patch the owning module and run focused tests.
- [x] Run full tests, source smoke, diff check, and sync Obsidian.
