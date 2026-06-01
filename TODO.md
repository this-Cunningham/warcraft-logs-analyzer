# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

---

## TODO: more / better insights — what other data can we leverage?

> What else can we do to give better insights and ability to improve our raid? What other
> data is available? What little nooks and crannies of data can we leverage to find
> gaps / areas for improvement?

Concrete candidates already identified from API exploration:
- **Cooldown usage** (`Casts` table, filter to CD ability IDs): did players actually fire
  Combustion / Recklessness / Death Wish / trinkets / Power Infusion / racials — counts vs benchmark.
- **Per-class rotation / ability-mix** (`dd.abilities[]` — already fetched): compare one of our
  mages to the benchmark's best mage, ability by ability. Deepest *individual* coaching tool.
- **Flask / consumable coverage per player**: raid-aggregate flask presence is visible, but
  per-player needs a per-source buff query or event scan.
- **Healer mana / OOM + resource usage** (`Resources` table).
- **Gear / item-level gaps**: raid **avg item level** is shown on the Enchants tab. Still open:
  *per-player* ilvl vs the benchmark's same-role players; biggest BiS gaps.
- **Positioning** (x/y from events): advanced/heavy to render, but possible (spread/stack mechanics).
- Keep asking the meta-question every pass: *what modality of data haven't we looked at yet?*

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

## TODO: order bosses by our kill order + show kill order on the Bosses tab

> Sort the boss panels by the order **raid 1 (ours)** killed them, and show the boss kill
> order at the top of the "Bosses" tab.

Notes:
- `fights.json` already carries `startTime` per kill, so kill order = bosses sorted by our
  `startTime`. Today the per-boss list follows the `commonIds` hashtable order, which isn't
  guaranteed to be chronological.
- Build a chronological index from `OursDir`'s fights (shared bosses only) and order `perBoss`
  by it. Bosses ours killed that the benchmark didn't are excluded already (shared-only).
- Add a compact "kill order" strip at the top of the Bosses tab: `1. Lurker → 2. Leotheras →
  3. Karathress → …` (our order). Could show our kill time next to each.
- Tiny open Q: if the two raids killed shared bosses in a different order, we anchor on **ours**
  (the strip is our run); optionally annotate where theirs diverged.

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
