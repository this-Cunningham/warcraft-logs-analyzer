---
name: backlog
description: Add a longer-term idea to BACKLOG.md, in the voice of the product. Invoked by the user as `/backlog <the idea>`.
model: sonnet
allowed-tools: Read, Edit, Write
---

# backlog

Add this idea to `BACKLOG.md`, framed against the product's guiding principles.
Backlog items are bigger or longer-term than `TODO.md` items — things that need more
research, design, or are lower priority right now.

> $ARGUMENTS

## Steps

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root) — this is the product's soul.
   Every item must answer to it: does the idea reveal an actionable gap,
   honestly, at a glance? Use it to frame *why* the item matters and to phrase it
   in the product's voice (neutral analyst; gap-focused; not a data dump).
2. **Read `BACKLOG.md`** (repo root) — understand its current sections and style.
   If it doesn't exist yet, create it with the same header structure as `TODO.md`.
3. **Place the item.** Decide whether it belongs under an existing section or
   warrants a new `## BACKLOG:` header. Match the existing format exactly:
   - A `## BACKLOG: <short title>` header (only if it's a new section).
   - A `>` blockquote capturing the user's ask in their framing.
   - A short note tying it to the product soul — the gap it reveals / the action
     it enables — and any obvious data source or open question.
4. **Edit `BACKLOG.md`** to insert it. Keep it lightweight; do not rewrite or
   reorder existing items. Newest ideas go at the bottom of their section.

## Notes

- Do not invent scope the user didn't ask for. Capture the idea faithfully, just
  framed through the soul.
- If the idea clearly conflicts with an anti-goal in the soul (data dump, blame
  machine, WCL replacement, dishonesty), still add it but note the tension in one
  line so it's flagged for later judgment.
- Report back in one sentence: which section you added it to (new or existing).
