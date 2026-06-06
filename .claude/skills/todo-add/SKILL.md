---
name: todo-add
description: Add a near-term item to TODO.md, in the voice of the product. Invoked by the user as `/todo-add <the idea>`.
model: sonnet
allowed-tools: Read, Edit, Bash
---

# todo-add

Add this idea to `TODO.md`, framed against the product's guiding principles.

> $ARGUMENTS

## Capture the decision — don't overrule it

**The user's ask is a decision, not a proposal.** Your job is to record it faithfully
and frame *why it matters*, in the product's voice. It is **not** to re-litigate
whether it should exist.

- If the user calls something a **bug**, write it down as a bug. Never downgrade it to
  "verify whether it's a bug" or "not a bug — by design." If you find the current
  behavior is intentional, say so in **one neutral line** as added context *and still
  record the user's fix as the ask* — the user decides, not you.
- If the user asks to **build / change / remove** something, capture that exact intent.
  Never substitute a worth-it judgment ("is this worth a leader's time?", "judge as a
  consumer first") for their call. That worth-it lens is for ideas **you** originate in
  a spike — not a veto over an instruction the user has already given.
- The soul is a tool for **framing** (naming the leader decision + the lever, phrasing
  it as a neutral analyst) — not a filter the user's request must pass to get written.
- The only thing you may add beyond a faithful capture is a **concrete, factual** note
  — an accuracy constraint, a data-availability limit, a feasibility cost — in one
  line. Never an argument that the item shouldn't be done.

## Always write to `main`

This skill only ever touches `TODO.md` in the **canonical main checkout** (the repo
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
   use it to decide whether to honor the user's ask (see *Capture the decision* above);
   the soul frames the item, it does not gate it.
2. **Sync, then read `TODO.md`.** Run the sync in *Always write to `main`* above, then
   read `TODO.md` at the path below — understand its current sections and style
   (markdown `## TODO:` headers, a `>` blockquote restating the ask, then notes).
3. **Place the item.** Decide whether it belongs under an existing section or
   warrants a new `## TODO:` section. Match the existing format exactly:
   - A `## TODO: <short title>` header (only if it's a new section).
   - A `>` blockquote capturing the user's ask in their framing.
   - A short note tying it to the product soul — the leader decision it serves and
     the lever it surfaces, plus the magnitude that would make it matter — and any
     obvious data source or open question.
4. **Edit `TODO.md`** to insert it. Keep it lightweight; do not rewrite or
   reorder existing items. Newest ideas go at the bottom of their section.
5. **Commit + push to `main`:**
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: <short title>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push origin main
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- Do not invent scope the user didn't ask for, and do not shrink it either. Capture the
  idea faithfully — the user's classification (bug / build / change), severity, and
  wording are preserved, just framed through the soul.
- If you notice a genuine accuracy, data-availability, or feasibility constraint, add it
  as **one neutral line of context** — never as a reason to not do the item, and never
  by reclassifying the user's call (a "bug" stays a bug).
- Report back in one sentence: which section you added it to (new or existing).
