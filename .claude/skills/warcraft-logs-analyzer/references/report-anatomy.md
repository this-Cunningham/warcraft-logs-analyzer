# Report anatomy — the deep-dive comparison report

`build_deepdive.py` (invoked by `compare_raids.py`) injects a `const DATA` blob into
`templates/report.html` (inline CSS+JS, dark, offline, no CDN) by replacing the
literal `/*__DATA__*/null`. Six top-level tabs, a funnel:

| Tab | `data-t` | Question it answers |
|---|---|---|
| **Overview** | `overview` | Where's the gap, at a glance |
| **Readiness** | `enchants` | Did we show up set up to win — roster, buffs, consumes, gear (sub-tabs: **Roster & Buffs** · **Consumables** · **Enchants & Gear**) |
| **Combat** | `execution` | How the raid played the fights — a **dimension** (Output · Survival · Buffs & Cooldowns · Mechanics) × a **scope** switch (All shared bosses ⟷ each boss) |
| **Wipes** | `wipes` | Why we wipe (the wall, the trend, the tax, what ends attempts) |
| **Rotations** | `optimize` | How each raider's rotation compares to the world best |
| **Trash** | `trash` | How we handle trash packs (sub-tabs: **Overview** · **Deaths** · **Coordination**) |

The funnel was reorganized for legibility (layout only — no metric changed): the old
**Composition** tab folded into **Readiness** (the old **Prep** tab); the old **Execution**
(raid-wide) and **Bosses** (per-boss) tabs **merged into one Combat tab** with a scope switch,
so each dimension is defined once and re-scopes between the raid-wide aggregate and any single
boss instead of being duplicated across two tabs; the **Trash** tab gained inner sub-tabs;
**Optimize** was renamed **Rotations**. Tab `data-t` ids and panel ids are unchanged where they
survive (so the `dmgMode` re-render and the dynamic mounts keep working); the merged Combat tab
keeps `data-t="execution"`/`p-execution` and the `bosses` tab/panel were removed. Sub-tabs reuse
the `.btab`/`.bsub` idiom; `combatScope`/`combatDim` (module vars) persist the active scope and
dimension across the `dmgMode` re-render.

