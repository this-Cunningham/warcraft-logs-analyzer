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

---

# Gap-analysis build list (2026-05-31 brainstorm)

Prioritized batch of "find the big gaps across dimensions" features. Goal: turn the report from
a data dump into a coaching tool that points at the lowest-hanging fruit. Ordered by payoff/effort.
Most of Tier 1 needs **zero new API calls** — it re-slices data `fetch_report.py` already pulls.

## TODO: consumable coverage panel (flask / food / elixir / drums / potions) — **DONE**

> The #1 bad-guild fix. Verified fully derivable from the `Buffs` table we already fetch for every
> boss — auras include `Flask of Relentless Assault`, `Well Fed`, `Drums of Battle`,
> `Greater Arcane Elixir`, `Spellpower Elixir`, `Destruction` (potion), etc., each with `totalUses`.

- Per consumable category, `totalUses` ≈ raiders who used it (flask persists through death → ~1
  application/player; food re-eaten on death so cap at roster size). Raid-aggregate, not per-player
  exact — label honestly.
- Render on the prep tab (rename "Enchants" → "Prep"): coverage cards (flask / food / elixir / drums)
  ours vs theirs + delta, with a per-consumable detail table.
- Caveat: Buffs table can't dedupe flask-vs-elixir per player; flask users is the headline proxy.
- **Also DONE — Per-Player Consumables matrix** (ours only, sorted worst-first): one row per raider,
  shared bosses across the top, F·B·G·Fd·P sub-columns per boss (flask / battle elixir / guardian
  elixir / food / combat potion) + a Prep summary column (consumed/played). "Consumed" = flask OR a
  battle+guardian elixir pair (a lone elixir isn't enough). Per-player data comes from the Buffs table
  scoped by `sourceID` (`_fetch_per_player_buffs` → `consumes-<enc>.json` → `per_player_consumables`),
  NOT events — flask/food/elixir are applied pre-pull so they generate no in-fight events, and
  `combatantInfo.auras` is empty in TBC.
- **Consumables classified by SPELL ID, not name** (`FLASK_IDS`/`ELIXIR_BATTLE_IDS`/
  `ELIXIR_GUARDIAN_IDS`/`POTION_IDS`): WCL renames buffs to their effect (Flask of Supreme Power →
  "Supreme Power", Elixir of Major Shadow Power → "Major Shadow Power"), so name-matching misses them
  and catches false positives (scrolls "Strength"/"Agility", a +125 "Spell Power" proc). Ids are mined
  from the report data (guid is on every aura; benchmark carries the full set); only the battle/guardian
  label needs a one-time Wowhead check. Name fallback covers unmapped "Flask of …"/"Elixir of …".

## TODO: "Biggest Gaps" scorecard at top of Overview

> Highest-leverage framing change. Pure presentation over metrics we already compute.

- One ranking function over every tracked dimension (parse, kill-time, deaths, overheal, activity,
  buff/debuff gaps, enchant gaps, consumable gaps): normalize each delta, sort, show top 5–7 as
  plain-language cards with a severity color driven by distance from benchmark.
- Convert each to an actionable sentence ("Only ~4/25 ate food; benchmark ~24"). Reuse the
  `impact` string pattern from `PROVIDER_CHECKS`.

## TODO: "what's killing us" — deaths aggregated by cause across the tier

> We already capture `killedBy` per death. Aggregate across all shared bosses → ranked
> "Toxic Spore killed your raid 11×; benchmark 0." Repeated killing blows = a mechanic you fail.

- Free re-slice. Death records also carry `damage`, `events`, `overkill`, `deathWindow` — enough to
  show the damage lead-up, not just the final blow. Surface as a raid-level "top death causes" table
  + ours-vs-theirs.

## TODO: per-spec DPS gap on each boss (lowest-hanging-fruit spec) — *(user idea, sharpened)*

> User's ask: "we had 3 mages (names + dps) vs benchmark's 2 mages (names + dps) for this boss."
> Sharper framing for "which spec to target": rank specs by the **per-capita DPS gap** to the
> benchmark's same spec, biggest deficit first — that floats the lowest-hanging-fruit spec to the top.

- Bucket the `dd` table entries (already fetched for shared bosses) by spec via the roster's
  name→spec map (`primary_spec_map` already exists). Compute avg DPS per spec, ours vs benchmark
  same spec, sorted by deficit.
- Render as a ranked spec-gap list per boss; expand a row to show the individual players + their DPS
  on both sides (this is spec-aggregate, not 1:1 player comparison, so it stays inside the
  "raid across dimensions" goal).
- Handle roster-count mismatches (3 vs 2 mages) by comparing **average DPS per player of that spec**,
  not raw totals, and showing both counts. Note specs only one side brought.

## TODO: raid DPS / HPS per boss + total

> Direct explanation of the kill-time gap; we don't show it. Sum `dd`/`heal` totals ÷ duration.

- "Raid DPS on Kael: 18.2k vs 31.4k." Add as a hero metric on the Overview boss cards next to
  kill-time, and to the Output Quality section.

## TODO: damage contribution by class/role + role-level ilvl

> `dd` entries carry `type` (class) and per-player `itemLevel`. Aggregate to "% of raid damage per
> class" and compare — surfaces whether melee, casters, or everyone is dragging. Role-level ilvl
> (your healers vs theirs), not just one raid average.

## TODO: wipe / attempt counts per boss (one cheap new query)

> Only real new fetch in this batch. Add `fights(killType:Encounters)` and count non-kills per
> encounter → "you wiped 12× on Kael; they one-shot it." Big execution/progression signal.

## TODO: cooldown usage counts (raid-level)

> `Casts` table filtered to CD ability IDs (Bloodlust, Combustion, Recklessness, trinkets, Power
> Infusion, racials) → "3 Heroisms fired where 6 were possible." (Also tracked in the insights
> section above; promoted here as a concrete build item.)
