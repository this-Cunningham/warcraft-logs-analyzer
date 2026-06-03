# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: Interrupts — refactor to ability-first with specs nested

> In the Abilities Interrupted section, nest the kicking specs under each ability, ours vs benchmark —
> "benchmark used Fire Mages to kick X, we used Ele Shaman."

Under each interrupted ability in the Abilities Interrupted list, show which specs handled it and how
many kicks (counts preserved), ours vs benchmark side by side. Descriptive (like
Dispels — a different spec assignment isn't inherently better/worse, but reveals strategy differences).
Data already fetched: Interrupts table `details[]` has per-player kick counts per ability; join with
`primary_spec_map` to bucket by spec. No new fetch needed.

---

## TODO: Enemy Targets — Engagement & Survival — find better insights or cut

> The current insights from this data are not useful or interesting. Find more useful insights to derive
> from this data, or remove the section.

The underlying data (per-enemy first-appearance time, survival duration, ours vs benchmark) may have
something in it — but the current view doesn't surface it. What meaningful gap can actually be read from
enemy engagement timelines that a raid leader would act on?

---

## TODO: Rotation — Ability Mix: DPS / Healer tab + all overlapping specs + collapse-on-match

> Split Rotation — Ability Mix into a DPS tab and a Healer tab; show every spec both raids fielded;
> collapse specs where the cast mix barely differs and show a green success label instead.

Same data source (Casts table) and same descriptive framing — cast share per ability, ours vs benchmark,
biggest divergence first. Healer spell priority is a real coaching lever (e.g. Holy Priest over-relying
on Flash Heal vs Greater Heal). Tab toggle keeps the view lean (same pattern as Kill Order / Crowd
Control in the Trash tab). `rotation_buckets` already pulls the full Casts table — needs healer-role
filter unlocked and a second spec-bucketing pass.

For specs where `maxDiff` is below a threshold (TBD — maybe ≤5pp), collapse the panel and render a green
chip ("Rotation matches benchmark") so a leader can see at a glance which specs are fine and focus on the
ones that aren't. Expanded panels stay as-is for specs with real divergence.

---

## TODO: in-combat consumables matrix (second matrix, below the existing prep one)

> Add a second per-player matrix underneath the existing prep matrix — same shape, focused on in-combat
> consumables: combat potion, health potion, mana potion, healthstone. Don't touch the existing matrix.

Same structure as the existing prep matrix (rows = players sorted worst-first, columns = bosses, sub-columns
per consumable type, ✓/✗ cells). The "P" combat potion sub-column should move out of the existing matrix
into this new one (so the prep matrix becomes F · B · G · Fd only). Sub-columns in the new matrix:
**P** (combat potion) · **HP** (health potion) · **MP** (mana potion) · **HS** (healthstone).

Data source is the same Buffs aura table scoped by `sourceID` (`consumes-<enc>.json`) — health/mana pots
and healthstones should appear as buff auras with `totalUses`; spell IDs need confirming from live data.
Healthstone availability is warlock-dependent — flag "no warlock in raid" rather than marking every player
red when none were present.

---

## TODO: throughput consumable choices — potion count gap + type breakdown by spec

> More comprehensive breakdown on throughput potions — "you popped 17 less potions on boss fights";
> per-spec breakdown ("rogues used 21 more potions than your rogues"); surface which types top guilds use.

Two angles:

1. **Potion count gap (ours vs benchmark, per spec):** total combat potion activations across shared
   bosses, bucketed by spec, ours vs benchmark. "Rogues: 21 more pots" is a concrete, actionable gap at
   the spec grain — raid-level coaching, not per-player. The benchmark is the discovery mechanism for
   which throughput potions matter (no hardcoded assumptions) — mine spell IDs from the benchmark's buff
   auras, the same way `FLASK_IDS` etc. were built. Data already fetched (`consumes-<enc>.json` per-player
   buff auras + the Casts table for in-fight pot casts).

2. **Which throughput potions (flask + battle elixir choices):** surface WHICH specific buff players are
   using, so a leader can see DPS on survival flasks vs throughput ones. The existing matrix classifies by
   category; this extends to the specific buff name within each category. Benchmark-first: the top guild's
   buff auras reveal the meta choices without us having to hardcode them.

---

## BUG: Clear Efficiency — wall-clock not scoped to shared zone

> Clear Efficiency is not comparing apples to apples — the benchmark may have run 3 raids in the time
> we ran one; wall-clock and out-of-boss time need to be scoped to the shared encounters only.

Currently uses the full report wall-clock (first pull to last kill across the entire night). If the
benchmark guild's report covers SSC + TK + Gruul but ours covers only TK, the comparison is meaningless.
Fix: scope wall-clock and derived values (out-of-boss time, clear efficiency) to the time window
spanning only the shared bosses — from the first pull of a shared encounter to the last kill of a shared
encounter, on each side independently. Audit all other night-total or report-wide metrics nearby for the
same issue — any value computed from the full report window rather than the shared-boss window is suspect
when the two reports cover different raid zones.

Also investigate **Trash at a Glance** for the same issue — pull count, clear time, and deaths are
already zone-scoped to the shared zone, but if one raid did more optional pulls within that zone the
pull count comparison may still not be apples-to-apples. Deaths are the clean signal; pull count and
clear time should be labeled or treated as rough proxies if the scoping can't be made exact.

---

## TODO: What's Killing Us on Trash — mob name on ability + melee sub-breakdown

> Show the mob name in parens next to each killing ability ("Grievous Bite (Greyheart Spellbinder)");
> for "Melee" deaths, show a sub-section listing which mobs' melee are doing the killing.

"Melee" as a killing blow is opaque — knowing which mob killed people points directly at a CC, kiting,
or tank-positioning fix. Named abilities benefit too ("Arcane Bolt" is more actionable as "Arcane Bolt
(Greyheart Spellbinder)"). The death entries already carry a `fight` id and killing-blow name; the
source mob actor should be available from the death event's source field joined against `masterData`
actors. Melee sub-breakdown groups "Melee" deaths by source mob name, ours vs benchmark, biggest delta
first — same ranked-by-payoff pattern as the main table.

---

## TODO: Trash — merged pull detection

> Is it possible to detect how many trash packs were combined on pulls — "they merged 3 trash packs
> where you merged none" — with a list of mobs in each merged pack?

A real efficiency gap: chain-pulling is a meaningful throughput lever. Feasibility question first —
WCL doesn't expose pack boundaries, only the mob roster of each fight segment. A "merged" pull could
be inferred when a segment's mob roster is notably larger or more diverse than a typical single-pack
baseline, but defining that baseline requires knowing what a single pack looks like for each zone.
The existing `trash.json` `enemyNPCs` (mob types + counts per segment) is the right starting point;
spike against a real report to see if merged pulls are detectable before building the view.

---

## TODO: Crowd Control tab — remove CC type summary table

> Remove the top overall CC summary table from the Crowd Control tab; keep only the per-mob breakdown.

The by-mob table ("which mob gets CC'd, by which CC, how often") is the actionable view — it tells you
specifically what to CC. The top summary (Polymorph N, Banish N, …) is redundant: the totals are
implied by the mob breakdown and add no signal a leader would act on. Cut it to keep the tab lean.

---

## BUG: Consumables Coverage — elixir pair not counted as "flasked"

> The Flask coverage card doesn't count a battle + guardian elixir combo as equivalent to a flask.

The per-player matrix already handles this correctly (`_elixir_type` + route-aware cell rendering treats a
flask OR a battle+guardian pair as "prepared"). The Coverage card at the top of Prep counts flask auras
only, so a player on a full elixir pair reads as un-flasked there — understating true coverage and
contradicting the matrix below it. Fix: apply the same "flask OR elixir pair" logic to the coverage
denominator/count that the per-player matrix already uses.

---

## TODO: Per-Player Consumables In Combat — sort worst-first + green numbers

> Within "Per-Player Consumables — In Combat": sort table rows so players with the highest potion counts
> are at the bottom (worst potion users float to the top). Also remove the green checkmark — just use
> green numbers instead.

Worst-first sorting matches the prep matrix pattern and puts the gap front-and-center — the leader's eye
lands immediately on the players using the fewest in-combat consumables. Green numbers over a ✓ keeps the
count visible in the cell while still signalling "good" — more informative than a binary pass/fail icon
and consistent with showing honest data (soul: never falsely precise; silence over noise). No new data
needed; purely a rendering and sort-order change on the existing in-combat matrix.

---

## TODO: Cloud startup script — pre-generate report from two pinned raid IDs

> Add a startup command we can run in a Claude Code cloud container environment so when we start a new
> session in cloud, we generate a report with two known raid URLs with IDs so you have something to work off of.

A cloud session starts cold — no local cached data, no report artifact. A startup script that fires the
skill with two pinned report codes (our raid + a top-world benchmark) immediately produces a fresh HTML
report and populates the local cache, so the developer can inspect, tweak, and verify changes against
real data without a manual fetch step every time. Engineering/pipeline layer only (soul: "runs with zero
friction") — nothing in the report changes. Needs two known report codes pinned in the script; should
ideally skip the API fetch and reuse cached data if it already exists, so re-runs are instant.
