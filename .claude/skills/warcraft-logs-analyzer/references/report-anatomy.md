# Report anatomy — the deep-dive comparison report

`build_deepdive.py` (invoked by `compare_raids.py`) injects a `const DATA` blob into
`templates/report.html` (inline CSS+JS, dark, offline, no CDN) by replacing the
literal `/*__DATA__*/null`. Seven top-level tabs, a funnel:

| Tab | Question it answers |
|---|---|
| **Overview** | Where's the gap, at a glance |
| **Composition** | Roster makeup & buffs |
| **Prep** | Did we show up ready |
| **Execution** | Raid-wide gaps + per-boss drill-down |
| **Bosses** | Per-boss execution drill-down + kill summary |
| **Wipes** | Why we wipe (the wall, the trend, the tax, what ends attempts) |
| **Optimize** | How each raider's rotation compares to the world best |
| **Trash** | How we handle trash packs |

Every section compares ours vs benchmark with a delta; weak/ambiguous metrics are
deliberately omitted (see `PRODUCT_MANAGER_SOUL.md`). Symbols below are
`build_deepdive.py` Python builders → `report.html` JS renderers, unless noted.

---

## Overview

- **Biggest Gaps scorecard** (`biggest_gaps` → `gapsScorecard`) — one ranking pass
  over every tracked dimension (parse, kill time, raid DPS, deaths, overheal,
  activity, avoidable dmg/s, flask, food, enchants, missing buff/debuff providers,
  wipes, worst spec-DPS gap, worst buff/debuff uptime gap, trash deaths via `trash=`,
  worst avoidable killing blow via `death_causes=`, threat opener via `threat=`,
  leaked interrupts via `leaked=`). Each gets a hand-tuned severity [0,1] + an
  actionable sentence; only dimensions where we trail are kept; top 7 render as
  severity-colored cards.
- **What You're Doing Well** (`strengths` → `didWellScorecard`) — same engine, sign
  flipped: where we match/beat benchmark, ranked by margin (top 5, green). Empty if
  we trail everywhere (never manufactures praise). The buff/debuff "well-maintained"
  strength requires benchmark uptime > 0 (a real "we maintain it better" lead, not a
  "they don't run it").