Most sections compare ours vs benchmark with a delta (B is whatever's loaded — a better
guild or your own past raid; some checks are absolute, no B); weak/ambiguous or hard-to-read metrics are deliberately omitted (the soul's accuracy + legibility floors — see `PRODUCT_MANAGER_SOUL.md`). Symbols below are
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
- The per-fight kill time, parse, rosters and the full execution drill-down live on the **Bosses** tab
  (the old Overview Boss-by-Boss / Kill Summary & Rosters block and the EXPERIMENTAL Parse Spread were
  cut in the /audit pass — see TODO.md).

---

## Readiness → Roster & Buffs (was the Composition tab)

`renderComposition` is now the **Roster & Buffs** sub-tab of Readiness (`renderReadiness`).
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

## Readiness → Consumables + Enchants & Gear (was the Prep tab)

`renderEnchants(d, group)` now renders one of two Readiness sub-tabs: `group="consumables"`
emits the five consumable sections below (Consumables Coverage → Opener Potion — Prepot);
`group="gear"` emits Enchants & Weapon Oils + Hit & Expertise + Item Level by Role. The split
is layout-only (each section's HTML is byte-identical; the section blocks are just guarded by
`wantC`/`wantG`). `renderReadiness` wires the three panes (Roster & Buffs · Consumables ·
Enchants & Gear) and `mountReadiness` toggles them via `data-rdy`.

- **Consumables Coverage** (`consumable_report`) — Flask/Elixir-Pair card reads
  per-player consumes (`_cell_for`), so a battle+guardian **elixir pair** counts as
  prepared like a flask (the aggregate Buffs table can't tell them apart). Food =
  per-player Well-Fed. Falls back
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
- **Throughput Consumables** (`throughputView`) — **Potions by Spec**
  (`potion_usage_by_spec`/`potion_gap`): combat-pot activations pooled by (class,
  spec), ranked by biggest deficit (clean better/worse — pure throughput). (The
  descriptive "Choices" flask/battle-elixir meta table was removed — it revealed no
  actionable gap; see the note in `build_deepdive.py`.)
- **Opener Potion — Prepot** (`prepot_timing` → `prepotView`) — **EXPERIMENTAL**, the *timing* decomposition
  of the potion-uses count: did the throughput potion land **on the pull** (the free TBC opener prepot,
  which shares a cooldown with the in-combat potion so skipping it wastes a potion) or only reactively
  mid-fight. From the aggregate Buffs `bands` (earliest potion band start vs fight start; ≤3s ≈ on the
  pull). **Scans THROUGHPUT potions only** (`THROUGHPUT_POTION_IDS` = Haste 28507 / Destruction 28508) —
  the defensive **Ironshield** potion (28515, in the usage `POTION_IDS`) is a tank damage-absorb, not a free
  DPS opener, so it must NOT count as a prepot or a tank's pull Ironshield fabricates a green "prepotted"
  cell and halves the real DPS-prepot gap. **Raid-aggregate** (bands merge across players) → an honest
  raid-level "opener potion on the pull: X/N bosses", NOT a per-player prepotter count.
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
  melee 9 · ranged 9); same-spec so talents (shared) cancel and a raid buff asymmetry (we run boomkins,
  they don't) doesn't wrongly flag our capped casters. Flag = a clear margin under target (2pp vs a real
  benchmark, 3pp vs the bare cap). Talent's real payoff is an HONEST effective-vs-cap read — a Shadow
  Priest at 6% gear is capped via Shadow Focus, not under (under-flag count 7→2 on the sample). Expertise
  shown benchmark-relative only (unit ambiguous, no absolute cap claim). Graceful "" on older folders.
  - **Summary cards compare GEAR+TALENT, not effective.** The "Avg Caster/Melee/Ranged Hit (gear+talent)"
    cards drop the raid Imp-FF component so the better/worse delta reflects the controllable itemization
    lever — otherwise an asymmetric boomkin buff (Imp FF on one side only) paints a green "we hit better"
    while our casters' own gear+talent hit is worse. Melee/ranged have no raid hit component, so there
    gear+talent == effective. The per-player table still shows full Effective hit + a **Role** column.
  - **Role-fluid Feral / tanks are not flagged on the bare-cap fallback.** A bear that tanks half the night
    legitimately deprioritizes gear hit; when the benchmark fielded no same-spec player to compare against,
    a Feral druid or a tank is not flagged `under` against the bare 9% cat cap (no invented gear gap).
- **Item level** — raid avg (`fights.averageItemLevel`) + **by role** (`role_ilvl`:
  dps/healer/tank from dd/heal/dt) so an under-geared role stands out.

---

## Combat — dimension × scope (was the Execution + Bosses tabs)

`renderCombat` is ONE dynamic panel (`p-execution`) with two axes: a **dimension** sub-tab
(`data-cdim`: Output | Survival | Buffs & Cooldowns | Mechanics) crossed with a **scope** switch
(`data-cscope`: `all` = the raid-wide aggregate, or one `<encounterID>` to drill into a boss).
A content cell shows only when BOTH its scope wrap and its dimension pane are `.active` (nested
`.bsub` cascade). The raid-wide bodies come from `combatAllDims(d)` (was `renderExecution`); the
per-boss bodies from `combatBossDims(b)` (was `execPanel`), reusing every existing renderer verbatim.
A boss scope also shows a header (name + Bloodlust badge + `statStrip`) above the dimension content.

Each dimension, by scope:
- **Output** — *All:* Output Quality (holds the `dmgMode` Per-second/Overall toggle), Clear Efficiency,
  DPS Gaps — By Spec, Melee Uptime on the Boss. *Boss:* Timeline (curves + ghost overlay), DPS by Spec.
- **Survival** — *All:* What's Killing Us, Time Lost to Deaths, Avoidable Damage by Mechanic.
  *Boss:* Damage Taken (by source), Deaths.
- **Buffs & Cooldowns** — *All:* Buff & Debuff Coverage Gaps, Debuff Ramp & Continuity, Cooldown & Trinket
  Usage, Bloodlust. *Boss:* Buff Uptime (boss debuffs + per-target zoom + raid buffs).
- **Mechanics** — *All:* Interrupts Leaked, Early Aggro — Threat Pulls, Add Control — Kill Speed.
  *Boss:* Interrupts, Dispels, Phases, Positioning.

The `dmgMode` toggle (in Output Quality, All scope) is honored by the per-boss Damage Taken and the
boss `statStrip` too, so it re-renders the whole `p-execution` panel; `combatScope`/`combatDim`/`tlTab`
persist the user's place across that re-render. Timeline inner tabs (`data-tlboss`), the ghost overlay
(delegated on `.ghostwrap`), and positioning `.postab`/zoom (delegated on `document`) all survive.

### Raid-wide ("All bosses") sections

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
  (Activity by Spec was cut in the /audit pass — no decision hung on it: it named a trailing spec's
  active-GCD uptime but couldn't say *why*, and the cause lives in Add Control / Damage Taken / Positioning.
  The raid-wide Activity aggregate still feeds Output Quality and the Overview scorecard. See TODO.md.)
  (Cut: *DPS Ramp* — seconds to reach 90% of the fight's median DPS. Its self-normalization to each raid's
  OWN median meant a weak raid (low median) could read a "fast ramp" while its absolute opener DPS trailed —
  an honesty wobble — and the opener caption already covers the start. `dps_ramp`/`dpsRampView` and the
  `deep.dpsRamp` payload were removed; the per-boss opener caption remains.)
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
  (Cut: *Rotation — Ability Mix*, a tier-wide per-spec cast-share-vs-benchmark table. It pooled a spec's
  casts across raids, which blended a bear-Feral's threat casts into the cat-Feral comparison (a form/role
  blind spot). Superseded by the **Optimize** tab, which compares each raider's rotation per boss against the
  world best with form/role awareness. `rotation_buckets`/`tier_rotation`/`rotationView`/`data-rtab` removed.)
- **Early Aggro — Threat Pulls** (`threat_pulls` → `threatPullsView`) — new modality
  (`table(Threat)`): per boss, count of times a **non-tank** held the **named boss's**
  aggro, + opener count (first 30s). Clean better/worse (fewer = better). **Two scopings
  (verified live):** (1) only the target whose name == encounter (counting all enemies
  reads 131% on Al'ar — that naive metric was NOT built); (2) only **brief** holds (≤15s
  — a sustained hold is an intended off-tank). Tanks/pets excluded. Under-counts. Opener
  count feeds the scorecard.
  (Cut in the /audit pass: *Target Focus* — avg share of raid damage on the single most-focused enemy per
  slice. It was redundant with **Add Control — Kill Speed** (which names the actual add) and read as
  scored despite being descriptive. `focus_view`/`focusFireView` and the `deep.focusFire` payload removed.)
- **Add Control — Kill Speed** (`target_engagement`/`_targets_by_name` →
  `targetEngagementView`) — per boss >1 target, for each non-boss add either raid engaged,
  survival (median first→last hit), ranked by how much **slower** we are. A slower add =
  focus/CC/assignment target (e.g. Al'ar Embers 132.6s vs 42.9s). Boss row dropped (just
  restates kill time). Descriptive (some adds held on purpose). Add names from `masterData`;
  targets <1% of fight damage dropped. A side that never engaged an add (×0) **skipped** it — the benchmark skipping an add we fought (its boss DPS out-paced the wave) is the biggest gap; the reverse is a lead. [] only when neither raid engaged a non-boss add. No extra fetch.
- **Output Quality** — time-weighted Raid DPS/HPS, avg activity (`dd.activeTime`/dur),
  damage taken ex-tanks (`dt`, with a per-sec/overall toggle), overheal (`heal.overheal`).
  **DPS gap diagnosis** (`dps_diagnosis` → `quality.dpsDiagnosis`) splits the raid-DPS
  deficit into an **activity** (uptime/movement) vs **throughput** (gear/rotation/buffs)
  component — what *kind* of fix. An estimate; silent unless we trail on raid DPS.
  (Cut: *Healing Efficiency by Spec* — each healer spec's overheal % vs the benchmark's same spec. On the
  sample it was extremely thin (only 1 of 6 specs had a same-spec benchmark to compare), so it rarely said
  anything actionable. The raid-wide Overheal % stays under Output Quality. `heal_eff_buckets`/
  `tier_heal_eff_gap`/`healEfficiencyView` and the `deep.healEffGap` payload removed.)
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

### Per-boss ("single boss" scope) sections — `combatBossDims(b)`

When a boss scope is selected, the same four dimensions show that boss's detail (the views below were
the old Bosses-tab sub-tabs, now distributed across Output / Survival / Buffs & Cooldowns / Mechanics):

