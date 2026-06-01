# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

---

## Open question: language / runtime — Node or Python instead of PowerShell?

> Should this be written in Node/Python instead of PowerShell? Can it be written in
> those and still work? Are those better than PowerShell (my guess is probably)?

Notes / context to evaluate:
- **Can it work in Node/Python?** Yes, cleanly. The whole pipeline is just: OAuth token →
  GraphQL POST → shape JSON → inject into a static HTML template. None of that is
  PowerShell-specific. The **report itself wouldn't change at all** — it's already a
  self-contained HTML file with vanilla JS; only the fetch/build scripts would be rewritten.
- **Why PowerShell today:** it was the zero-install path — this Windows box has no Node or
  working Python, but PowerShell + `curl` are built in. Good for "just works," less good for
  ergonomics (the UTF-8/encoding gotchas, verbose JSON handling, `ConvertTo-Json` single-element
  array unwrapping we had to defend against).
- **Likely better in Node/Python because:** nicer JSON handling, real package ecosystem (a GraphQL
  client, a templating lib), easier testing, and a clearer path *if* this ever becomes a hosted
  web app (see the tab-restructure note + the original "do we need Next.js" discussion).
- **Cost of switching:** requires installing a runtime (and for Node, `npm install`). Decide based
  on where the project is headed (static report generator → PowerShell is fine; interactive/hosted
  app → Node/Next).
- Decision criteria mirror the earlier architecture chat: stay simple while it's a "generate a
  shareable report" tool; switch when it becomes an "interactive product."

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
- ✅ **Death timeline & cause** (`Deaths` table): DONE 2026-05-31 — per-boss Deaths sub-tab shows
  who died, their spec, the killing blow, and when (sec into fight). Per-pull-vs-execute framing
  could still be layered on via phase correlation.
- ✅ **Interrupts: kicks landed vs missed** (`intr.missedCasts[]`): DONE 2026-05-31 — the Interrupts
  sub-tab now has a "Casts That Went Off Un-kicked" section (kicked / went-off per ability, hostile
  casters only). A per-*player* interrupter view is still open.
- **Flask / consumable coverage per player**: raid-aggregate flask presence is visible, but
  per-player needs a per-source buff query or event scan.
- **Healer mana / OOM + resource usage** (`Resources` table).
- ✅ **Phase timing** (`phaseTransitions` on fights): DONE 2026-05-31 — per-boss Phases sub-tab shows
  each phase's duration + share of the kill with a delta vs the benchmark (Vashj P1/P2/P3, etc.).
- **Gear / item-level gaps**: ⚠️ partial — raid **avg item level** now shown on the Enchants tab
  (DONE 2026-05-31). Still open: *per-player* ilvl vs the benchmark's same-role players; biggest BiS gaps.
- ✅ **Dispels** (`Dispels` table): DONE 2026-05-31 — per-boss Dispels sub-tab compares which enemy
  auras each raid removed, with counts.
- **Positioning** (x/y from events): advanced/heavy to render, but possible (spread/stack mechanics).
- Keep asking the meta-question every pass: *what modality of data haven't we looked at yet?*

---

## TODO: restructure top-level tabs — ✅ DONE 2026-05-31 (per-player inspection still open)

> Break the top level of "Dive Deeper" into other tabs. Raid comp all the way down to
> per-player inspection should be a separate whole tab next to Dive Deeper. We can probably
> rename Dive Deeper to be about composition, then create a tab next to it that's like "Bosses".

**Done (2026-05-31):** "Dive Deeper" split into four top-level tabs —
**Overview | Composition | Enchants | Bosses**. Composition holds raid composition + buff
coverage; the enchant/gem audit got its own **Enchants** tab (rather than nesting under
Composition); **Bosses** holds Clear Efficiency + Output Quality + Per-Boss Execution. No
sections or data were dropped in the move. The Enchants audit was also brought onto the
**shared-boss roster** so its player count matches Composition (was previously computed over
all kills), and a latent double-count of players who appear in two role buckets (e.g. a feral
who both tanked and DPS'd) was deduped.

**Still open:** per-player inspection — drill into a single raider's gear/enchants/parses/
activity ("all the way down to per-player inspection"). The Composition/Enchants tabs are
per-raid aggregates, not a per-player drilldown, so this remains the outstanding piece.

Original plan (for reference):
- Promote the per-boss content into its own top-level **"Bosses"** tab. ✅
- Rename **"Dive Deeper" → "Composition"**, holding raid composition + buff coverage. ✅
- Resulting top-level tabs: shipped as four (**Overview | Composition | Enchants | Bosses**). ✅
- Resolved questions:
  - **Clear Efficiency** and **Output Quality** (cross-boss summaries) → placed on **Bosses**.
  - The enchant/gem **Audit** → its own **Enchants** tab.
  - Growing client-side JS may still justify inlining a tiny view lib (Preact + htm) if a
    per-player drilldown adds tabs-within-tabs. Still keep single-file output.

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
