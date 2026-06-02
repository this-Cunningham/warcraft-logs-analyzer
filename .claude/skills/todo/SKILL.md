---
name: todo
description: Add a backlog item to TODO.md, in the voice of the product. Invoked by the user as `/todo <the idea>`.
model: sonnet
allowed-tools: Read, Edit, Bash
---

# todo

Add this idea to `TODO.md`, framed against the product's guiding principles.

> $ARGUMENTS

## Steps

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root) — this is the product's soul.
   Every item must answer to it: does the idea reveal an actionable gap, honestly,
   at a glance? Use it to frame *why* the item matters and to phrase it in the
   product's voice (neutral analyst; gap-focused; not a data dump).
2. **Read `TODO.md`** at the path below — understand its current sections and style
   (markdown `## TODO:` headers, a `>` blockquote restating the ask, then notes).
3. **Place the item.** Decide whether it belongs under an existing section or
   warrants a new `## TODO:` section. Match the existing format exactly:
   - A `## TODO: <short title>` header (only if it's a new section).
   - A `>` blockquote capturing the user's ask in their framing.
   - A short note tying it to the product soul — the gap it reveals / the action
     it enables — and any obvious data source or open question.
4. **Edit `TODO.md`** to insert it. Keep it lightweight; do not rewrite or
   reorder existing items. Newest ideas go at the bottom of their section.
5. **Commit** the change directly to main:
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: <short title>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- Do not invent scope the user didn't ask for. Capture the idea faithfully, just
  framed through the soul.
- If the idea clearly conflicts with an anti-goal in the soul (data dump, blame
  machine, WCL replacement, dishonesty), still add it but note the tension in one
  line so it's flagged for later judgment.
- Report back in one sentence: which section you added it to (new or existing).
