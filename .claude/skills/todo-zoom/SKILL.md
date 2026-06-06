---
name: todo-zoom
description: Add a TODO item to zoom in on / break a report section down more granularly (the soul's "go one cut deeper"), framed by the product soul. Invoked by the user as `/todo-zoom <report section>`.
model: sonnet
allowed-tools: Read, Grep, Edit, Bash
---

# todo-zoom

The user wants the report to **go one level deeper** on a section — to take a
raid-level number and decompose it into the grain that names a lever. Capture that
as a `TODO.md` item, framed through the soul's *surface the lever, never the verdict*
and *what's the one cut deeper?* principle.

> $ARGUMENTS

(the report section / metric to zoom in on)

## Capture the decision — don't overrule it

**The user has decided this section should go deeper.** Record that intent faithfully
and frame the deeper cut; do not re-litigate whether the zoom is worth doing. The
consumer-first view and magnitude notes below are **guidance for whoever implements the
zoom later** — not a worth-it gate you must clear before writing the item. Capture the
user's classification and wording as given; add factual constraints (no honest
dimension to cut by, data not available at that grain) as **one neutral line**, never as
a reason to decline the ask.

## What "zoom" means here

A raw aggregate ("23 interrupts", "Raid DPS 18k") answers *how many* — which is
rarely a lever. The actionable cut is almost always one decomposition down: **who**
(spec), **what** (mechanic / mob / ability), or **when** (phase). `/todo-zoom` records the
intent to take this section from a tally to that deeper, lever-naming cut. The total
can ride along as context; the deeper cut becomes the headline. (Going *deeper* is
distinct from `/todo-reframe`, which re-cuts the same data along a *different* axis.)

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

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root). Use it to **frame** the zoom (not to
   gate it):
   - **What decision** would the deeper cut serve? Name it in a raid leader's voice.
   - **Which grain** names the lever — spec, mechanic, mob, or phase? ("Deeper" means
     a finer *grain*, never a finer *person* — stay raid/spec/mechanic-level, not a
     per-player callout.)
   - **Legibility:** keep the deeper cut readable in seconds — a framing goal for the
     implementer, not a bar the user's request must pass.
   - **Honest-dimension note:** if there's genuinely *no* honest dimension to decompose
     by, record that as one neutral line of context — still write the item the user
     asked for.
2. **Ground the item so it's concrete.** Skim
   `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (and grep the
   builder `scripts/build_deepdive.py` / renderer `templates/report.html` if useful) to
   name the section's builder→renderer symbols. Then add, **as a note in the item for
   the future implementer**, the reminder to view the rendered section in a real report
   first (preview server `report-preview` in `.claude/launch.json`) so they pick the cut
   that reads best — this is implementation guidance, not a check you perform before
   capturing the ask.
3. **Sync, then read `TODO.md`.** Run the sync in *Always write to `main`* above, then
   read `TODO.md` (repo-root path) to match its style (`## TODO:` headers, a `>`
   blockquote restating the ask, then notes).
4. **Place the item.** A `## TODO: <section> — zoom in` header (or an existing
   zoom-ins section), a `>` blockquote with the user's ask in their framing, then a
   short note: **current grain → proposed deeper grain**, the **leader decision** it
   serves, the magnitude/legibility caveat, any honest-dimension open question, and a
   reminder to **judge it as a consumer first** (view the rendered section before
   implementing the deeper cut, not code-first).
5. **Edit `TODO.md`** to insert it. Keep it lightweight; do not rewrite or reorder
   existing items. Newest at the bottom of its section.
6. **Commit + push to `main`:**
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: zoom — <section>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push origin main
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- Capture the user's zoom faithfully; don't invent extra scope.
- If the section genuinely can't be decomposed honestly, still add the item but flag
  that tension in one line.
- Report back in one sentence: which section you added it to (new or existing).
