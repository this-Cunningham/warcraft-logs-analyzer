---
name: todo-backlog
description: Add a longer-term idea to BACKLOG.md, in the voice of the product. Invoked by the user as `/todo-backlog <the idea>`.
model: sonnet
allowed-tools: Read, Edit, Bash
---

# todo-backlog

Add this idea to `BACKLOG.md`, framed against the product's guiding principles.
Backlog items are bigger or longer-term than `TODO.md` items — things that need more
research, design, or are lower priority right now.

> $ARGUMENTS

## Capture the decision — don't overrule it

**The user's ask is a decision, not a proposal.** Record it faithfully and frame *why it
matters*; do not re-litigate whether it should exist. If the user calls something a
**bug**, write it as a bug (never downgrade to "verify" or "by design"); if they ask to
**build / change / remove**, capture that exact intent. The soul is for **framing**
(naming the leader decision + lever, neutral-analyst voice) — not a filter the request
must pass. The only thing you may add beyond a faithful capture is a **concrete factual**
note (accuracy constraint, data limit, feasibility cost) in one line — never an argument
that the item shouldn't be done, and never by reclassifying the user's call.

## Always write to `main`

This skill only ever touches `BACKLOG.md` in the **canonical main checkout** (the repo
root in *Paths* below) — always on the `main` branch, never the current worktree or
feature branch. **Before editing**, sync it so you append to the latest list and the
final push fast-forwards cleanly:

```
git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" fetch origin
git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" pull --ff-only origin main
```

If the fast-forward fails, stop and surface it (don't force) — the main checkout has
diverged and needs a human.

## Steps

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root) — this is the product's soul. Use it
   **only to frame** *why* the item matters — the **leader decision** it serves and the
   **lever** it surfaces (not a prescribed action) — and to phrase it in the product's
   voice (neutral analyst; lever-focused, never a verdict; never a data dump). Do **not**
   use it to decide whether to honor the user's ask (see *Capture the decision* above).
2. **Sync, then read `BACKLOG.md`.** Run the sync in *Always write to `main`* above,
   then read `BACKLOG.md` at the path below — understand its current sections and style.
3. **Place the item.** Decide whether it belongs under an existing section or
   warrants a new `## BACKLOG:` header. Match the existing format exactly:
   - A `## BACKLOG: <short title>` header (only if it's a new section).
   - A `>` blockquote capturing the user's ask in their framing.
   - A short note tying it to the product soul — the leader decision it serves and
     the lever it surfaces, plus the magnitude that would make it matter — and any
     obvious data source or open question.
4. **Edit `BACKLOG.md`** to insert it. Keep it lightweight; do not rewrite or
   reorder existing items. Newest ideas go at the bottom of their section.
5. **Commit + push to `main`:**
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add BACKLOG.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "BACKLOG: <short title>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push origin main
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\BACKLOG.md`

## Notes

- Do not invent scope the user didn't ask for, and do not shrink it either. Capture the
  idea faithfully — the user's classification, severity, and wording are preserved, just
  framed through the soul.
- If you notice a genuine accuracy, data-availability, or feasibility constraint, add it
  as **one neutral line of context** — never as a reason to not do the item, and never
  by reclassifying the user's call.
- Report back in one sentence: which section you added it to (new or existing).
