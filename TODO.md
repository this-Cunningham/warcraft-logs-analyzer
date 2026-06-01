# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: auto-name reports by guild — "Imminent" vs "Benchmark (Guildname)"

> When generating the report, name each side after the guild rather than the report title.
> The person generating the report should see their guild name (e.g. "Imminent"); the other
> side should be labeled "Benchmark (Guildname)" throughout. The file should also be named
> after the guilds, not the report codes. Right now "New Mount" and "SSC / TK" make it hard
> to remember which is which.

Why: the report's whole value proposition is "your raid vs the benchmark" — the labels are the
spine of every comparison card, every delta, every tab header. Opaque report titles break that
at a glance. Guild names are already in the data (`rankings.data[*].guild.name` in the parses
JSON — confirmed present, e.g. `"guild":{"name":"Imminent","server":{"name":"Nightslayer"}}`),
so this is a cheap fetch with high clarity payoff.

Design notes:
- `compare_raids.py` auto-detects guild name from the parses data and passes it as
  `--ours-name` / `--theirs-name` to `build_deepdive.py`; manual `--ours-name` override
  still wins if the user supplies it.
- Theirs label: `"Benchmark (Guildname)"` keeps the "this is the benchmark" orientation
  clear — a reader who didn't generate the report knows at a glance which side to aspire to.
- Output filename: `imminent-vs-guildname.html` (slugified lowercase) rather than
  `code1-vs-code2.html`.
- Edge case: multiple guilds in one report (PUG night) — fall back to report title or
  the most-common guild name across the parses entries.

---

## TODO: skill behavior — generate + open report, no inline analysis

> Update the skill so it just generates the report and serves/opens it in a browser. Don't do
> any separate analysis in the chat response unless separately asked.

Why: the report *is* the product — the insight lives there, not in the chat transcript. Summarizing
findings in chat after generating the report is redundant (the user can read the report) and
implicitly frames the chat as the deliverable. The soul says the report exists to surface
highest-leverage gaps at a glance; that job belongs to the report, not a bullet list in the reply.

Changes needed in the skill instructions (SKILL.md / the warcraft-logs-analyzer skill prompt):
strip the "reason over the JSON to surface insights" step and the final chat-summary convention;
replace with: run `compare_raids.py`, open/serve the report, confirm it's live. Analysis on
demand only — if the user asks a follow-up question, answer it; otherwise stop at "report is ready."

---

## TODO: soul audit — review report against PRODUCT_MANAGER_SOUL.md and reorganize

> Read PRODUCT_MANAGER_SOUL.md and then reorganize any parts of the report that need to
> be reorganized in ways that match our goals.

This is a chore, not a feature. The soul has three hard filters: gaps ranked by payoff,
every insight actionable, lean on top / depth on demand. Walk every section and ask the
one-line test: *"Would this help an unfamiliar raid leader decide what to fix next —
honestly, at a glance?"* Anything that fails (data dump, raw count, section that doesn't
point at a behavior change) gets removed, moved behind a drill-down, or reframed. The
pending TODOs (Pack-by-Pack removal, sub-tab for CC, spec-instead-of-role, absolute
timeline axis, gap-sorted DPS by Spec) are all partial outputs of this audit — this item
is the holistic pass that catches what those missed.

---

## TODO: more / better insights — what other data can we leverage?

> What else can we do to give better insights and ability to improve our raid? What other
> data is available? What little nooks and crannies of data can we leverage to find
> gaps / areas for improvement?

_(to be replaced)_

---

## TODO: Trash tab — next-pass ideas

> Pending ideas surfaced while building the (shipped) Trash tab.

- Feed the big trash-deaths gap (e.g. 48 vs 11) into the Overview **Biggest Gaps** scorecard — it's
  a high-leverage gap that currently only lives in the Trash tab.
- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier.

---

## TODO: time-resolved insights — mine the event stream & timelines (one level deeper than aggregates)

