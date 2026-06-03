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

## ✅ DONE: In-Combat consumables matrix — gray "✕" for empty slots

> In Per-Player Consumables — In Combat, in that matrix — any slot that's not filled with a number, can we fill with a gray "✕" like in the matrix above?

Empty cells currently read as ambiguous — is that zero uses, or a slot that doesn't apply? A gray ✕ makes the absence explicit, matching the visual language already used in the Prep matrix above. Consistent empty-state treatment lets a leader scan the full row and immediately see the gaps without wondering if a blank means "fine" or "missing."

---

## ✅ DONE: Fix Flasked / Elixir Pair display in Per-Player Consumables — Prep

> something wrong with Flasked / Elixir Pair section when compared to this matrix Per-Player Consumables — Prep

The Flasked / Elixir Pair columns in the Per-Player Consumables — Prep section appear to disagree with or duplicate data from the consumables matrix. Gap: if a player shows as flasked in one view but not the other, a raid leader can't trust either. Investigate whether the two views are drawing from the same data pass and whether the battle+guardian elixir pairing logic is consistently applied in both places.

---

## ✅ DONE: Throughput Potions — By Spec: restrict comparison to overlapping specs only

> Throughput Potions — By Spec — does this compare against specs that were not overlapping in our raids? If so we can't be doing this.

Data-integrity issue. If the By Spec view compares potion usage rates for specs that appear in the benchmark but not in our raid (or vice versa), the delta is meaningless — apples to oranges. The comparison must be gated to specs present in *both* raids. Any spec unique to one side should be omitted from the comparison entirely rather than shown as a misleading gap. Audit whether the current implementation already enforces this; if not, it's a silent integrity violation the soul explicitly prohibits.

---

## ✅ DONE: Remove or replace "Throughput Consumable Choices" section

> This section is useless — Throughput Consumable Choices.

If it doesn't reveal an actionable gap it fails the soul's first test. Evaluate whether the section is a scoreboard (counts without a lever) or a data dump that WCL already shows better. If no clean gap-revealing reformulation exists, remove it. If there's a salvageable insight — e.g. wrong potion choice by spec vs. benchmark — define that narrowly and rebuild; otherwise cut.

---

## ✅ DONE: Raid Composition & Buff Coverage — "Provided by" as first column

> In the Raid Composition & Buff Coverage table, put "Provided by" as the first column.

A scan-order fix. Leaders read left-to-right; the provider (which class/spec covers the buff) is the actionable lever — knowing *who* provides the buff is the thing a leader acts on when a coverage gap exists. Moving it first keeps the highest-value identifier at the anchor position before the coverage columns.

---

## ✅ DONE: Truncate guild names past 13 characters with "…" everywhere in the report

> Any references to the guild names across the report should truncate the guild name past 13 chars with ...

Layout robustness. Long guild names break column widths and delta labels, making the report harder to scan. A consistent 13-char truncation with an ellipsis keeps the layout stable for any guild pairing without losing recognizability. Apply uniformly — headers, table column labels, inline references — so no part of the report wraps or overflows unexpectedly.

---

## ✅ DONE: Write a clear, concise description for the "Rotation Matches Benchmark" metric

> Clear concise description for "rotation matches benchmark."

The label surfaces in the report but a raid leader reading it cold needs to know immediately what "matches" means and what they should do if it doesn't. Write a short, plain-language description — what the metric measures, what the benchmark is, and what a gap implies for the player's rotation. Self-explanatory is a soul requirement; an unlabeled or poorly-explained metric is a failure of that standard.

---

## ✅ DONE: Rotation — Ability Mix: add horizontal bars, delta in the middle

> Rotation — Ability Mix tables for each class/spec should render horizontal bars in this layout:
> `our value → our bar → ability name → delta value → benchmark bar → benchmark value`
> (maintain existing sort). I want to see what it's like putting the delta value in the middle
> next to the ability name.

Visual upgrade that puts the gap where the eye lands. The ability name is the natural anchor — placing the delta right beside it means a leader scanning row-by-row sees the gap at the same moment they read the ability, without having to track across to a far-right column. The mirrored bar layout (our bar left, benchmark bar right, meeting at the name) also makes magnitude comparison immediate. Maintain existing sort order; this is a layout/rendering change only.

---

## ✅ DONE: Fix font style on "Abilities Interrupted — by spec" explanatory copy

