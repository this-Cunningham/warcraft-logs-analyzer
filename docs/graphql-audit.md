# GraphQL Data-Surface Audit — untapped, actionable insights

**Date:** 2026-06-02 · **API:** WCL v2 public (client-credentials) · **Budget used:** ~14 of
3600 pts/hr (see [Method](#method--evidence)). · **Scope:** discovery only — this is a vetted menu,
not an implementation. Every "is the data there?" claim below is backed by a live trial query against
real TBC SSC/TK reports.

This audit systematically diffs **what the WCL API exposes** against **what our pipeline actually
queries**, then ranks the gap by the [product soul](../PRODUCT_MANAGER_SOUL.md): does it reveal an
*actionable gap*, with a *clean* better/worse signal, ideally from a *new modality* of data — and is
it actually *populated in TBC* (a schema field ≠ usable data).

---

## Build status (update — 2026-06-02)

Acting on review, four candidates were **built and verified end-to-end** on the test reports (the report
generates, the data flows, the JS validates):

- ✅ **#4 Wipe depth** — per-boss "Best attempt: X% boss HP remaining (PhaseName)" (sub-1% → "<1%").
- ✅ **A Named phases** — `report.phases` joined to transitions; upgrades Phases, wipe depth, death timing
  (Kael'thas → "P5: Gravity Lapse"). *Corrected a stale SKILL caveat.*
- ✅ **#2 Cooldown & Trinket usage** — per-spec activations/min, ours vs benchmark. **Reworked during the
  build:** verified that TBC logs marquee cooldowns only as **buffs** (no cast events), so it reads buff
  `uses` for cooldowns + casts for trinkets (disjoint sources). Captures hunters'/warriors' CDs correctly.
- ✅ **Casts rotation / ability-mix** — per-spec cast-share vs benchmark, descriptive (neutral Δ).

- ✅ **#1 Threat / early-aggro** (`table(Threat)`) — "Early Aggro — Threat Pulls": per-boss count of a
  non-tank holding the **named boss's** aggro, ours vs benchmark, opener-weighted; feeds the Overview
  scorecard ("Pulling aggro in the opener"). Built the **scoped** version and **cut the naive
  aggro-uptime %** exactly as the audit warned (it reads 131%/62% on multi-tank/phase fights).
- ✅ **#3 Focus-fire** (`events.targetID`) — "Target Focus & Add Handling": **focus concentration** (share
  of raid damage on the most-focused enemy) **+ add-handling** (median add lifespan once engaged), ours vs
  benchmark. Built for **zero extra API cost** by binning the Timeline's existing DamageDone pull by
  `targetID`. A spike confirmed **switch-latency (spawn→engage) is a dead-end** — boss-add spawns aren't
  exposed (`summon` events are player totems) — so add *survival* is the buildable cousin (TODO #6).

**Verified dead-end (don't retry):** focus-fire **switch-latency** — add spawn times aren't reachable. 
**Lower-priority leftovers:** cross-guild leaderboard (redundant with parses), raid incoming-damage
timeline (candidate B).

---

## TL;DR — ranked verdict table

| # | Candidate | New modality? | Data source | Gap it reveals | Soul-fit | API cost | Populated in TBC? (evidence) | **Verdict** |
|---|-----------|:---:|-----------|----------------|----------|----------|------------------------------|-------------|
| 1 | **Threat / early-aggro pulls** | ✅ threat | `table(Threat)` → `threat[].targets[].bands[]` | A non-tank held the *boss's* aggro (opened too hard / no misdirect) | Clean **only when scoped** to the named boss + opener; naive "tank-uptime %" is noisy | Cheap (~2–4 pt/boss/side) | ✅ **Yes** — all 4 bosses; VR shows a clean Warlock pull (see [E1](#e1)) | **SPIKE** — build the *scoped* version; cut the uptime% |
| 2 | **Cooldown / trinket usage** | ✅ casts | `table(Casts)` → `entries[].abilities[]` | Major DPS CDs / on-use trinkets pressed less than benchmark | Clean *if* per-fight-normalized + curated CD id set (like our consumable ids) | Cheap (~2–4 pt/boss/side) | ✅ **Yes** — Abacus trinket, Icy Veins, Adrenaline Rush, racials all present (see [E2](#e2)) | **SPIKE** — needs the CD set + normalization |
| 3 | **Focus-fire / target-switch latency** | ✅ targeting | `events(DamageDone/Casts)` + `targetID` + `masterData.actors` | Melee/ranged slow to switch to a priority add | Clean as *concentration* + *switch latency* (no hardcoded "correct" target) | **Heaviest** (events; ~10–20 pt/boss/side with `filterExpression`) | ✅ **Yes** — `targetID` present on every event (see [E3](#e3)) | **SPIKE** — already scoped as TODO #1; highest coaching value, multi-target bosses only |
| 4 | **Wipe depth / progression wall** | ➖ (we count wipes, not depth) | `fights(killType:Wipes/Encounters)` → `fightPercentage`, `lastPhase` | *How far* the best attempt got — where progression stalls | Clean **absolute** signal; actionable for progression nights | ~Free (rides the existing attempts query) | ✅ **Yes** — Kael'thas wipe reached 21.6%; phase bosses need care (see [E4](#e4)) | **BUILD** — extend the existing wipe view (small) |
| 5 | **Cross-guild world leaderboard** | ➖ | `worldData.encounter(id).characterRankings(metric,className,specName)` | Per-spec "vs the whole world," no 2nd report needed | Largely **redundant** with parse `rankPercent` we already fetch | Moderate (1 pt / spec-page-of-100) | ✅ **Yes** — 100 Fire Mages on Solarian, top 2440 DPS (see [E5](#e5)) | **SKIP** for compare mode · spike only for benchmark-free solo mode |
| 6 | **Pet uptime** (hunter/lock) | ➖ | `masterData` `petOwner` + pet death/summon events | Pet died/dismissed = lost DPS | Pet damage **folds into owner** in tables; uptime needs costly events; per-player | ✅ schema; ➖ not cleanly aggregable | ⚠️ Damage rolls up to owner (`petOwner:null`, see [E6](#e6)) | **SKIP** — not a clean raid-level signal |
| 7 | **Summary table** | ❌ | `table(Summary)` | (consolidation — composition+dd+heal+dt+deaths in one call) | Engineering, **not a product gap** | 1 call replaces ~5 | ✅ Yes (rich) | **SKIP** — optimization, not an insight |
| 8 | **Summons table** | ❌ | `table(Summons)` | Player totems/pets summoned | Noisy; not better/worse (a shaman dropping 39 totems isn't "good") | Cheap | ⚠️ Player-summons only, **not boss adds** | **SKIP** — not clean |
| 9 | **Survivability table** | ❌ | `table(Survivability)` | Death count + killing-blow ability | **Redundant** with the Deaths table we already use | Cheap | ✅ Yes (but duplicate) | **SKIP** — already covered |
| 10 | **Resources / mana** | ✅ would-be | `table/graph(Resources)` | OOM / mana management | — | — | ❌ **DEAD** — 0 entries (see [E7](#e7)) | **SKIP** — confirmed dead (matches TODO) |

**Headline:** the one genuinely new, cheap, populated modality with a *clean* signal hiding in it is
**Threat (#1)** — but only the *scoped* "early aggro pull on the boss" reading survives the honesty
bar; the obvious "tank aggro-uptime %" does **not** (it reads 131% on Al'ar, 62% on Kael). Right
behind it: **cooldown/trinket usage (#2)** and the already-scoped **focus-fire timeline (#3)**, both
real but needing curation/cost work. **Wipe depth (#4)** is the cheapest clean win — a near-free
extension of the wipe view we already render.

---

## Round 2 — follow-up (Summary/Casts deep-dive + 3 more candidates)

### Direct answer: do the **Summary** and **Casts** tables add benchmark value?

**Summary → no new gap (confirmed).** Every component — `composition` (name/type/specs/role),
`damageDone`/`healingDone`/`damageTaken` (only `name`+`total`), `deathEvents` (`deathTime` + killing
`ability`), `playerDetails` (healer/dps/tank buckets) — is data we **already fetch via dedicated
tables/parses, usually in *more* detail** (our `DamageDone` table carries per-ability breakdown +
`activeTime`; Summary's carries a bare total). Its only merit is *one call instead of ~five* — an
engineering consolidation the soul explicitly rules out of the product. **Skip as an insight.** (E11)

**Casts → yes, two levers beyond cooldowns, and one trap to cut:**

| Casts lever | Verdict | Note |
|---|---|---|
| Cooldown / trinket usage (= #2) | **SPIKE** | cleanest sub-signal: on-use trinket activations/min vs benchmark; needs curated CD ids |
| **Ability mix / rotation** vs benchmark same-spec | **SPIKE (new)** | genuinely new modality + actionable rotation coaching, but must pool **by spec** (no per-player dump) and flag only *meaningful* deltas → needs TBC rotation priors to separate "different" from "worse" |
| Action rate (casts/min) | **CUT — not clean** | ~entirely spec-determined (BM Hunter **68**/min vs Combat Rogue **26**/min) and within-spec it duplicates the DPS-activity% we already show (everyone here 90–99% active) |

The ability-mix lever is the one genuinely new thing in `Casts`: pooling each spec's cast composition
and diffing vs the benchmark's same spec ("your fire mages cast 18% Scorch vs benchmark 4%") is
real rotation coaching — but a spike, because staying clean (and not becoming a data dump) needs
per-spec priors and strict spec-level aggregation. (E11)

### Three more candidates surfaced

**A. Named phases — `report.phases` → BUILD (pairs with #4).** *Corrects a stale caveat:* SKILL.md
says "TBC has no phase names." True for `phaseTransitions` (id+time only) — but the **report-level
`report.phases`** field returns `PhaseMetadata{id,name,isIntermission}` and **is populated in TBC**.
Cheap (one field). Upgrades the **wipe-depth (#4)**, the **Phases** sub-tab, and **death-timing** from
"P4" → "P4: Kael'thas Engaged." Only multi-phase journal bosses return it — graceful per-boss. (E8)

**B. Raid incoming-damage timeline — `graph(DamageTaken)` / event-binned → SPIKE.** Overlay *when*
raid-wide avoidable damage spikes onto the existing per-boss Timeline ("a damage-taken spike at 2:30
the benchmark doesn't have"). `graph(DamageTaken)` is populated + cheap but **coarse** (fixed
server grid); matching our DPS-timeline resolution means event-binning DamageTaken like we bin
DamageDone (a few more points/boss). Honesty caveat: present as a *relative* spike-shape, not absolute
numbers (graph rates run hot, per the existing SKILL note). (E9)

**C. Global fight leaderboard — `worldData.encounter.fightRankings(metric:speed|execution)` →
SPIKE / low.** Populated for TBC: the world's fastest Solarian kill is **50.7s, 0 deaths**, and each
entry carries the **comp** (tanks/healers/melee/ranged) + ilvl bracket. An *absolute* kill-time /
execution target + meta comp — but partly **redundant** with the benchmark kill-time delta we already
show. Worth it mainly to anchor "world's best" or inform a composition discussion. (E10)

### Evidence (round 2)

<a name="e8"></a>**E8** — `report.phases` (named phases populated in TBC):
```
enc 100733 (Kael'thas): separatesWipes=true
  P1: The Advisors | P2: The Weapons | P3: The Advisors Return | P4: Kael'thas Engaged | P5: Gravity Lapse
(Al'ar / Void Reaver / Solarian returned no named phases — graceful per-boss.)
```
<a name="e9"></a>**E9** — `graph(DamageTaken, hostilityType:Friendlies, fightIDs:[25])`: 26 player series
returned, but server-downsampled to a coarse fixed grid → too blunt for spike-pinpointing without
event-binning.

<a name="e10"></a>**E10** — `worldData.encounter(id:100732).fightRankings(metric:speed)`:
```
#1  guild "BLEACH"  duration 50761ms  deaths 0  comp{tanks 1, healers 2, melee 11, ranged 11}  ilvl 117.6
#2  guild "DREAM"   duration 52325ms  deaths 0  comp{tanks 1, healers 3, melee 9,  ranged 12}  ilvl 117.3
```
<a name="e11"></a>**E11** — Summary vs Casts deep-dive (Solarian kill):
```
SUMMARY.deathEvents[]: {name, deathTime, ability{name,guid}}  <- timing+killing blow, but we already have it (Deaths table)
SUMMARY.damageDone[]:  {name,id,guid,type,total}              <- bare total; our DamageDone table has per-ability + activeTime
SUMMARY.composition[]: {name,type,specs[{spec,role}]}         <- specs; we already get these from parses
CASTS action-rate: BMHunter 67.7/min(99% active) ... CombatRogue 25.9/min  <- spec-determined, dup of activity% -> CUT
CASTS ability-mix: Rogue-Combat[SinisterStrike 42, SnD 4, Eviscerate 3]; Mage-Arcane[ArcaneBlast 64, Frostbolt 6]  <- rotation, spike
```

---

## What we query today (the baseline)

Diffed from `fetch_report.py`, `compare_raids.py`, `build_deepdive.py`, and `queries/`:

- **Tables (8 of 14):** `Buffs`, `Debuffs`, `DamageDone`, `Healing`, `DamageTaken`, `Interrupts`,
  `Dispels`, `Deaths`.
- **Rankings:** `rankings(compare:Parses)` (+ a second `playerMetric:hps` pass merged over healers).
- **playerDetails:** `includeCombatantInfo:true` (gear/enchants/gems/ilvl).
- **fights:** `id,name,encounterID,difficulty,startTime,endTime,size,averageItemLevel,phaseTransitions`;
  plus `fights(killType:Encounters){encounterID kill}` (wipe counts) and `fights(killType:Trash){…}`.
- **masterData.actors** (Player + NPC, id→name).
- **events (4 types):** `DamageDone`/`Healing` (timeline binning), `Deaths` (trash kill order),
  `Debuffs` (trash CC).

## The gap list — what exists that we never touch

- **Tables never queried (6):** `Summary`, **`Casts`**, `Resources`, `Summons`, `Survivability`,
  **`Threat`**.
- **`graph()` — entirely unused.** (Deliberate for the DPS/HPS timeline — see the SKILL note on
  `graph()` returning a ~2× rolling rate — but `graph(Threat)` is a separate, untapped lever.)
- **`worldData` — entirely unused.** No cross-guild leaderboard (`characterRankings`),
  `fightRankings`, or zone/partition data.
- **`ReportFight` fields never read:** `bossPercentage`, **`fightPercentage`** (wipe depth),
  `lastPhase`/`lastPhaseAsAbsoluteIndex`/`lastPhaseIsIntermission`, `wipeCalledTime`, `friendlyPets`,
  `enemyPets`, `friendlyItemLevels` (per-player ilvl array).
- **`events`/`table` args never used:** `filterExpression` (server-side filtering — the lever that
  makes targeted event pulls cheap), `sourceClass`/`targetClass`, `sourceAurasPresent/Absent`,
  `targetID`/`targetInstance` filtering, `viewBy`, `wipeCutoff`.
- **`rankings(compare:Rankings)`** — we only use `Parses`; the `Rankings` (all-star points) mode is
  untouched (judged redundant).
- **`masterData.abilities`**, **`petOwner`**, **`report.phases`** (report-level phase metadata).

---

## Detailed candidates + trial-query evidence

### 1. Threat / early-aggro pulls — *the standout new modality* · **SPIKE**

`table(Threat)` returns, **per actor, per enemy, the time-bands during which that actor held the
enemy's aggro** (`threat[].targets[].bands[{startTime,endTime}]` + `totalUptime`). We have never
touched threat. This directly answers "did a DPS pull off the tank, and when?" — a question the
report can't ask today.

**The clean signal:** a **non-tank holding the *named boss's* aggro**, especially in the opener
(before threat-reset mechanics muddy the water). That's an unambiguous mistake → *open softer / use
Misdirection / Tricks of the Trade.*

**The honesty trap (verified, important):** the *obvious* metric — "% of the fight the tank held
aggro" — is **not clean** and must be cut. Across the four shared bosses it reads:

| Boss | "Tank aggro-uptime" | Why it's misleading |
|------|---------------------|---------------------|
| Void Reaver | **97%** | clean tank-and-spank — *this* is where the metric works |
| Solarian | ~52% | split/shadow phase resets threat |
| Kael'thas | **62%** | 5 phases, boss untargetable windows, advisors/weapons counted as NPC targets |
| Al'ar | **131%** | two tanks **+** adds counted as Boss/NPC → sums past 100% |

So the build must **scope to the target whose name == the encounter boss**, and lead with the
discrete **opener-pull** event, not a blanket uptime %. (A Feral *off-tank* also reads as "non-tank"
by spec-icon — needs the role map we already compute.) `graph(Threat)` is the deeper follow-on: it
gives the *threat margin* ("a mage sat at 95% of the tank's threat" — a leading indicator), at
per-actor cost.

> **Example report line:** *"Void Reaver — a non-tank held the boss's aggro for 4s at 2:08; open
> softer or misdirect."* / *"Opener: 2 threat pulls in the first 20s (benchmark: 0)."*

<a name="e1"></a>**Evidence (E1)** — `table(Threat, fightIDs:[17])` (Void Reaver kill), and the cross-boss scan:

```
Void Reaver: dur 193s | 3 threat entries | TANK aggro-uptime 97%
   NON-TANK held boss aggro >2s (after 8s): [('Pifflock','Warlock-Destruction', 4.1s, first @ +127.8s)]
Al'ar:       dur 448s | TANK aggro-uptime 131%   <- two tanks + adds inflate it
Kael'thas:   dur 546s | TANK aggro-uptime 62%    <- phases / untargetable / advisors
Solarian:    a DPS Arms warrior held boss aggro 12.5s starting at +14.4s (opener pull)
```

### 2. Cooldown / trinket usage — **SPIKE**

`table(Casts) → entries[].abilities[]` lists **every** ability each player cast with a count — crucially
including **non-damaging** ones the `DamageDone` table can't show: on-use trinkets, racials, and major
cooldowns. The gap: *are your DPS actually pressing their buttons?* Maps straight to a behavior change.

**Why it's a spike, not a build:** to be a *clean* signal it needs (a) a **curated CD/trinket spell-id
set per spec** — exactly the pattern we already use for consumables (`FLASK_IDS` et al., mined from
report data), and (b) **per-fight normalization** (CDs have their own cooldowns; "uses per kill" only
compares fairly on like-length fights). The cleanest sub-signal is **on-use trinket activations per
minute** (every raider has trinkets; pressing them is unambiguously good), pooled by spec vs benchmark
— no per-player call-out, stays at the soul's spec grain.

> **Example report line:** *"On-use trinkets fired 1.1×/min vs benchmark 1.9×/min — cooldowns are
> being sat on."*

<a name="e2"></a>**Evidence (E2)** — scan of `table(Casts, fightIDs:[25])` (Solarian) for CD/trinket/racial names:

```
   Abacus of Violent Odds (guid 33807): 4 casts / 2 players   <- on-use trinket
                Icy Veins  (guid 12472): 4 casts / 2 mages
          Adrenaline Rush  (guid 13750): 1 cast  / 1 rogue
               Blood Fury  (guid 33697): 2 casts / 1 player    <- racial
               Berserking  (guid 20554): 1 cast               <- racial
```

### 3. Focus-fire / target-switch latency — **SPIKE** (already scoped as TODO #1)

The flagship time-resolved idea already documented in `TODO.md`. Re-verified here: **`targetID` is
present on every event**, and `masterData.actors` maps ids→names for players *and* adds — so we can
reconstruct *who each player was hitting, moment to moment*, and measure **focus concentration** (share
of raid DPS on the single most-damaged enemy) and **switch latency** (time to put damage on a freshly
spawned priority add). Honesty guard per TODO: prefer concentration/latency (boss-agnostic) over any
hardcoded "correct target." Highest coaching value of the lot, but the **heaviest** (event pulls) and
only meaningful on multi-target fights — hence spike, behind the cheaper wins.

> **Example report line:** *"Melee took 24s to switch to the Tainted Elemental; benchmark switched in 6s."*

<a name="e3"></a>**Evidence (E3)** — `events(DamageDone, fightIDs:[25], limit:6)`:

```
{"type":"damage","sourceID":39,"targetID":175,"abilityGameID":25274,"amount":78}
{"type":"damage","sourceID":17,"targetID":175,"abilityGameID":27019,"amount":1484}
   ... targetID present on every event (175 = Solarian); targetInstance distinguishes add copies.
```

### 4. Wipe depth / progression wall — **BUILD** (cheapest clean win)

We currently render **wipe counts** but throw away *how far each attempt got*. `fightPercentage`
(and `lastPhase` on multi-phase bosses) is **populated** and turns "you wiped 6×" into "your best
attempt reached 21.6%, and you're walling at the P4→P5 transition" — a clean **absolute** progression
signal (no benchmark needed; the soul blesses first-class absolute checks). It rides the attempts
query we *already* run, so it's ~free. Caveat to encode: phase bosses can report oddly (an Al'ar wipe
showed `fightPercentage 0.01` — either a genuine sub-1% heartbreaker or a phase-tracking quirk), so
read `fightPercentage` together with `lastPhase` and verify per encounter. Naturally quiet on farm
nights (few wipes) — which is correct, *silence over noise*.

> **Example report line:** *"Best Kael'thas attempt: 21.6% (reached P5). Six wipes — the wall is P4→P5."*

<a name="e4"></a>**Evidence (E4)** — `fights(killType:Wipes){fightPercentage,lastPhase,wipeCalledTime}`:

```
Kael'thas wipe: bossPercentage 21.6, fightPercentage 21.6, lastPhase 5   <- real wipe-depth
Al'ar wipe:     fightPercentage 0.01, lastPhase 0                        <- phase quirk: verify per-boss
wipeCalledTime: null on every wipe                                       <- DEAD (Companion-app only)
```

### 5. Cross-guild world leaderboard — **SKIP** (compare mode) / spike (solo mode)

`worldData.encounter(id).characterRankings(metric, className, specName, …)` **works for TBC** — it
returns the global per-spec DPS distribution for a boss. But it is **largely redundant** with data we
already pull: `rankings(compare:Parses)` already gives every player a `rankPercent` (their percentile
vs this very pool) *and* their `amount`. The only thing the leaderboard adds is the *absolute* top/median
DPS number, which the parse data already lets a leader infer. Its real future use is **powering the
benchmark-free single-report mode** ("your raid vs the world's best per spec" with no 2nd report) — a
spike for *that* mode, not the comparison headline.

<a name="e5"></a>**Evidence (E5)** — `worldData.encounter(id:100732).characterRankings(metric:dps, className:"Mage", specName:"Fire")`:

```
encounter: High Astromancer Solarian | zone: SSC / TK
characterRankings: 100 rankings (hasMorePages:true)
  Guccifart  2440.6 dps (Mage/Fire, "No Hard Feelings")
  Fetalars   2040.4 dps
  Blådag     1880.0 dps  ...
```

### 6–10. Skips (with the why)

<a name="e6"></a>**6. Pet uptime (E6)** — in `table(Summary).damageDone`, every entry is a *player* with
`petOwner:null` (22 entries, no pet rows): **pet damage rolls up into the owner's total**. Measuring "pet
was dead for N seconds" would need per-pet death/summon **events** (expensive) and is inherently a
per-player hunter/warlock issue — not a clean raid-level gap. *Skip.*

**7. Summary table** — a rich one-call bundle (`composition`+`damageDone`+`healingDone`+`damageTaken`+
`deathEvents`+`playerDetails`). Purely an **engineering consolidation** (fewer calls), which the soul
explicitly rules out of the product's value prop. *Skip as an insight* (worth a glance only if we ever
optimize the fetch path).

**8. Summons table** — its `entries[]` are **players with summon counts** (totems, pets), e.g. a shaman
"summoned 39" (totems). Not boss-add spawns, and "more totems" is not better/worse. Noisy. *Skip.*
(Boss-add handling is better served by #3's `targetInstance` + enemy death events.)

**9. Survivability table** — `actortotals[].total` (death count) + `abilitytotals` (killing-blow
ability). **Redundant** with the `Deaths` table we already mine for "What's Killing Us." *Skip.*

<a name="e7"></a>**10. Resources / mana (E7)** — `table(Resources)` returned **0 entries** (`resources:[]`);
`graph(Resources)` was already verified to return 0 series and `hitPoints` null in TBC (TODO). **Confirmed
dead** — do not re-spend points here. *Skip.*

---

## Confirmed dead-ends (do not re-spend API points)

- **`Resources`/mana** — empty in TBC (re-confirmed: 0 table entries). 
- **`wipeCalledTime`** — null (Companion-app only; our test guilds don't use it).
- **`lastPhase` as a general field** — 0 for non-phased/short fights (Al'ar, VR, Solarian); only
  meaningful where `phaseTransitions` already are. Use it *with* phase transitions, not standalone.
- **Per-actor positioning** — already exhaustively killed in TODO (events carry no x/y; only the
  whole-fight `boundingBox`). Not re-tested.
- **`petOwner` for pet uptime** — pet damage folds into the owner in tables (this audit).

---

## Method & evidence

- **Schema:** regenerated via `scripts/introspect.py` (gitignored `schema.json`, 380 KB); enumerated
  `TableDataType`/`GraphDataType`/`EventDataType`, the full `Report`/`ReportFight`/`WorldData`/
  `Encounter`/`ReportActor` field sets, and the `table`/`graph`/`events` arg lists.
- **Diff:** grepped `fetch_report.py`, `compare_raids.py`, `build_deepdive.py`, `queries/*.graphql`
  for every `table(`/`graph(`/`rankings(`/`events(`/`playerDetails`/`masterData` call.
- **Trial reports (public TBC SSC/TK):** `pkHqfrBbhQK9GP1a` (shared bosses Al'ar 100730 / Void Reaver
  100731 / Solarian 100732 / Kael'thas 100733). All "is it populated?" verdicts above are from live
  queries against the *kill* fights, batched via aliases.
- **Budget:** total spend for the entire audit was **~14 pts** of the 3600/hr cap — `graph`/`table`
  probes are cheap; only the focus-fire (#3) build would draw meaningfully on events.

> Reproduce any probe with, e.g.:
> ```bash
> python3 .claude/skills/warcraft-logs-analyzer/scripts/query.py \
>   --query 'query { reportData { report(code:"pkHqfrBbhQK9GP1a") {
>     threat: table(dataType:Threat, fightIDs:[17]) } } }'
> ```
