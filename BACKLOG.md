# Backlog

Longer-term ideas for the Warcraft Logs analyzer. Items here are bigger, need more
research/design, or are lower priority than [`TODO.md`](TODO.md).

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## BACKLOG: Trash tab — next-pass ideas

> Pending ideas surfaced while building the (shipped) Trash tab.

- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
  Needs a new Casts-on-trash fetch + view; research-flavored, deferred.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier. Conditional, not needed yet.

---

## BACKLOG: per-actor positioning (dead-end until OAuth)

> Spread-vs-stack, boss-facing, "where does the melee stand" — the classic positioning gap.

WCL records per-actor coordinates (the website replay works; `boundingBox` is populated per fight), but
the **public client-credentials API withholds the per-actor stream** — all 17k events on a Hydross kill
carried zero `x`/`y`. Confirmed dead-end on the current auth path (2026-06-01).

**One unopened door:** the user-OAuth flow (authorization-code, needs a one-time browser login) *might*
expose the stream. Spike only if positioning becomes a real priority — don't re-investigate the
client-credentials path.

---

## BACKLOG: Layout audit — Overview tab

> Go through the Overview tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Composition tab

> Go through the Composition tab and audit layout/organization. Does it make sense? Should things be
> moved around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Prep tab

> Go through the Prep tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Execution tab

> Go through the Execution tab and audit layout/organization. Does it make sense? Should things be
> moved around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Trash tab

> Go through the Trash tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?
