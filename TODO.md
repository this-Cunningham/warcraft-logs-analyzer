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

---

## TODO: Throughput Potions — By Spec: restrict comparison to overlapping specs only

> Throughput Potions — By Spec — does this compare against specs that were not overlapping in our raids? If so we can't be doing this.

Data-integrity issue. If the By Spec view compares potion usage rates for specs that appear in the benchmark but not in our raid (or vice versa), the delta is meaningless — apples to oranges. The comparison must be gated to specs present in *both* raids. Any spec unique to one side should be omitted from the comparison entirely rather than shown as a misleading gap. Audit whether the current implementation already enforces this; if not, it's a silent integrity violation the soul explicitly prohibits.

---

## TODO: Remove or replace "Throughput Consumable Choices" section

> This section is useless — Throughput Consumable Choices.

If it doesn't reveal an actionable gap it fails the soul's first test. Evaluate whether the section is a scoreboard (counts without a lever) or a data dump that WCL already shows better. If no clean gap-revealing reformulation exists, remove it. If there's a salvageable insight — e.g. wrong potion choice by spec vs. benchmark — define that narrowly and rebuild; otherwise cut.

---

## TODO: Raid Composition & Buff Coverage — "Provided by" as first column

> In the Raid Composition & Buff Coverage table, put "Provided by" as the first column.

A scan-order fix. Leaders read left-to-right; the provider (which class/spec covers the buff) is the actionable lever — knowing *who* provides the buff is the thing a leader acts on when a coverage gap exists. Moving it first keeps the highest-value identifier at the anchor position before the coverage columns.