- **Timeline** (`timeline_view` → `timelineChart`/`tlChart`) — Raid DPS+HPS over the
  fight, ours vs benchmark, on a shared **absolute-seconds** x-axis: each curve point i
  sits at i/(n-1) of its OWN duration, so the shorter kill's line ends earlier (that gap =
  benchmark finishing sooner). Death ticks (▲), Bloodlust (⚡, full-height per side), all at real
  seconds. Phases live in a slim two-lane **phase track** below the x-axis labels (benchmark on top,
  ours below), each side's fight drawn as alternating P1/P2/… segments on the same x-scale — the lanes'
  boundaries differ because the timelines do (full-height dividers would fake an alignment that isn't
  there). The track only renders when a side has phase transitions. Inline SVG, no libs. **Curves from events, not `graph()`** (see Timeline note
  below). **Opener caption** (`opener_gap` → `b.openerGap`): first ~30s of raid DPS, reddened
  only if we trail. **Inner tabs: Raid · Melee DPS · Ranged DPS · By spec** — the two aggregates stay as
  tabs; the individual per-spec curves collapse behind the **By spec** tab's dropdown (`select.tlspecsel`,
  `tlSpec[enc]` persists the choice across the `dmgMode` re-render) so the bar is ~4 tabs, not a dozen.
  Each spec's curve (`spec_timelines`/`_spec_curves`) is plotted **PER PLAYER** (summed bins ÷ bin width ÷
  the spec's distinct player count) — matching the DPS-by-Spec table's avg/player, so a side with more
  players of a spec doesn't draw ~Nx taller when each player is worse. The Melee/Ranged aggregate curves
  sum those per-player spec curves over overlapping specs; the per-spec title annotates each side's player
  count when they differ.
  - **Ghost Run overlay** (EXPERIMENTAL, `ghostInner`/`computeGhost` over `deep.ghostRun`, on the Raid-DPS
    sub-view) — a master toggle draws a dashed-green **ghost line**: your raid DPS as if the costliest DPS
    deaths hadn't happened (each revived raider projected at their **night-average DPS** from death to kill),
    with the shaded gap = output the deaths consumed and a green **projected-kill** marker. **Per-death
    toggles** revive/down each raider individually, recomputing the curve + projected kill incrementally —
    so a leader can isolate what just one death cost. **Upper bound** (assumes the raider sustains their
    average, no battle-res, no phase gate). Moved here from a standalone Execution text block (TODO.md) so
    the cost lands in the fight's shape — *when* the deaths hurt, not just how much.
