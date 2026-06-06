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

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root). Frame the zoom against it:
   - **What decision** would the deeper cut serve? Name it in a raid leader's voice.
   - **Which grain** names the lever — spec, mechanic, mob, or phase? ("Deeper" means
     a finer *grain*, never a finer *person* — stay raid/spec/mechanic-level, not a
     per-player callout.)
   - **Magnitude + legibility:** is the gap big enough that the deeper cut would
     matter, and can the leader still read it in seconds?
   - **Honesty check:** if there's *no* honest dimension to decompose by, say so —
     the soul treats that as a sign the metric may be a scoreboard, not an insight
     (and maybe a `/todo-remove` candidate instead).
2. **Judge it as a consumer first.** Before reasoning from code, view the named
   section in the **rendered HTML** as a raid leader would — start the preview server
   (`report-preview` in `.claude/launch.json`) against a report under `reports/`
   (regenerate via the analyzer pipeline if none exists), navigate to the section, and
   screenshot/snapshot it. Seeing how the *current* grain actually reads is what tells
   you which deeper cut would genuinely help — and whether the gap even looks worth it.
   *Only then* ground it: skim
   `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (and grep the
   builder `scripts/build_deepdive.py` / renderer `templates/report.html` if useful)
   to name the section's builder→renderer symbols, so the item is concrete.
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