> Everything today is a fight-total aggregate ("Raid DPS on Hydross: X vs Y"). The richest coaching
> lives in *when* and *at what*: where in the fight did we fall behind, what was each role doing at
> that moment, what were the melee/ranged actually targeting, when did cooldowns fire, when did the
> deaths cascade? Derive second-order insights from the per-event timeline and compare the *shape* of
> our fight against the benchmark's, not just the totals. The thing we want to be able to say:
> *"your melee spent the first 30s on the wrong target."*

This is a research-and-build track, not one feature. Below is what the WCL v2 data actually supports
(verified live against a real SSC/TK report on 2026-06-01 — the current pipeline only ever calls
`table`/`playerDetails`, so `events`/`graph` are untapped), the cost levers, and the candidate
insights ranked by soul-fit. **Read "what's available vs not" first — it kills the literal
positioning ask, and we don't want to re-spend API points re-discovering that.**

### What's available vs not (verified — don't re-investigate)

- **Not reachable via our API — per-actor positioning.** WCL *does* have position data for these
  reports — the website "replay" works, and `ReportFight.boundingBox{minX,maxX,minY,maxY}` comes back
  **populated** with real coordinate spans per boss (Hydross 5337×6062 units; SSC fights on map 332,
  TK on map 334). But the **per-actor coordinate stream is not exposed through the public
  client-credentials API we use**: across a full Hydross kill, all **17,062 events carried zero
  `x`/`y`** — the keys aren't even present in the JSON, despite the populated bounding box. So "where
  does tank 1 / a healer / the melee stand", spread-vs-stack, and boss-facing **cannot be built** from
  the data our pipeline can reach. The only positional field the public API exposes is the whole-fight
  `boundingBox` — one rectangle, not time-resolved and not per-role, so not actionable on its own.
  **Caveat / one unopened door:** the per-actor stream *might* be reachable via the user-OAuth API
  (authorization-code flow, not yet built — needs a one-time browser login) or a website-internal
  endpoint; unconfirmed, don't rely on it, but it's the spike to run if positioning becomes a
  priority. (Verified 2026-06-01 on report 1GHrpaNc2YM4hKTJ — note the earlier "TBC doesn't record
  positions" framing was wrong: WCL records them, the public client API just withholds the per-actor
  stream.)
- **Available — targeting.** Every `cast` and `damage` event carries `targetID` (+ `targetInstance`
  to tell apart multiple copies of the same add). `masterData.actors(type:"")` maps every id →
  name/type for players AND all NPCs/adds in the fight (244 actors on the test pull). So we can
  reconstruct *who each player was hitting, moment by moment.* (Note: stale `zzOLD…` totem actors
  appear in the actor list — filter them.)
- **Available and cheap — time-series curves.** `graph(dataType:…, viewBy:Source)` returns one
  **pre-downsampled** series per player — ~38 points for a 98s fight (≈ one sample every 2.5s). This
  *is* the "sample every 2s instead of every ms" idea, and WCL does it server-side for free, with no
  raw-event pull, for DamageDone / Healing / Threat / etc.
- **Available — threat over time.** `graph(dataType:Threat)` (~20 pts/fight) → aggro / threat-lead
  insights ("a DPS overtook the tank on threat at 0:45"). Verify per-enemy bucketing before building.
- **Unreliable in TBC — mana/resources.** `graph(dataType:Resources)` returned **0 series** on the
  test fight and `hitPoints` on events was null — TBC logs are sparse here. Verify before promising
  any OOM / mana-management insight; treat as not-available until proven otherwise.

### Making it cheap (the cost question, answered)

The granular stream is large, but volume is controllable:

1. **Prefer `graph` over `events`** for anything that's a curve (DPS/HPS/threat over time). It's
   already bucketed to ~2-3s server-side — one cheap call per fight, no pagination.
2. **`filterExpression`** (verified, applied server-side on `events`/`graph`/`table`) — fetch only
   the events you need (`type="cast"`, a target id, a source role) so volume is cut before it leaves
   WCL. This is the lever that makes the targeting reconstruction affordable.
