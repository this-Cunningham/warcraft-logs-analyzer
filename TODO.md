# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

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

## TODO: Fix inconsistent font on per-spec timeline tab titles — audit report-wide

> this font is off from normal table title label fonts BeastMastery Hunter — DPS over time, ours vs benchmark, audit for others like this

The "Beast Mastery Hunter — DPS over time, ours vs benchmark" tab title renders in a different font style than standard section/table title labels elsewhere in the report. These per-spec timeline tabs were added recently and appear to have inherited a different style. Fix the offending title and audit all dynamically-generated tab/section labels (per-spec DPS, per-spec HPS, any other generated titles) to ensure they match the report-wide title font. Consistent typography is a readability baseline — a mismatched font signals "rough edge" and undermines trust in the report at a glance.

---

## TODO: Tighten in-report table/section descriptions — concise without losing meaning

> simplify and make beefy table/context descriptions more concise while maintaining meaning

The explanatory copy under tables and sections has grown verbose. The soul calls for leaders to get the headline gaps in seconds; long descriptions create friction before they reach the data. Trim each one to the minimum that answers "what am I looking at and what does a gap here mean?" — cut throat-clearing, restate only what isn't obvious from the table itself, keep any caveat that affects how to read the numbers. No meaning lost, just less to wade through.

---

## TODO: Tighten benchmark guild name truncation to 8 characters

> truncate benchmark guild name even down to 8 chars

The current 13-char limit still lets the benchmark guild name crowd column headers and delta labels — particularly bad for the benchmark side, which appears as a column label in many side-by-side tables. Dropping to 8 chars keeps headers tight and layout stable across any guild name. The 8-char rule should apply to the benchmark name specifically (or both names if that's cleaner); the existing truncation logic just needs its cap lowered.