> This copy doesn't match the other font styles for "additional explanation context" — Abilities Interrupted — by spec: "Each interrupted enemy cast and which specs kicked it, ours vs the benchmark — so you can see e.g. 'benchmark kicked it with Fire Mages, you used Ele Shaman.' Descriptive: a different kick assignment isn't better or worse, it reveals how each raid covers interrupts."

Consistency fix. The explanatory/context copy under this section is rendering in a different style than the equivalent explanatory text elsewhere in the report. Align it to the standard style used by other sections' additional-context copy so the visual language is uniform throughout.

---

## ✅ DONE: Fix font style on "Interrupt Success — Kicked vs Leaked" explanatory copy

> Same as above — "Interrupt Success — Kicked vs Leaked": "Per ability: kicked = interrupts you landed; leaked = interruptible casts that still went off un-kicked. A highlighted leaked count is a miss — lower is better, 0 leaked is ideal."

Consistency fix. The explanatory/context copy under this section is rendering in a different style than the equivalent explanatory text elsewhere in the report. Align it to the standard additional-context copy style so the visual language is uniform throughout. (Same fix as the Abilities Interrupted — by spec item above.)

---

## ✅ DONE: Abilities Interrupted — by spec: rework to grouped-row layout

> The current flat table (Ability Interrupted | Our Raid — kicked by | Benchmark — kicked by) isn't clear. Rework to: rows = interrupted spell name (grouped header), sub-rows within each group = one row per spec that kicked it, columns = "Kicked by spec" | "Our Raid" | "Benchmark". Long guild names in column headers also make it worse (see truncation TODO).

The current flat layout puts both raids' full spec lists in a single cell per row, making the comparison hard to parse. Grouping by interrupted spell as the primary row, with one spec-per-sub-row, lets a leader see at a glance "benchmark used Fire Mage for this cast, we used Ele Shaman" — the exact side-by-side that reveals how each raid's interrupt assignments differ. This is the actionable cut the section promises.

---

## ✅ DONE: All mirrored-bar tables — move delta to center, next to the name

> For all tables with the layout `value — bar — name — bar — value — delta (sorted)`, move the delta to be right next to the name in the center. Apply to ALL tables of this type.

This supersedes/generalizes the Rotation — Ability Mix item above. The delta is the signal; the name is the anchor — they belong together. Placing the delta beside the name means a leader reads the gap at the same moment they identify what it's for, without tracking to a far-right column. Apply consistently to every mirrored-bar table in the report so the pattern is uniform. The sort order (by delta) stays unchanged; this is a column-position change only.

Examples of tables with this layout: Boss Debuffs, Raid Buffs, Avg DPS / player by spec, and many more across the report. The *only* thing that changes is the location of the delta column (move it to the center next to the name) — nothing else about these tables changes.

---

## ✅ DONE: Per-spec DPS and HPS timeline tabs inside each boss panel

> In each boss panel under "Timeline": keep the existing "Raid DPS Timeline" as the first sub-tab (unchanged). Add additional sub-tabs named after each class/spec combo present in our raid — clicking one shows the same timeline graph but with our spec's DPS vs. the benchmark's same spec. Do the same for healing ("Raid HPS over time"). Color the tabs by class color.

The existing raid-level DPS/HPS timeline shows the full-raid aggregate, which obscures whether individual specs are running at benchmark pace through each phase. A per-spec tab lets a leader click e.g. "Fire Mage" and see immediately whether their Mage's output curve matches the benchmark Mage's — revealing ramp timing gaps, phase drop-offs, or sustained throughput deficits that the aggregate buries. The spec-tab coloring by class type makes the tab bar scannable at a glance.

Data integrity: only generate spec tabs for class/spec combos present in *both* our raid and the benchmark — a spec we ran but the benchmark didn't (or vice versa) has nothing to compare against, so showing it would be a misleading apples-to-oranges gap. Omit non-overlapping specs from the tab set entirely. (Same overlapping-specs rule as the Throughput Potions — By Spec item.)

---

## ✅ DONE: Per-boss timeline — add "Melee DPS" and "Ranged DPS" aggregate tabs

> On the new dps per spec over time per boss, also add additional tabs that are "melee dps" and "ranged dps" that aggregates all the specs over time per boss.

Alongside the per-spec Timeline tabs, two aggregate tabs sum the whole melee or ranged core's DPS over time, ours vs the benchmark — so a leader sees the group's combined ramp/sustain, not just one spec. Summed over the same (overlapping) DPS specs on both sides to stay apples-to-apples; melee/ranged classified by the existing `_is_melee` (Warriors/Rogues, Enh/Ret/Feral = melee; casters and hunters = ranged).