3. **Reconstruct target-over-time from cast/damage events you'd pull anyway** — players act every GCD
   (~1.5s), so target resolution is naturally ~1-2s with no extra sampling cost.
4. **Only the shared bosses, only the kill** (one clean pull per boss, not every wipe), and **cache
   to disk** — a finished fight's events never change. Extends the existing `data/<code>` pattern.

### Candidate insights (ranked by soul-fit)

1. **Focus-fire / target-switching timeline** — *the flagship; reveals a real, actionable gap.* On
   multi-target fights, at each ~2s tick compute the share of raid DPS hitting the single
   most-damaged enemy (focus concentration), and per role the latency to switch onto a newly-spawned
   priority add. Benchmark the *shape*: "melee took 24s to switch to the Tainted Elemental; benchmark
   switched in 6s" / "raid DPS was split 60/40 across two adds for the first 30s." **Honesty guard:**
   prefer measurable focus *concentration* and *switch latency* (boss-agnostic, no hardcoded "correct
   target"); only where we encode TBC add priorities, label them explicitly as our assumption.
   Data: `events(Casts/DamageDone)` + `targetID` + `Summons` for spawns.
2. **Per-boss timeline vs benchmark** — already shipped (per-boss **Timeline** sub-tab; event-binned
   DPS/HPS curves, `tlChart` in report.html). Established the timeline plumbing the remaining
   candidates (#1 targeting, #3 cooldowns, #4 threat, #5 cascades) can reuse.
3. **Cooldown-timing timeline.** When the big raid/personal CDs actually fired vs the optimal window —
   Bloodlust, Power Infusion, trinkets, Combustion/Recklessness/Death Wish. "You lusted at 0:45 (P1)
   vs benchmark at 2:30 (execute)." Data: `events(Casts)` filtered to a CD ability-id set. (Already
   noted in SKILL "next-pass ideas"; the timeline framing makes it land.)
4. **Threat / early-aggro check.** Did a DPS pull aggro off the tank, and when — and what was the
   threat-lead margin at pull? "A mage overtook the tank on threat at 0:12 on three pulls." Action:
   open softer / misdirect. Data: `graph(Threat)`. Cheap; honest; verify per-enemy bucketing first.
5. **Death-cascade detection.** We already list deaths; the *timeline* reveals whether they cluster
   (a cascade = one trigger — e.g. a healer death — not N independent mistakes). "3 of 4 deaths fell
   within 8s at 2:10 — fix the trigger, not four players." Data: death timestamps (already fetched) —
   near-free, just a clustering pass over data we have.
6. **Add-handling speed.** Time from a priority add's spawn (`Summons` / first appearance) to its
   death, ours vs benchmark. "The Tainted Elemental lived 14s longer for you." Pairs with #1.
   Data: `Summons` events + enemy `death` events + `targetID`.

Open questions across the track: which bosses have enough multi-target structure to make #1/#6 worth
it (single-target fights → skip); how to align two fights of different length on one axis (% of fight
vs absolute seconds); where these live in the report (a per-boss **Timeline** sub-tab under Execution
feels right); and how much extra fetch/points the event pulls add over today's table-only budget
(spike #2 first — cheapest, highest-value, and proves the timeline plumbing for the rest).

---

## TODO: timeline x-axis — use absolute seconds, not % of fight

> The timeline view should not be % based on the time x-axis. This makes it harder to compare
> when fights are different lengths.

Why: the current 0–100% normalization was chosen so two kills of different lengths overlay on the
same axis, but it obscures *when* things happened in real time — "our DPS fell at 60%" reads
differently depending on whether the fight was 3 minutes or 8. Absolute seconds is the honest axis:
the reader can immediately place events ("we lost DPS at 2:30") and the charts give accurate phase
timing. When fight lengths differ, the shorter kill's line simply ends earlier — the gap is visible,
not hidden by compression.

Design note: death/lust/phase markers are currently placed as % of each fight's duration; they'd
need to convert to absolute seconds. The benchmark line ending early (their faster kill) is itself
signal — it shows *how much sooner* they finished. Open Q: whether to offer a toggle (absolute /
normalized) or just switch outright.

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

## TODO: sort "What's Killing Us on Trash" by biggest delta we can improve

> Sort the "What's Killing Us on Trash" section by the biggest delta we can improve.

Why: currently the table is ranked worst-for-us by raw ours count, but the highest-leverage
rows are those where the benchmark avoids a death we're taking — i.e. the biggest positive
delta (our deaths − their deaths for that killing blow). Sorting by that delta puts the most
actionable rows first: abilities the benchmark has solved and we haven't. Rows where both
sides take equal damage are real but lower priority; rows where only we die are the fix-it
list. Fits the soul's gap-ranked hierarchy and surfaces what to fix *next*.

---

## TODO: per-player consumables table — show spec instead of role

> In the Per-Player Consumables table, replace the role label next to each player's name
> with their spec. "Healer" becomes "Holy", etc.

Why: spec is more specific and more actionable — a raid leader scanning for offenders can
immediately tell if it's the Holy Priest or the Disc Priest who skipped their flask. "Healer"
carries no useful signal beyond what the row context already implies. The primary spec per
player is already computed in `primary_spec_map` (used throughout the report), so this is a
pure display change with no new data needed.

---

## TODO: Prep enchant audit — treat Windfury as a valid weapon-slot substitute for melee

> In the Prep tab, the weapon-oil check should be "Oil/Windfury" for melee. A melee player
> in a Windfury shaman group won't apply a weapon oil — Windfury replaces it. The correct
> logic: if no oil AND a caster → ✗ (always a gap); if no oil AND melee AND no Windfury
> → ✗ (real gap); if no oil AND melee AND Windfury present → ✓ (covered).

Why: flagging well-prepared melee as missing prep is a false positive — it will erode trust
in the enchant audit and cause raid leaders to ignore real gaps. The soul's data-integrity
principle is clear: don't surface a "gap" that isn't one. Windfury Totem is a buff aura
already present in the data we fetch (Buffs table or `combatantInfo.auras`), so the check is
achievable without extra API calls.

Data notes:
- Windfury Totem buff aura: spell id 25587 (rank 5, the raid-tier version); check presence
  on the player for the boss fight in question.
- Melee specs that benefit: Warrior (all), Rogue, Enhancement Shaman, Feral Druid (cat),
  Ret Paladin, Hunter (melee-range edge case — likely skip). Casters and healers never
  substitute oil for Windfury regardless of group.
- A player can be in a non-Windfury group even if the raid has a shaman (totems are
  group-scoped, not raid-wide) — so check the buff on the *individual*, not just whether
  the raid has a shaman.

---

## TODO: move "Crowd Control on Trash" into its own sub-tab

> Move the "Crowd Control on Trash" section into its own sub-tab within the Trash tab.

Why: the Trash tab is getting long — CC is detail, not a headline gap. Moving it behind a sub-tab
keeps the main Trash view lean (Glance + What's Killing Us + Kill Order as the primary read) while
preserving the CC breakdown for leaders who want to drill in. Consistent with the soul's
"lean on top, deep on demand" layout principle. The Kill Order section already uses a sub-tab
toggle (`.btab[data-ktab]`), so the pattern and plumbing already exist.

---

## TODO: remove Pack-by-Pack section from the Trash tab

> Remove the entire Pack-by-Pack section and any dangling references to it.

Soul check: Pack-by-Pack is a single-raid per-pull drill-down (our raid only, no benchmark comparison). It's the closest thing to a raw data dump in the report — a list of every pull with its mobs, kill timeline, deaths, and CC detail. It doesn't rank gaps or tell the leader what to fix first; a reader has to do all that work themselves. Removing it tightens the Trash tab to the sections that do point at actionable gaps (Glance, What's Killing Us, Kill Order, CC). Dangling refs likely live in `build_deepdive.py` (`trash_packs`/`build_trash`), `SKILL.md`, `report.html`, and potentially `TODO.md` itself (the DONE section above mentions it).

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
