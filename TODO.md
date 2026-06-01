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

## TODO: "Trash" tab — per-trash-pack panels + intra-pack kill order

> Add a "Trash" tab that shows each trash pack, similar to the boss panels. Different stats per
> pack than bosses. Especially interested in **kill order within each pack** — "Mob X was killed
> first within trash pack group Y".

Feasibility / data exploration needed (not yet confirmed):
- `report.fights(killType:Trash)` returns trash segments — need to check what WCL groups as a
  "pack" vs individual mobs, and whether segment boundaries line up with how players perceive packs.
- Per-mob death/kill timing: `Deaths`/`DamageDone` tables filtered to trash fightIDs, or an event
  scan for enemy `death` events to get per-mob kill timestamps → derive intra-pack kill order.
- Likely-useful per-pack stats (different from bosses): clear time, # mobs, mob kill order +
  timestamps, damage taken during the pack, deaths, CC/interrupts used, lust used on trash (waste?).
- Open Qs: how to define/segment a "pack" (WCL trash segments, time-gap clustering, or pull
  markers)? How much does this bloat fetch/points (trash is a lot of fights)? Probably gate it
  behind a flag so the default report stays lean. Verify the whole thing is even cleanly derivable
  before building — this one's a research spike first.

---

## TODO: redesign "DPS by Spec" in boss panes — gap-sorted bar chart

> Update "dps by spec" within each boss pane to look more like the "Damage Contribution by Class"
> design, but for spec. Sort so the specs we can most improve (biggest gap vs benchmark) appear at
> the top. (Don't surface our missing specs here — that composition signal belongs in the
> composition section; see the TODO below.)

Why: the current layout treats all specs as equally interesting. Sorting by improvement headroom
(our spec's share vs their spec's share, descending gap) makes the section pull its weight — a
leader scans the top row and immediately sees the highest-leverage spec contribution gap.

Design notes:
- Borrow the horizontal bar chart framing already proven in "Damage Contribution by Class."
- Two bars per spec row (us vs them), like the class section — so the visual grammar is consistent
  across the boss pane.
- Sort descending by gap: specs where we contribute the least relative to the benchmark rise to top.
- Keep the focus on specs both sides actually field — whether a side is *missing* a spec entirely is
  a roster-composition story, surfaced in the composition section, not framed as a per-boss DPS gap.

---

## TODO: highlight missing specs in the composition section

> In the "composition" section where we already show our raid comp specs vs theirs, highlight the
> specs we're missing relative to the benchmark (and, the other direction, specs we bring that they
> don't).

Why: which specs each side fields is a real, actionable composition gap — "they run a Shadow Priest
for replenishment, we don't" is a lever a leader can pull next week. The composition section is
already the honest home for ours-vs-theirs spec rosters, so the missing-spec callout belongs there
rather than being smuggled into a per-boss DPS chart (which would falsely frame an absent spec as a
contribution shortfall).

Design notes:
- Annotate specs present for them but absent for us ("missing") and, optionally, specs present for
  us but absent for them — visually distinct so the missing-spec gap reads at a glance.
- Stay neutral-analyst: state the composition delta; let the leader judge whether to recruit/respec.
- Open Q: do we interpret *why* a missing spec matters (e.g. flag lost raid buffs/debuffs like
  replenishment, Misery, Heroism source) or just show the roster delta? The former is more
  actionable but needs a spec→buff knowledge table; the latter is honest and cheap.
