# Chat Configuration Boundary Refactor

## Goal

Move chat configuration validation, persistence, model rules, public endpoint lookup, and local Aliyun quota state out of `buddy_ai.py` into `petpet.chat.config` while preserving the legacy public API.

## Steps

1. Add failing boundary tests for normalized configuration, atomic persistence, endpoint precedence, and local quota state.
2. Implement the package module with path-explicit functions so tests and packaged runtime can select their own storage paths.
3. Replace implementations in `buddy_ai.py` with thin adapters that continue honoring its patchable compatibility constants.
4. Run focused and full tests, source GUI smoke, then synchronize the Obsidian implementation record.
