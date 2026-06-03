# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

_No open items — the last pass shipped the Interrupts ability-first refactor, the
Add Control kill-speed rework, the Rotation DPS/Healer tabs, the in-combat
consumables matrix (worst-first sort + green count numbers), the throughput-potion
gap, the Clear Efficiency shared-zone scoping fix, trash killing-blow mob names +
melee breakdown, the chain-pull view, the Crowd Control summary-table cut, the
flask/elixir-pair coverage fix, and the cloud startup script._

## TODO: In-Combat consumables matrix — gray "✕" for empty slots

> In Per-Player Consumables — In Combat, in that matrix — any slot that's not filled with a number, can we fill with a gray "✕" like in the matrix above?

Empty cells currently read as ambiguous — is that zero uses, or a slot that doesn't apply? A gray ✕ makes the absence explicit, matching the visual language already used in the Prep matrix above. Consistent empty-state treatment lets a leader scan the full row and immediately see the gaps without wondering if a blank means "fine" or "missing."

---

## TODO: Fix Flasked / Elixir Pair display in Per-Player Consumables — Prep

> something wrong with Flasked / Elixir Pair section when compared to this matrix Per-Player Consumables — Prep

The Flasked / Elixir Pair columns in the Per-Player Consumables — Prep section appear to disagree with or duplicate data from the consumables matrix. Gap: if a player shows as flasked in one view but not the other, a raid leader can't trust either. Investigate whether the two views are drawing from the same data pass and whether the battle+guardian elixir pairing logic is consistently applied in both places.
