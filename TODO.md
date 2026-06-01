# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: soul audit — review report against PRODUCT_MANAGER_SOUL.md and reorganize

> Read PRODUCT_MANAGER_SOUL.md and then reorganize any parts of the report that need to
> be reorganized in ways that match our goals.

This is a chore, not a feature. The soul has three hard filters: gaps ranked by payoff,
every insight actionable, lean on top / depth on demand. Walk every section and ask the
one-line test: *"Would this help an unfamiliar raid leader decide what to fix next —
honestly, at a glance?"* Anything that fails (data dump, raw count, section that doesn't
point at a behavior change) gets removed, moved behind a drill-down, or reframed.

---

## TODO: more / better insights — what other data can we leverage?

> What else can we do to give better insights and ability to improve our raid? What other
> data is available? What little nooks and crannies of data can we leverage to find
> gaps / areas for improvement?

_(to be replaced)_

---

## TODO: Trash tab — next-pass ideas

> Pending ideas surfaced while building the (shipped) Trash tab.

- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
  Needs a new Casts-on-trash fetch + view; research-flavored, deferred.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier. Conditional, not needed yet.

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
   DPS/HPS curves on an absolute-seconds axis, `tlChart` in report.html). Established the timeline
   plumbing the remaining candidates (#1 targeting, #3 cooldowns, #4 threat, #5 cascades) can reuse.
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
it (single-target fights → skip); where these live in the report (a per-boss **Timeline** sub-tab under
Execution feels right); and how much extra fetch/points the event pulls add over today's table-only
budget (spike #2 first — cheapest, highest-value, and proves the timeline plumbing for the rest).