- **Raid Summary cards** (incl. Total Wipes when attempt data present).
- **Parse Spread** (`parse_spread` → `parseSpreadView`) — **EXPERIMENTAL**, the distribution behind the
  Avg Raid Parse *mean*: median + the count of **floor** parses (rankPercent < 25) + the lowest-parsing
  **specs** (with the benchmark's same spec), ours vs theirs. Tells a leader whether the gap is the whole
  raid or a handful of anchors — coach the named floor specs vs re-gear everyone. Spec grain, never
  per-player. From the per-player-per-shared-boss `rankPercent` already in the parses file.
- **Boss-by-Boss** — one sub-tab per boss (`mountOverview` wires `.btab/.bsub
  [data-otab]`): kill time, Raid DPS/HPS bars (total ÷ duration), avg parse, deaths,
  wipes-before-kill (shown only if either wiped), **wipe depth** (`attempt_map`:
  closest wipe's `fightPercentage` + `lastPhase` → "Best attempt: X% remaining
  (Phase)"; sub-1% renders "<1%" — phase-reset bosses like Al'ar collapse to ~0
  without a kill), and both rosters. Each side renders a DPS/tanks table + a
  **separate Healers table** (`sideRosters` → `rosterTable`) with an HPS column
  (healer parses are HPS-based — see `wcl-api.md`).

---

## Composition

Raid composition + buff-provider gaps (`PROVIDER_CHECKS`: class/spec → raid buff it
brings). Spec = each player's **primary (most-frequent) spec across shared bosses**
(`primary_spec_map`), so a Feral who bear-tanks one fight still reads Feral and still
counts as a Leader-of-the-Pack provider — keeps counts order-independent.

**Provider Count & Coverage** (`count_providers` + `scope` on `PROVIDER_CHECKS` → the second Composition
table) — **EXPERIMENTAL**, one level deeper than the binary ✓/✗: **how many** providers each side fields.
Honest split by buff `scope`: **group**-scoped buffs (Windfury / Bloodlust / Battle Shout / Trueshot /
Ferocious Inspiration / Leader of the Pack land on the provider's 5-man party) → a count delta is a clean
coverage signal (more = more groups covered); **raid**-scoped boss debuffs (Misery / CoE / Imp FF / JoW /
Imp Scorch / Expose) → one provider delivers it in full, so a count delta isn't better/worse, but
**count == 1 is a single-point-of-failure** (one death/absence and the buff is gone). Count matching
inherits `has_provider`'s spec-name logic, so a WCL spec variant (e.g. "Dreamstate" boomkin) can read 0 —
the same caveat the binary check already carried.

(Cut in the soul audit: *Damage Contribution by Class* — % share conflates "fewer of
that class" with "that class underperforms." The per-player **DPS by Spec** gap is
the honest version.)

---

## Prep

- **Consumables Coverage** (`consumable_report`) — Flask/Elixir-Pair card reads
  per-player consumes (`_cell_for`), so a battle+guardian **elixir pair** counts as
  prepared like a flask (the aggregate Buffs table can't tell them apart). Food =
  per-player Well-Fed; Drums uptime % = fight-uptime from aggregate Buffs. Falls back
  to aggregate flask/food totals on bosses without a consumes file. `ELIXIR_EXCLUDE`
  drops junk "…Elixir" names (Noggenfogger).
- **Consumables classified by SPELL ID, not name.** WCL renames most consumable buffs
  to their *effect* (Flask of Supreme Power → "Supreme Power"; Ironshield Potion →
  "Ironshield") — name-matching misses them and false-positives same-named scrolls.
  Id sets (`FLASK_IDS`, `ELIXIR_BATTLE_IDS`, `ELIXIR_GUARDIAN_IDS`, `POTION_IDS`) are
  **mined from the report data** (every buff carries `guid`; the benchmark top guild
  carries the full set), battle/guardian verified once vs Wowhead. A "Flask of…"/
  "Elixir of…" name fallback covers unlisted ids. Extend id sets as new tiers surface.
- **Per-Player Consumables — two matrices** (ours only; one row/raider labeled by
  primary spec; shared bosses across the top):
  - **Prep matrix** (`per_player_consumables` → `consumeMatrix`) — worst-prepared
    first, cols **F·B·G·Fd** (flask / battle / guardian / food) + a leading Prep
    (consumed-bosses / played). "Consumed" = flask OR a battle+guardian pair
    (`_elixir_type`; a lone elixir isn't enough). **Route-aware** cells: a flasked
    player's empty B/G render faint; a guardian-only player's missing battle is red.
    Legend: ✓ had it · red ✗ missing+needed · faint ✗ not needed via that route ·
    `·` didn't attend. **Source:** Buffs table scoped by `sourceID`
    (`_fetch_per_player_buffs` → `consumes-<enc>.json`), NOT events — pre-pull buffs
    fire no events and `combatantInfo.auras` is empty in TBC.
  - **In-combat matrix** (`per_player_incombat` → `inCombatMatrix`) — pressed *during*
    the fight: **P** throughput potion (buff-sourced, POTION cat) · **HP/MP/HS**
    health/mana potion, healthstone (from the **Casts** table — instant items leave no
    aura: mana pot = "Restore Mana", healthstone = "Master Healthstone", health pot =
    "Restore Health"). A **usage** view, not pass/fail: a non-use is a faint dash,
    never a red gap. **HS is warlock-dependent** (column flagged unavailable with no
    warlock). Sorted least-potion-use first.
- **Throughput Consumables** (`throughputView`) — (1) **Potions by Spec**
  (`potion_usage_by_spec`/`potion_gap`): combat-pot activations pooled by (class,
  spec), ranked by biggest deficit (clean better/worse — pure throughput). (2)
  **Choices** (`throughput_choices`): which specific flasks/battle-elixirs each raid
  runs (meta mined from benchmark), descriptive.
- **Opener Potion — Prepot** (`prepot_timing` → `prepotView`) — **EXPERIMENTAL**, the *timing* decomposition
  of the potion-uses count: did the throughput potion land **on the pull** (the free TBC opener prepot,
  which shares a cooldown with the in-combat potion so skipping it wastes a potion) or only reactively
  mid-fight. From the aggregate Buffs `bands` (earliest potion band start vs fight start; ≤3s ≈ on the
  pull). **Raid-aggregate** (bands merge across players) → an honest raid-level "opener potion on the pull:
  X/N bosses", NOT a per-player prepotter count (same precedent as Drums uptime).
- **Enchants & Weapon Oils** (`audit_report`) — missing enchants from
  `combatantInfo.gear.permanentEnchant` + weapon-oil presence, restricted to the
  **shared-boss roster** (matches Composition). **Windfury counts as a weapon buff for
  melee** — a melee in a WF group applies no oil, so flagging "no oil" is a false
  positive. `_is_melee` classifies melee (Warrior/Rogue all; Enh/Ret/Feral; hunters
  excluded); `windfury_players` reads WF **per-player** from `consumes-<enc>.json`
  auras (NOT aggregate Buffs — WF is group-scoped; match "Windfury"/`WINDFURY_IDS`). A
  melee w/ WF but no oil is covered (✓ WF). Graceful: no consumes → no upgrades. (Gem
  count dropped — no socket count to flag empties.)
- **Hit & Expertise** (`stat_audit`/`stat_audit_compare`/`spell_hit_env` → `hitCapView`) — **EXPERIMENTAL**,
  the first new modality off `combatantInfo.stats` (a per-pull Hit/Expertise/Crit/Haste snapshot the report
  never read). Per-raider **effective hit %** = **gear + talent + raid**, broken into those three columns,
  worst-first — the one per-player view outside Optimize (a gear FIX, not a skill judgment).
  - **gear**: the snapshot rating ÷ 12.6 (casters) / ÷ 15.77 (melee+ranged), `max` across the night.
  - **talent**: the spec's standard-build hit talent, assumed taken in full (`SPEC_TALENT_HIT` — Shadow
    Focus +10, Balance of Power +4, Elemental Precision +3 [Fire/Frost mage], Nature's Guidance +3 [Elem &
    Enh shaman], Precision +5 [all rogue specs] / +3 [Arms/Fury warrior], Surefooted +3 [Survival hunter]).
    Invisible in the data (TBC talents are placeholders), so it's a meta assumption, not a read. Omitted
    (no standard hit talent / partial): Warlock Affliction (Suppression helps DoTs not Shadow Bolt — they
    gear to the SB cap), Destruction/Demo Warlock, Mage Arcane (EP is Fire/Frost only), BM/Marksmanship
    Hunter, Ret, Feral, and the TANKS (Prot Warrior/Pala, bear — they itemize to ~9% without a talent).
  - **raid**: Improved Faerie Fire (+3% spell hit, `IMP_FAERIE_FIRE_HIT`) via `spell_hit_env`, credited when
    a Balance Druid is in that side's roster (raid-wide boss debuff). NOT modeled: Totem of Wrath / Heroic
    Presence (party-scoped), Misery (it's +5% spell DAMAGE, not hit). Melee/ranged raid = 0.
  **Target** = the *benchmark's same-spec EFFECTIVE* hit, capped at the textbook cap (`HIT_CAP`: spell 16 ·
  melee 9 · ranged 8); same-spec so talents (shared) cancel and a raid buff asymmetry (we run boomkins,
  they don't) doesn't wrongly flag our capped casters. Flag = a clear margin under target (2pp vs a real
  benchmark, 3pp vs the bare cap). Talent's real payoff is an HONEST effective-vs-cap read — a Shadow
  Priest at 6% gear is capped via Shadow Focus, not under (under-flag count 7→2 on the sample). Expertise
  shown benchmark-relative only (unit ambiguous, no absolute cap claim). Graceful "" on older folders.
- **Item level** — raid avg (`fights.averageItemLevel`) + **by role** (`role_ilvl`:
  dps/healer/tank from dd/heal/dt) so an under-geared role stands out.

---

## Execution — raid-wide gaps

- **What's Killing Us** (`death_cause_compare` → `deathCausesView`) — killing-blow
  names across all shared bosses, ranked by **biggest avoidable delta** (ours−theirs;
  floats the mechanic the benchmark solved). Top row feeds the scorecard.
- **Time Lost to Deaths** (`death_time_compare` → `deathTimeView`) — **EXPERIMENTAL**, the *time*
  companion to What's Killing Us: each death costs `(fight end − death time)` player-seconds of lost
  output, summed across the clear into **player-minutes** by killing-blow cause (reusing
  `_death_cause_label`, so an add's blow carries its mob in parens), plus a raid headline (minutes lost +
  **effective uptime** = 100 − lost%, base = roster × total shared-boss fight time). Ranks by the mechanic
  burning the most output-time — a death at 90% boss HP costs far more than one at 2%, which a raw count
  misses. **Upper bound** (assumes a downed raider stays down; a battle-res reduces it) — labeled as such.
- **Lowest-Hanging DPS — Spec Gaps** (`tier_spec_gap` → `tierSpecGapView`) — DPS
  pooled by (class, spec) across shared bosses, ranked by per-player deficit. Mirrored
  bars; one-raid-only specs noted.
- **Activity by Spec** (`activity_buckets`/`tier_activity_gap` → `activityGapView`) — **EXPERIMENTAL**,
  sits right under the spec DPS gap as its uptime decomposition. Each **DPS** spec's avg per-player
  activity (`dd.activeTime` ÷ fight dur — the share of the fight spent actively dealing damage) pooled
  across shared bosses, ours vs benchmark same spec, mirrored bars. Idle GCDs (movement/swaps/range) are
  throughput recoverable *without* gear, so a trailing spec is high-leverage coaching — it names which
  spec is losing the uptime behind the raid-wide Activity number. **Healers excluded on purpose:** their
  "active" time isn't a clean better/worse signal (less healing can just mean the raid took less damage);
  tanks excluded too (activeTime conflates tanking with incidental DPS). Clean better/worse for DPS.
- **DPS Ramp** (`dps_ramp` → `dpsRampView`) — **EXPERIMENTAL**, per boss: seconds to first reach 90% of
  the fight's **median** (cruising) DPS — how fast the raid got up to pace after the pull (median is robust
  to the opener and any execute spike). Coarse (binned to the timeline buckets), ours vs benchmark, lower
  better. Complements the per-boss opener caption with a tier-wide "who starts slow" read.
- **Buff & Debuff Coverage Gaps** (`tier_uptime_gap` → `tierUptimeGapView`) — each
  aura's avg uptime, listing only where we trail (biggest deficit first).
- **Debuff Ramp & Continuity** (`debuff_timing`/`tier_debuff_timing` → `debuffTimingView`) —
  **EXPERIMENTAL**, the two time dimensions a flat uptime % hides: per key debuff (`KEY_DEBUFFS`), **when
  it was first established** (first `band` start, sec into fight) and its **longest continuous gap** after,
  averaged across shared bosses, slowest-to-establish first. Casters/melee lose damage until CoE / Sunder /
  Misery / Judgement land. Benchmark-relative on purpose — a phased fight delays the boss debuff on **both**
  sides, so the **Δ** (not the raw seconds) is the signal; only debuffs both raids applied are shown.
- **Interrupts Leaked** (`leaked_casts`/`leaked_interrupts_gap` →
  `leakedInterruptsView`) — interruptible casts that went off, tier-wide. **Soundness:**
  no "interruptible" flag exists; the Interrupts table only lists abilities kicked ≥1×,
  so `spellsInterrupted >= 1` is our proof an ability is interruptible. Leak = a
  **hostile** cast in `missedCasts` (friendly excluded); we do NOT use `spellsCompleted`
  (no caster-type proof). **Under-counts, never over-counts** (an ability never kicked
  is absent entirely — stated in the UI hint). Worst leak (Δ≥2) feeds the scorecard.
- **Cooldown & Trinket Usage** (`cd_usage_pool`/`tier_cd_usage` → `cdUsageView`) —
  major DPS cooldowns + on-use trinkets per minute, pooled by (class, spec). Clean
  better/worse. **Sourcing (verified live):** off-GCD cooldowns (Death Wish,
  Recklessness, Bestial Wrath, Rapid Fire, Arcane Power, Icy Veins…) fire **no cast
  events** — only buffs w/ `totalUses` → read per-player buff `uses` (`COOLDOWN_NAMES`).
  Trinkets are the inverse: *use* logs as a cast under item name, buff renamed to effect
  ("Haste") → read from Casts (`TRINKET_NAMES`). Disjoint, no double-count.
- **Bloodlust — Timing & Payoff** (`lust_window_mult` + per-boss `lust_sec` → `bloodlustView`) —
  **EXPERIMENTAL**, per boss: **when** each raid popped Bloodlust/Heroism (`lust_sec`, seconds into the
  fight) and the **window payoff** — raid DPS in the 40s lust window ÷ the fight-average DPS (binned off
  the timeline curve), so >1× = cooldowns/trinkets stacked into the haste window. Timing is **descriptive**
  (on-pull for burn-now fights, saved for a phase on others — the benchmark is the reference, not a target);
  the payoff has a clean direction (higher = better-aligned burst). A third column, **CDs in window**
  (`cooldown_lust_alignment`), is the share of major DPS cooldown TYPES (`COOLDOWN_NAMES`) whose buff
  `band` overlapped the lust window — did the burst actually coincide with lust (counts types, not
  activations: you can't hold a 2-min cooldown for one window). Graceful "—" when a side didn't lust /
  has no timeline. Assembled from the per-boss `oursLustSec`/`oursLustMult`/`oursLustCd` fields.
- **Rotation — Ability Mix** (`rotation_buckets`/`tier_rotation` → `rotationView`) —
  per spec both raids fielded, **share** of casts per ability (from the **Casts** table;
  `dd.abilities` only covers damaging). DPS + Healer sub-tabs (`data-rtab`). Specs
  within `collapse_diff` (5pp) collapse to a green "matches benchmark" chip. **Descriptive,
  not scored** (cast mix is gear/talent/fight-driven); spec grain; `min_share` drops fillers.
- **Early Aggro — Threat Pulls** (`threat_pulls` → `threatPullsView`) — new modality
  (`table(Threat)`): per boss, count of times a **non-tank** held the **named boss's**
  aggro, + opener count (first 30s). Clean better/worse (fewer = better). **Two scopings
  (verified live):** (1) only the target whose name == encounter (counting all enemies
  reads 131% on Al'ar — that naive metric was NOT built); (2) only **brief** holds (≤15s
  — a sustained hold is an intended off-tank). Tanks/pets excluded. Under-counts. Opener
  count feeds the scorecard.
- **Target Focus** (`focus_view` → `focusFireView`) — avg share of raid damage on the
  single most-focused enemy per time slice (higher = concentrated). **Free** — binned off
  the Timeline's DamageDone pull by `targetID` (`_binned_curves`). Shown only when both
  sides multi-target (`multiTarget`: top-enemy share <80% AND ≥2 enemies ≥5%). Descriptive.
- **Add Control — Kill Speed** (`target_engagement`/`_targets_by_name` →
  `targetEngagementView`) — per boss >1 target, for each non-boss add both raids engaged,
  survival (median first→last hit), ranked by how much **slower** we are. A slower add =
  focus/CC/assignment target (e.g. Al'ar Embers 132.6s vs 42.9s). Boss row dropped (just
  restates kill time). Descriptive (some adds held on purpose). Add names from `masterData`;
  targets <1% of fight damage dropped. [] when no shared add. No extra fetch.
- **Output Quality** — time-weighted Raid DPS/HPS, avg activity (`dd.activeTime`/dur),
  damage taken ex-tanks (`dt`, with a per-sec/overall toggle), overheal (`heal.overheal`).
  **DPS gap diagnosis** (`dps_diagnosis` → `quality.dpsDiagnosis`) splits the raid-DPS
  deficit into an **activity** (uptime/movement) vs **throughput** (gear/rotation/buffs)
  component — what *kind* of fix. An estimate; silent unless we trail on raid DPS.
- **Healing Efficiency by Spec** (`heal_eff_buckets`/`tier_heal_eff_gap` → `healEfficiencyView`) —
  **EXPERIMENTAL**, the per-healer-spec decomposition of the raid **Overheal %** number (sits right under
  Output Quality). Each healer spec's overheal % (overheal ÷ (overheal + effective), pooled across shared
  bosses) ours vs the benchmark's **same spec**, biggest excess first — names which healer spec is
  splashing/sniping inefficiently (coachable on spell choice, snipe discipline, assignments). Same-spec
  comparison cancels the structural HoT-vs-direct-heal overheal difference (Resto Druid ~67% on both
  sides), leaving the residual Δ as the real signal. Specs with no benchmark same-spec ride along as a
  first-party absolute note (overheal% is a valid absolute — lower is tighter). DPS got DPS-by-spec and
  Activity got Activity-by-spec; this completes the set for Overheal. (Note: NOT decomposable by *spell* —
  the Healing table carries `overheal` only at the player level, not per ability.)
- **Clear Efficiency** (`efficiency`) — first-pull→last-kill wall-clock vs in-combat time,
  **scoped to shared bosses** on each side (filters fights to shared encounters — the bug
  fix: the old full-report span was meaningless when the two reports covered different
  content).
- **Wipe Recovery** (`wipe_recovery`/`wipe_recovery_compare` → `wipeRecoveryView`) — **EXPERIMENTAL**,
  per boss: average wall-clock between a **wipe ending and the next pull starting** — the raid's reset/
  rebuff/re-pull pace on progression, plus a raid aggregate + each boss's worst gap. Needs `attempts.json`
  with `startTime`/`endTime` (added to the attempts query; older folders without them → graceful empty).
  The gap includes breaks/strategy, so it's **directional** (tighter = more attempts a night), not a pure
  reset. Largely **first-party** — a benchmark on farm wipes little, so its column is often "—".

## Execution — per-boss drill-down

Each boss is a card (output strip + eight sub-tabs; **Timeline** is the default):

- **Timeline** (`timeline_view` → `timelineChart`/`tlChart`) — Raid DPS+HPS over the
  fight, ours vs benchmark, on a shared **absolute-seconds** x-axis: each curve point i
  sits at i/(n-1) of its OWN duration, so the shorter kill's line ends earlier (that gap =
  benchmark finishing sooner). Death ticks (▲), Bloodlust (⚡, full-height per side), all at real
  seconds. Phases live in a slim two-lane **phase track** below the x-axis labels (benchmark on top,
  ours below), each side's fight drawn as alternating P1/P2/… segments on the same x-scale — the lanes'
  boundaries differ because the timelines do (full-height dividers would fake an alignment that isn't
  there). The track only renders when a side has phase transitions. Inline SVG, no libs. **Curves from events, not `graph()`** (see Timeline note
  below). **Opener caption** (`opener_gap` → `b.openerGap`): first ~30s of raid DPS, reddened
  only if we trail.
- **Buff Uptime** — boss debuffs + raid buffs, value←bar—name—bar→value, sorted by delta.
- **DPS by Spec** (`spec_gap` → `specDpsView`) — DamageDone bucketed by (class, spec) for
  DPS, ranked by per-player deficit (avg/player, so 3-vs-2 mages stays fair). Spec grain, no
  per-player drill-down.
- **Damage Taken** — top sources (honors the per-sec/overall toggle).
- **Deaths** — who/spec (parsed from death `icon`)/killing blow/when. "Clean kill" if none.
  **"When you died"** (`death_timing`): the phase or third where our deaths cluster — silent
  unless ≥3 deaths AND ≥40%-in-one-phase / ≥45%-in-one-third. **"Cascade"** (`death_cascades`):
  ≥4 deaths in a 15s window (near-wipe burst).
- **Interrupts** (`int_break`/`int_compare` → `interruptView`) — **ability-first**: one row
  per interrupted ability, kicking specs nested under it, ours vs benchmark ("they kicked it
  with Fire Mages, you used Ele Shaman"). Descriptive. Below: **Casts That Went Off Un-kicked**
  (leaked = `missedCasts[]` filtered to hostile casters).
- **Dispels** (`disp_compare` → `dispelsView`) — which enemy auras each raid *chose* to remove,
  how often. **Descriptive, neutral Δ** (more dispels ≠ better; a debuff can be dispellable yet
  un-kickable). Kept per-boss (tier-wide would lose which fight).
- **Phases** (`phase_compare`) — per-phase duration + share, delta, from `phaseTransitions`.
  **Phase NAMES** from report-level `report.phases` (`PhaseMetadata{id,name}`, populated in TBC
  for scripted bosses e.g. Kael "P5: Gravity Lapse"), joined by id (`phase_name_map`); fall back
  to "Phase N". Single-phase fights show a graceful note.

---

## Optimize

`build_optimize` → `renderOptimize`/`optSpecBody` (wired by `mountOptimize`). The **only per-player
view in the report** (a deliberate exception to the otherwise raid/spec-level rule) and the only one
benchmarked against the **world**, not the comparison guild. Two nested tab levels: **class** sub-tabs
(`data-octab`) → **spec** sub-tabs (`data-ospec`, scoped per class via `data-ocls` so distinct classes
don't collide — mirrors the Bosses-tab wiring). Within a spec, each of our raiders' cast SHARE per
ability is mirror-barred against a same-faction world-best player's, reusing the Rotation view's layout
(`dmgcmp`/`ugrid`). Raiders within `collapse_diff` (5pp) on every tracked ability collapse to a green
"matches world best ✓" chip; the rest get the full table. **Descriptive, not scored** (same rule as the
Rotation view — a different mix can be gear/talent/fight-driven). DPS + healer only (tanks have no clean
ranking metric); `min_share` (3pp) drops fillers.

- **Benchmark selection** — `fetch_worldbest.py` (fetch stage; needs the network, so NOT in the pure
  `build_deepdive` path) resolves, per distinct DPS/healer (class, primary-spec): the highest-ranked
  **same-faction** entry from `worldData.encounter(id).characterRankings(metric, className, specName)`,
  walking the shared bosses in order and taking the first boss that yields a same-faction hit. It then
  fetches that player's **Casts** table for their ranked `report{code,fightID}` and writes raw ability
  tallies + player meta to `worldbest.json` in our data dir. `metric` is `hps` for healers, `dps`
  otherwise. **Faction:** a guild's `GameFaction` id is 1=Alliance/2=Horde, but a ranking entry's raw
  `faction` int is 0=Alliance/1=Horde, so the same-faction filter is `entryFaction == guildFactionId - 1`
  (verified live). Our roster's spec strings (`BeastMastery`, `Survival`, …) match the API's `specName`
  verbatim — no mapping.
- **Same-encounter integrity** — each spec is benchmarked on the boss its world-best player parsed
  (which our raiders also killed), and our raiders' casts are read from that **same** `boss-<enc>.json`,
  so both sides' cast shares come from the same fight. The spec header names the boss + the world player
  (`World #N <Faction> <Spec> <Class> on <Boss> · <amount> DPS/HPS`).
- **Caching** — `worldbest.json` lives in our data dir alongside the deep data; `compare_raids`
  refetches it when our data isn't cached, on `--refresh`, or when an older cached dir predates the file
  (so re-running over a cached report backfills the tab). A fetch failure is non-fatal — the rest of the
  report still builds; the tab renders an empty-state note. Graceful `{present:false}` when the file is
  absent or our raid had no resolvable guild faction (a PUG night).
- **Hit/Expertise cross-link** (`hit_map` from `stat_audit_compare` → `optBossBody`) — **EXPERIMENTAL**,
  a per-raider note on a *diverging* row when the Prep stat audit flagged that raider **under their
  effective-hit cap**: "effective hit 12% vs the 16% cap — missed casts can distort this mix; closing it
  is a gem/enchant fix, not a rotation change." Explains *why* a rotation diverges with a concrete, fixable
  gear lever rather than scoring the rotation — coach-not-blame, and the soul's blessed absolute check
  (hit cap = wrong-vs-correct). Reuses the already-computed Prep audit; no extra fetch. Shown only when
  `under` is true, so it's silent for capped raiders.
- **Known wrinkle** — a hybrid who played the spec in a different role/form on the benchmark boss (a
  Feral who bear-tanked) reads a large, role-driven "gap"; inherited from the Rotation view, covered by
  the descriptive framing. Form-aware spec detection would sharpen it.

---

## Wipes

`wipe_analysis` → `renderWipes` (static panel, no mount). **EXPERIMENTAL** and **first-party by nature** —
a benchmark on farm rarely wipes, so its column is usually absent/0. Scoped to the **shared bosses** the
raid actually wiped on (names + wipe-death data are scoped there). Empty-state is a positive ("a clean
clear"). Per boss:

- **The Wall** (`wall`) — the phase the most wipes **ended in** + the typical boss-HP% remaining there
  (`lastPhase` + `fightPercentage` from `attempts.json`, phase id→name via `phase_name_map`). Names the
  phase gate to drill.
- **Progression Trend** (`_wipe_trend` + the `trendSeq` bar viz) — the %-remaining sequence across the wipe
  pulls, with a verdict: **converging** (closest attempt is recent — keep pushing), **plateaued** (clustering
  at one depth — change something), or **regressing** (further after early attempts — fatigue/tilt, reset).
  **Silent under 3 wipes** (no honest trend to call). Viz bar height = progress (boss HP removed; taller =
  closer to the kill).
- **The progression Tax** — wall-clock **time spent wiping** per boss + the raid total + the biggest
  time-sink boss. The cost the kill-time number hides (a "1 wipe" can be a 12-minute attempt).
- **What Ends Your Attempts** (needs `wipe-deaths.json`) — the most common **first death** (the failure that
  starts the cascade) + the **killing blows** on the wipe pulls, ranked. From the friendly Deaths table on
  the wipe fights (`fetch_report` writes `wipe-deaths.json`), bucketed to each pull by the entry's `fight`
  id. Graceful when absent (older folders): the progression sections still render, with a note that the
  death detail backfills on the next refresh. `hasDeaths` gates it.

Benchmark wipe counts ride along per boss as light context where present (`dp.wipes.theirs`).

---

## Trash

`build_trash` → `renderTrash`. WCL splits trash into pull **segments**
(`fights(killType:Trash)`), each named after its notable mob, with `enemyNPCs` (mob ids+counts)
and `masterData.actors` resolving ids→names. **Hybrid comparison rule:** benchmark-compare only
what aligns across guilds (deaths, CC, mob-type kill priority, exact-roster pack matches) — pull
boundaries don't align. **Scoped to shared zones:** `_trash_zones` intersection → `_filter_to_zones`
drops off-zone fights (each fight carries `gameZone{id name}`; older folders skip gracefully).

- **Trash at a Glance** (`_trash_glance`) — pulls, clear time, deaths. Clear time is a *rough*
  proxy (routes/skips differ); deaths are the clean signal.
- **What's Killing Us** (`trash_death_causes` + `_death_source_mob`) — trash deaths by killing
  blow, ranked by biggest improvable delta (ours−theirs). Each named blow carries the **source
  mob** in parens ("Fragmentation Bomb (Tempest-Smith)" — the actionable half), from the killing-
  blow event `sourceID` joined to the NPC map (fallback: top hostile `damage.sources`). "Melee"
  stays one row + a **by-mob** sub-table (`trash_melee_by_mob`). Source: the friendly Deaths table.
- **Chain-Pulling** (`trash_chain_pull`) — avg/max mobs per pull + count of LARGE pulls (≥10) +
  each side's biggest pull. WCL exposes **no pack object / baseline**, so "N packs merged" can't be
  inferred and we don't claim it. Descriptive, neutral Δ.
- **Trash Deaths by Pull Size** (`trash_deaths_by_pull_size` → inline in `renderTrash`) — **EXPERIMENTAL**,
  the honest one-level-deeper of the flat trash-deaths count: death-**rate per pull** bucketed by mob count
  (1–3 / 4–7 / 8–12 / 13+), ours vs benchmark. Solves the hybrid-comparison problem — pull boundaries don't
  align across guilds, but **death-rate-per-pull-of-size-N does** ("when you pull 8–12, how often does
  someone die, vs them?"). Sharp, aligned, better/worse. Raw deaths/pulls shown beside the rate (samples
  are small — be honest). Sits under Chain-Pulling (the size lever it pairs with).
- **Kill Order & Crowd Control** — outer toggle (`.btab[data-ttab]`, `mountTrash`): **Kill Order**
  (default) | **Crowd Control**. Kill Order nests two lenses (`data-ktab`):
  - **Same-Pack Matches** (default; `trash_identical_packs` → `sameMatchesBody`/`killSeq`) — kill
    order only for packs both raids pulled with the **exact same roster** (mob types AND counts;
    `_roster_sig` = sorted (name,count) from `enemyNPCs`). Identical roster ⇒ genuinely same pack
    (a merge won't match). `_typical_order` (median death time per type) shows your sequence over
    theirs, flagging any mob in a different slot. The trustworthy 1:1 view.
  - **Pairwise Priority** (`trash_pairwise_priority` + `trash_kill_priority` → `pairwiseBody`/
    `killLadder`) — needs no pack identity: an SVG slopegraph of every mob's pooled kill-priority +
    a per-pair "when A & B are both up, who dies first?" table (reversals flagged). Covers far more
    pairs. Descriptive.
  - **Crowd Control** (`trash_cc_by_mob` → `trashCcView`) — by-mob only (row per (mob, CC type),
    most-CC'd first; the old by-type summary was cut). Descriptive (more CC ≠ better). Count = landed
    `applydebuff`. **CC classified by NAME, not id** — unlike consumable buffs, CC debuffs keep their
    real name, so a curated allowlist (`report_common.HARD_CC_NAMES` / `cc_label`) is reliable and
    excludes look-alikes (Ice/Explosive Trap; Kidney/Cheap Shot, Gouge, Bash, Hammer of Justice are
    rotational stuns, not lockouts).

*(Removed in the soul audit: the single-raid Pack-by-Pack per-pull drill-down — the closest thing to
a raw data dump. `trash_packs`/`trashPacksView` and their CSS are gone.)*

---

## Data sourcing & fetch notes

Heavy tables (dd/heal/dt/intr/disp/**casts**/**threat**/**deaths**) are fetched only for shared
bosses (`fetch_report.py --full-encounters <ids>`; responses are large). `casts` powers Rotation +
the trinket half of Cooldown Usage; `threat` powers Early Aggro; focus-fire needs no extra fetch.
`phaseTransitions` + `report.phases` ride the cheap `fights` query (all kills).

**Wipe/attempt + depth** — one cheap query per report
(`fights(killType:Encounters){id encounterID kill startTime endTime fightPercentage lastPhase}` →
`attempts.json`); `attempt_map` tallies kills vs wipes + closest wipe's depth/phase, and `wipe_recovery`
uses the `startTime`/`endTime` (added for the Wipe Recovery view) to measure the gap between a wipe and the
next pull. Graceful without the file (and older `attempts.json` without timestamps → Wipe Recovery empty).
The **Wipes tab** adds one more cheap call: the friendly Deaths table for the shared bosses' **wipe** fight
ids (`fetch_report` → `wipe-deaths.json`, entries carry `fight` + `timestamp` + killingBlow so they bucket
to pulls client-side) — powers "what ends your attempts". Graceful when absent (the tab's progression
sections still render from `attempts.json`).

**Timeline curves** (`timeline-<enc>.json`, shared bosses) — `_binned_curves` pages DamageDone +
Healing events, bins `amount` into 40 buckets ÷ width → exact DPS/HPS-over-time. **From events on
purpose, not `graph()`:** `graph(viewBy:Source)` returns a rolling rate ~2× true DPS (drifts
1.9–2.1×), contradicting the time-weighted Raid DPS elsewhere — event-binning matches table totals.
~3–6 pts/boss/side (≈20–60 for a full comparison; cap is 3600/hr). `_side_timeline` emits each side's
`durSec` + markers as `tSec`/`lustSec`; graceful without the file (Timeline sub-tab falls back to Buff
Uptime).

**Trash data** — on by default in `fetch_report.fetch()` (or `--trash-only`); cheap (~7–9 calls):
deaths/CC come back in single paginated `events` calls keyed by `fight`, not per pull. Writes
`trash.json` (pulls + actors), `trash-deaths.json` (kill-order events + friendly death entries),
`trash-cc.json` (hard-CC aura table + apply events). `build_trash` is graceful without `trash.json`.

For a single-raid report, emit one "team" or extend the template — data shape documented inline.
