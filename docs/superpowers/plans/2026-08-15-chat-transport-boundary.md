# Chat Transport Boundary Refactor

## Goal

Move provider-neutral payload fitting plus Cloudflare/Aliyun and personal GLM streaming transports into `petpet.chat.transport`, retaining `buddy_ai` as the compatibility and orchestration facade.

## Steps

1. Add failing tests for UTF-8 payload bounds and personal SSE parsing.
2. Implement transport functions with explicit injected I/O dependencies so existing patches and diagnostics remain valid.
3. Replace the legacy transport implementations with thin adapters.
4. Run focused/full verification, source smoke, and update Obsidian.

