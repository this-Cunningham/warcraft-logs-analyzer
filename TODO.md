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

---

## TODO: Truncate guild names past 13 characters with "…" everywhere in the report

> Any references to the guild names across the report should truncate the guild name past 13 chars with ...

Layout robustness. Long guild names break column widths and delta labels, making the report harder to scan. A consistent 13-char truncation with an ellipsis keeps the layout stable for any guild pairing without losing recognizability. Apply uniformly — headers, table column labels, inline references — so no part of the report wraps or overflows unexpectedly.

---

## TODO: Write a clear, concise description for the "Rotation Matches Benchmark" metric

> Clear concise description for "rotation matches benchmark."

The label surfaces in the report but a raid leader reading it cold needs to know immediately what "matches" means and what they should do if it doesn't. Write a short, plain-language description — what the metric measures, what the benchmark is, and what a gap implies for the player's rotation. Self-explanatory is a soul requirement; an unlabeled or poorly-explained metric is a failure of that standard.

---

## TODO: Rotation — Ability Mix: add horizontal bars, delta in the middle

> Rotation — Ability Mix tables for each class/spec should render horizontal bars in this layout:
> `our value → our bar → ability name → delta value → benchmark bar → benchmark value`
> (maintain existing sort). I want to see what it's like putting the delta value in the middle
> next to the ability name.

Visual upgrade that puts the gap where the eye lands. The ability name is the natural anchor — placing the delta right beside it means a leader scanning row-by-row sees the gap at the same moment they read the ability, without having to track across to a far-right column. The mirrored bar layout (our bar left, benchmark bar right, meeting at the name) also makes magnitude comparison immediate. Maintain existing sort order; this is a layout/rendering change only.

---

## TODO: Fix font style on "Abilities Interrupted — by spec" explanatory copy

> This copy doesn't match the other font styles for "additional explanation context" — Abilities Interrupted — by spec: "Each interrupted enemy cast and which specs kicked it, ours vs the benchmark — so you can see e.g. 'benchmark kicked it with Fire Mages, you used Ele Shaman.' Descriptive: a different kick assignment isn't better or worse, it reveals how each raid covers interrupts."

Consistency fix. The explanatory/context copy under this section is rendering in a different style than the equivalent explanatory text elsewhere in the report. Align it to the standard style used by other sections' additional-context copy so the visual language is uniform throughout.