---

## TODO: Remove shaded-edge fade on scrolling tables

> undo the shaded edges of the scrolling tables you added recently

Visual regression fix. The fade/shadow applied to the left and right edges of horizontally-scrollable tables was meant to hint at overflow, but it obscures the data at the edges of the viewport — the opposite of the soul's "honest, at a glance" standard. Clean removal restores full-bleed readability without sacrificing the scroll affordance (the scrollbar itself is sufficient).

---

## TODO: Raid Summary "total kill time" — clarify label + audit Clear Efficiency apples-to-apples

> in raid summary total kill time, make it clearer labelled what that is, boss kill times?  Also double check CLEAR EFFICIENCY numbers are comparing apples to apples

Two integrity items in the same section. First: the "total kill time" label is ambiguous — a leader reading cold can't tell whether it's summed boss-combat time, wall-clock raid duration, or something else. Rename or subtitle it to make explicit what's being measured (e.g. "Total boss combat time" if that's what it is). Second: Clear Efficiency is a comparison metric, so the delta is only honest if both sides are measured over the same set of bosses. If one raid killed bosses the other didn't, summing kill times across unequal boss sets produces a meaningless gap. Verify the implementation scopes both sides to shared bosses only — the soul's data-integrity bar ("cut it unless it's clean") makes this non-negotiable.

---

## TODO: Convert remaining sections to mirrored-bar layout — delta in center, context columns on the right

> plz convert these tables to horizontal mirror bar tables with label and delta in middle, any tables mentioned with an extra context table, just maintain that all the way on the right
>
> BUFF & DEBUFF COVERAGE GAPS
> EARLY AGGRO — THREAT PULLS — keep extra column on right for earliest
> ADD CONTROL — KILL SPEED
> WHAT'S KILLING US ON TRASH
> Melee deaths — by mob

Five sections that haven't yet been converted to the mirrored-bar pattern already applied across most of the report. Unifying them closes the visual inconsistency: delta lands right next to the name (where the eye already is), mirrored bars make magnitude comparison instant, and the layout reads as "comparison" rather than "wall of numbers." For sections that carry an extra context column — specifically the earliest-pull timestamp in Threat Pulls — that column stays anchored on the right as additive context; it is not part of the mirrored comparison and shouldn't move.

---

## ✅ DONE: New "Bosses" top-level tab — consolidate all per-boss content

> Build a new top-level tab named "Bosses" (next to "Trash") that becomes the single home for all boss-specific content. Inside it:
> - **One sub-tab per boss.** Each boss sub-tab shows that boss's full content from the current "Per-Boss Execution" panel, and directly below the panel, that same boss's parse table from the current "Boss-by-Boss" section.
> - **Promote "Per-Boss Execution"** out of its current location into these per-boss sub-tabs.
> - **Move "Boss-by-Boss"** (kill time, raid DPS/HPS, parse, deaths, attempts, both rosters side by side) out of Overview into these same per-boss sub-tabs.
> - **Boss panel summary stats** (Raid DPS, DPS activity, Healer overheal, Dmg taken/s ex-tanks) should spread evenly across the full panel width rather than bunching.
> - **Boss portrait image** (research item): look into whether WCL or Blizzard API exposes a boss portrait/icon asset; if so, render it to the left of the boss name in each sub-tab header.

Navigation architecture change that consolidates a scattered story. Today boss-specific analysis is split across Overview (Boss-by-Boss picker) and a buried Per-Boss Execution panel. Unifying everything under one "Bosses" tab with a sub-tab per fight gives a leader a single, first-class per-fight lens: pick a boss, see its execution panel and its parse table together. Overview slims down to the raid-level summary it's meant to be.

Sub-points to carry through:
- **Even-width summary stats** — the headline stats are the first thing a leader sees per boss; full-width distribution gives each equal visual weight and scans cleanly left-to-right.
- **Boss portrait (research) — SKIPPED.** The WCL GraphQL `Encounter` type exposes only `journalID` (no image/icon URL); a portrait would require Blizzard's separate Game Data API, which this tool isn't set up for. Per the maintainer, skip when it isn't in WCL GraphQL.

(Note: the separate per-spec DPS/HPS timeline-tabs item below is a distinct feature — timeline graphs inside each boss panel — and is intentionally tracked on its own.)
