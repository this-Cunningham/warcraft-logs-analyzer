---
name: reframe
description: Add a TODO item flagging a report section that might hold real latent value but doesn't look valuable on its current surface — with a mandate to evaluate it from the RENDERED HTML as a consumer first, not from the code. Invoked by the user as `/reframe <report section>`.
model: sonnet
allowed-tools: Read, Edit, Bash
---

# reframe

The user suspects a section **might be hiding something genuinely valuable**, but on
its current surface it doesn't read that way. Capture that as a `TODO.md` item whose
core mandate is: **judge this section the way a raid leader sees it — from the
rendered HTML output — before reading a line of the code that builds it.**

> $ARGUMENTS

(the report section to reframe)

## Why this skill is different

The trap this skill exists to break: evaluating a section *code-first* makes you
reason about what the data *could* mean, not what a leader actually *experiences*.
Latent value is usually hidden by how the section is **presented or sliced** — the
right number cut along the wrong axis reads as noise — and you can only see that from
the consumer's seat. This is the soul's **legibility floor** + *latent value behind a
bad surface → fix the surface (sharpen), don't cut* — but you can't tell latent-value
from truly-inert until you've looked at the rendered thing as a leader would.

Note this is **not** `/zoom`. `/zoom` goes one cut *deeper* (a finer grain). `/reframe`
re-cuts the *same* data along a **different axis** — what/when/where/who/why — or
presents it differently. The data may already be at the right grain; it's just framed
in a way that buries the signal.

So the item must instruct the future executor to **view the rendered report first**,
and explicitly **not** open `build_deepdive.py` / `report.html` to form the initial
judgment.

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

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root) for the framing — the legibility
   floor and *latent value behind a bad surface → sharpen, don't cut*. Do **not**
   read the builder/renderer here; this skill deliberately defers code-reading to the
   consumer-view evaluation in the task itself.
2. **Sync, then read `TODO.md`.** Run the sync in *Always write to `main`* above, then
   read `TODO.md` (repo-root path) to match its style (`## TODO:` headers, a `>`
   blockquote restating the ask, then notes).
3. **Place the item.** A `## TODO: <section> — reframe` header (or an existing reframe
   section), a `>` blockquote with the user's hunch in their framing, then a note that
   spells out the **consumer-first mandate**:
   - **View the rendered HTML as a raid leader first.** Start the preview server
     (`report-preview` in `.claude/launch.json`) against a generated report under
     `reports/` (regenerate via the analyzer pipeline if none exists), navigate to the
     named section/tab, and screenshot/snapshot it. Read the labels, framing, and
     visual the way a leader would.
   - **Only then** form a verdict: is there real latent value the current surface is
     burying? If **yes** → name the reframe, which may be **(a)** a clearer
     presentation of the same cut (legibility), or **(b)** a *different slice of the
     same data* along a new axis — by mechanic instead of by spec, by phase instead of
     by fight-total, by target instead of by source. If **no** → it may be a `/remove`
     candidate; say so.
   - **Do not** start by reading `build_deepdive.py` / `templates/report.html` — that's
     the trap this item is guarding against.
4. **Edit `TODO.md`** to insert it. Lightweight; don't rewrite or reorder existing
   items. Newest at the bottom of its section.
5. **Commit + push to `main`:**
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: reframe — <section>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push origin main
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- Capture the user's hunch faithfully; don't pre-judge the value yourself (the whole
  point is to look at the rendered thing later).
- Report back in one sentence: which section you added it to (new or existing).