- **Buff Uptime** — boss debuffs + raid buffs, value←bar—name—bar→value, sorted by delta.
  On a multi-target boss a **Debuffs-by-Enemy-Target zoom** (`per_target_debuffs` → `targetDebuffsView`)
  decomposes each key debuff's uptime per enemy (normalized to that enemy's *engaged* window). Cells whose
  raw debuff ms implausibly exceeds the enemy's active window (>110% — a multi-instance / fight-end
  force-close artifact on reused phased-add NPC ids that would otherwise CLAMP to a fake 100%) are
  **dropped, not laundered**, so the zoom can't manufacture a false "they held it, you didn't" lever.
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
  how often. **Counts only removals whose TARGET actor is hostile** (`details[].actors[].type` in
  Boss/NPC): the WCL Dispels table also lists friendly cleanses (a Mind-Control break, an ally poison-cure),
  which are defensive plays, not enemy-aura removals — including them would mislabel the view and inflate the
  count. **Descriptive, neutral Δ** (more dispels ≠ better; a debuff can be dispellable yet
  un-kickable). Kept per-boss (tier-wide would lose which fight).
- **Phases** (`phase_compare`) — per-phase duration + share, delta, from `phaseTransitions`.
  **Phase NAMES** from report-level `report.phases` (`PhaseMetadata{id,name}`, populated in TBC
  for scripted bosses e.g. Kael "P5: Gravity Lapse"), joined by id (`phase_name_map`); fall back
  to "Phase N". Single-phase fights show a graceful note.

