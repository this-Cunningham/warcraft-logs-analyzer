# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: more / better insights — what other data can we leverage?

> What else can we do to give better insights and ability to improve our raid? What other
> data is available? What little nooks and crannies of data can we leverage to find
> gaps / areas for improvement?

_(to be replaced)_

---

## TODO: character-vs-character comparison (not just raid-vs-raid)

> Instead of comparing two raids, add the ability to compare a **specific character** to
> **another character** for a given boss fight.

Why: the current report is raid-vs-raid aggregates. The deepest coaching is 1:1 — line up our
mage against their mage (or the boss's best-parsing mage) on the same encounter and see exactly
where the gap is. Overlaps with the existing "per-class rotation / ability-mix" and "per-player
inspection" backlog notes.

Sketch / data already proven available:
- Pick a boss (shared `encounterID`) + a character from each side.
- Pull per-character for that fight: `dd.abilities[]` (ability-by-ability damage mix — already
  fetched today), `Casts` (rotation/CD usage + cast counts), `activeTime` (downtime), parse
  percentile (`rankings`), gear/enchants/gems (`playerDetails.combatantInfo`), deaths.
- Render a side-by-side: parse, DPS, activity, ability mix (which spells, what share), CD fire
  counts, gear deltas. Highlight the biggest contributors to the gap.
- Could also compare our character to the **global best** same-spec parse via
  `worldData.encounter(id).characterRankings` rather than a second report.
- Open design Qs: where does it live — a new top-level tab ("Players"/"Head-to-Head"), or a
  drilldown launched from a roster row? How to pick the opponent (manual, or auto-match same
  spec)? Single boss at a time, or across all shared bosses?

---

## DONE: "Trash" tab — per-trash-pack panels + intra-pack kill order

Shipped. The **Trash** tab has five sections — Trash at a Glance, What's Killing Us on Trash,
Kill Priority by Mob Type (descriptive), Crowd Control on Trash (descriptive), and a single-raid
Pack-by-Pack drill-down with intra-pack kill order, deaths, and per-mob CC. Hybrid comparison
(benchmark on night-totals + mob-type; per-pull detail ours-only). On by default. See SKILL.md
for the data sources and caveats.

**Next-pass ideas surfaced while building it** (not yet done):
- Feed the big trash-deaths gap (e.g. 48 vs 11) into the Overview **Biggest Gaps** scorecard — it's
  a high-leverage gap that currently only lives in the Trash tab.
- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier.
