---
name: zoom
description: Add a TODO item to zoom in on / break a report section down more granularly (the soul's "go one cut deeper"), framed by the product soul. Invoked by the user as `/zoom <report section>`.
model: sonnet
allowed-tools: Read, Grep, Edit, Bash
---

# zoom

The user wants the report to **go one level deeper** on a section — to take a
raid-level number and decompose it into the grain that names a lever. Capture that
as a `TODO.md` item, framed through the soul's *surface the lever, never the verdict*
and *what's the one cut deeper?* principle.

> $ARGUMENTS

(the report section / metric to zoom in on)

## What "zoom" means here

A raw aggregate ("23 interrupts", "Raid DPS 18k") answers *how many* — which is
rarely a lever. The actionable cut is almost always one decomposition down: **who**
(spec), **what** (mechanic / mob / ability), or **when** (phase). `/zoom` records the
intent to take this section from a tally to that deeper, lever-naming cut. The total
can ride along as context; the deeper cut becomes the headline.

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
     (and maybe a `/remove` candidate instead).
2. **Ground the section.** Skim
   `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (and grep the
   builder `scripts/build_deepdive.py` / renderer `templates/report.html` if useful)
   to name the section precisely and note its builder→renderer symbols, so the item
   is concrete rather than vague.
3. **Read `TODO.md`** — match its style (`## TODO:` headers, a `>` blockquote
   restating the ask, then notes).
4. **Place the item.** A `## TODO: <section> — zoom in` header (or an existing
   zoom-ins section), a `>` blockquote with the user's ask in their framing, then a
   short note: **current grain → proposed deeper grain**, the **leader decision** it
   serves, the magnitude/legibility caveat, and any honest-dimension open question.
5. **Edit `TODO.md`** to insert it. Keep it lightweight; do not rewrite or reorder
   existing items. Newest at the bottom of its section.
6. **Commit** the change directly to main:
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: zoom — <section>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- Capture the user's zoom faithfully; don't invent extra scope.
- If the section genuinely can't be decomposed honestly, still add the item but flag
  that tension in one line.
- Report back in one sentence: which section you added it to (new or existing).