---

## Rotations (the Optimize tab; `data-t="optimize"`)

Tab labelled **Rotations** in the nav; the in-panel section header keeps "Optimize — Rotation vs World
Best" for recognition. `build_optimize` → `renderOptimize`/`optSpecBody` (wired by `mountOptimize`). The **only per-player
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

`renderTrash` groups its sections into three inner sub-tabs (`data-trsub`, wired by `mountTrash`'s
generic `wire("trsub")` — distinct from the nested `data-ttab`/`data-ktab` toggles it preserves):
**Overview** (Trash at a Glance + Chain-Pulling), **Deaths** (What's Killing Us on Trash + Trash Deaths
by Pull Size), **Coordination** (Kill Order & Crowd Control). Layout-only regroup of the existing sections.

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

## Positioning (EXPERIMENTAL)

The five flagship positioning features (`positioning.py` → server-rendered stdlib-SVG/HTML fragments
injected into the template; built in `build_deepdive.build`'s per-boss loop + a tier rollup). All ride
ONE new artifact — `positions-<enc>.json` per shared boss — and embed next to the boss/mechanic they
explain (**no new top-level tab**, per the brainstorm's embed guardrail). Honesty: WCL x/y are a linear
transform of yards (isotropic), so relative geometry is exact; every yard figure is labelled ~approx and
only the ours-vs-benchmark ratio is leaned on — never an absolute yard, compass bearing, or HP.

- **Overview headline** (`spread_headline` → `deep.positioning.headline`) — the single biggest
  spread-vs-demand gap across vetted bosses, when we're past the benchmark by a real margin. Silent
  otherwise (an honest "no positioning gap here", as on the pinned Imminent matchup).
- **Execution → Melee Uptime on the Boss** (`melee_uptime` per boss + `melee_uptime_view` →
  `deep.positioning.meleeView`) — sits right under Lowest-Hanging DPS as the geometric cause beneath a DPS
  gap: the share of
  melee samples within the ~melee ring of the boss (soft in/edge/out band, time-weighted), ours vs
  benchmark, per boss. **Gated to non-mobile bosses** (on a mobile boss it would measure the boss's path,
  not melee discipline); the ours-vs-benchmark delta on the SAME boss cancels the shared boss-path.
- **Bosses → per-boss "Positioning" sub-tab** (`boss_positioning` → `perBoss[].positioning`, a 9th boss
  sub-tab, present on any boss with a positions file — including **mobile** bosses, see below):
  - **Raid formation & spread** (feature 2) — side-by-side formation maps (role-coloured dots, **boss diamond +
    dashed ring and white add squares drawn ON TOP of the player dots**, per-actor + add **facing arrows**
    where captured) + the spread-vs-demand verdict. When phase data exists, the single whole-fight median map
    is replaced by **phase-anchored snapshots** (`_plant_windows` + `_match_moments` + `_formation_at`), shown
    as **labelled TABS** (`Opener` / numbered re-plants / phase tags like `P2`, switched by a delegated
    `.postab` handler): the raid's *settled* formation at the opening + each phase start + every boss
    **re-plant** (a few seconds in, so it's the formation, not the transition scramble), ours vs benchmark per
    moment — *where the raid stood when it mattered*, not a whole-fight smear. **The two raids share ONE
    absolute frame at REAL positions** (`_window_frame`) — not aligned or boss-centered — so a positioning GAP
    (a different tank spot, a looser spread, the wrong side of the boss) reads as a real offset to point at,
    which is the whole purpose of the view. A non-mobile boss uses one frame across all moments (read drift as
    the raid moves within a stable window); a MOBILE boss uses a tight per-moment frame (its stands are
    different platforms). Falls back to one shared-frame whole-fight map when no plant window is detected.
    **Mobile bosses (Al'ar) DO render** their planted-window snapshots (only the whole-fight single-panel map
    is skipped — that one really would smear across the arena). The melee-uptime view and the whole-fight
    single map stay non-mobile. Spread is a robust **spread radius** (`spread_radius_yd`:
    median per-bin distance to the cohort's median centroid — resists both the stacked-raid median-collapse
    and max-range-ranged outliers), not median-NN. The spread/stack VERDICT fires only for a curated `DEMAND`
    set (Void Reaver, Solarian, Vashj, Leotheras); elsewhere the numbers are descriptive with no "you should…"
    arrow.

  (Features 1 "Why we eat more <ability>", 4 "Void-zone density heatmap", and 5 "Spread over time" were
  cut in the /audit pass — EXPERIMENTAL, buried in a sub-tab, and redundant with Execution → Avoidable
  Damage by Mechanic. Only feature 2 (formation map + spread-vs-demand verdict) remains.)

Boss auto-class (`boss_travel_yd`/`boss_class`: STATIONARY/PLANT-AND-MOVE/MOBILE from the **max** of both
raids' total boss travel — so a boss mobile on either pull is treated as mobile) gates which features make
sense: a MOBILE boss renders its plant-window snapshots (tabbed, real positions) but NOT the whole-fight
single map or the melee-uptime row. Graceful when a data folder predates the positions fetch
(the views simply don't render). See the `warcraft-logs-positioning` skill's `references/` for the
coordinate system, the centiradian facing decode, and rendering rules.

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

**Positions** (`positions-<enc>.json`, shared bosses) — `_fetch_positions` sweeps three resourced event
streams with `includeResources:true` (DamageTaken + Casts for player tracks, `DamageDone targetID:<boss>`
for the boss anchor; boss actor id resolved by NAME from masterData), then BINS them here (per-actor +
boss median position per ~2s time bin) + accumulates per-ability hit spots — so the heavy event payload
never reaches the deterministic build (same fetch-aggregates / build-reads split the timeline uses).
~6 pts/boss/side (resources are free, single page on TBC fights). `--positions-only` backfills the file
into an existing data folder without re-pulling the heavy tables (mirrors `--trash-only`). Graceful
without the file (Positioning views just don't render). Powers `positioning.py` (see the Positioning section).

**Trash data** — on by default in `fetch_report.fetch()` (or `--trash-only`); cheap (~7–9 calls):
deaths/CC come back in single paginated `events` calls keyed by `fight`, not per pull. Writes
`trash.json` (pulls + actors), `trash-deaths.json` (kill-order events + friendly death entries),
`trash-cc.json` (hard-CC aura table + apply events). `build_trash` is graceful without `trash.json`.

For a single-raid report, emit one "team" or extend the template — data shape documented inline.
