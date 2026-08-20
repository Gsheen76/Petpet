# Chat Prompt Service Boundary Plan

**Goal:** Move persona and prompt construction into a pure `petpet.chat.service` boundary while preserving `buddy_ai` compatibility and patchable knowledge lookup.

## Tasks

- [x] Add failing service ownership and behavior tests.
- [x] Move persona, time description, mood detection, and message construction.
- [x] Keep `buddy_ai._build_messages` as a thin compatibility adapter.
- [x] Run focused/full tests, source smoke, diff check, and sync Obsidian.
