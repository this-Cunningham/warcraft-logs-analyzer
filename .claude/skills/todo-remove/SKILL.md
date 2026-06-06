---
name: todo-remove
description: Add a TODO item to remove a report section and clean up every dangling reference, framed by the product soul. Invoked by the user as `/todo-remove <report section>`.
model: sonnet
allowed-tools: Read, Grep, Edit, Bash
---

# todo-remove

The user has decided a section should be **cut** from the report. Capture that as a
`TODO.md` item that names the section, the soul-based reason, and a concrete checklist
of every place the removal must clean up — so nothing dangles.

> $ARGUMENTS

(the report section to remove)

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

1. **Read `PRODUCT_MANAGER_SOUL.md`** (repo root). Note the cut reason in the soul's
   own terms — *helps with nothing* / *silly* (no decision · noise gap · cool-data) /
   *unfixable confound* / *redundant* / *raw dump* / *blame* / *unreadable*. The user
   is making the call; you're recording it, not re-litigating it. (If you think the
   cut is wrong — e.g. it's really a `/todo-zoom`, a `/todo-reframe`, or a legibility fix — add
   the item but say so in one line.)
2. **Enumerate the dangling refs — this is the core of the skill.** Ground the
   section in `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` to
   get its builder→renderer symbols, then **grep** for everything a removal must
   touch:
   - the builder function + its `DATA` key in `scripts/build_deepdive.py`
   - the renderer JS + the template/CSS block in `templates/report.html`
   - any **Overview** wiring (Biggest-Gaps / What-You're-Doing-Well ranking
     dimensions) that reads this section's data
   - the `report-anatomy.md` entry itself
   - anything else the grep turns up (helpers, constants, sub-tab registration)
   List the concrete symbols/files so the future cleanup is mechanical.
3. **Sync, then read `TODO.md`.** Run the sync in *Always write to `main`* above, then
   read `TODO.md` (repo-root path) to match its style (`## TODO:` headers, a `>`
   blockquote restating the ask, then notes).
4. **Place the item.** A `## TODO: <section> — remove` header (or an existing
   removals section), a `>` blockquote with the user's ask in their framing, then the
   **cut reason** and the **dangling-refs checklist** from step 2.
5. **Edit `TODO.md`** to insert it. Keep it lightweight; do not rewrite or reorder
   existing items. Newest at the bottom of its section.
6. **Commit + push to `main`:**
   ```
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" add TODO.md
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" commit -m "TODO: remove — <section>"
   git -C "C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer" push origin main
   ```

## Paths (always use these absolute paths)

- Soul: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\PRODUCT_MANAGER_SOUL.md`
- File: `C:\Users\cdstu\Documents\dev\warcraft-logs-analyzer\TODO.md`

## Notes

- This only records the intent + the cleanup map; it does **not** edit the report.
- Capture the user's ask faithfully; don't expand scope beyond the named section.
- Report back in one sentence: which section you added it to, and how many refs you
  found to clean up.
