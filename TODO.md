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
