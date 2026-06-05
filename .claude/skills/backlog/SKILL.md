---
name: backlog
description: Add a longer-term idea to BACKLOG.md, in the voice of the product. Invoked by the user as `/backlog <the idea>`.
model: sonnet
allowed-tools: Read, Edit, Bash
---

# backlog

Add this idea to `BACKLOG.md`, framed against the product's guiding principles.
Backlog items are bigger or longer-term than `TODO.md` items — things that need more
research, design, or are lower priority right now.

> $ARGUMENTS

## Steps

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root) — this is the product's soul.
   Every item must answer to its one-line test: *would this change how a raid leader
   runs next week — and can they read it and trust it in seconds?* Use it to frame
   *why* the item matters — the **leader decision** it serves and the **lever** it
   surfaces (not a prescribed action) — and to phrase it in the product's voice
   (neutral analyst; lever-focused, never a verdict; never a data dump).
2. **Read `BACKLOG.md`** at the path below — understand its current sections and style.
3. **Place the item.** Decide whether it belongs under an existing section or
   warrants a new `## BACKLOG:` header. Match the existing format exactly:
   - A `## BACKLOG: <short title>` header (only if it's a new section).
   - A `>` blockquote capturing the user's ask in their framing.
   - A short note tying it to the product soul — the leader decision it serves and
     the lever it surfaces, plus the magnitude that would make it matter — and any
     obvious data source or open question.
4. **Edit `BACKLOG.md`** to insert it. Keep it lightweight; do not rewrite or
   reorder existing items. Newest ideas go at the bottom of their section.
5. **Commit** the change directly to main:
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add BACKLOG.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "BACKLOG: <short title>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\BACKLOG.md`

## Notes

- Do not invent scope the user didn't ask for. Capture the idea faithfully, just
  framed through the soul.
- If the idea clearly conflicts with an anti-goal in the soul (data dump, bare
  scoreboard, blame machine, WCL replacement, dishonesty, or something a leader
  couldn't read at a glance), still add it but note the tension in one line so it's
  flagged for later judgment.
- Report back in one sentence: which section you added it to (new or existing).
