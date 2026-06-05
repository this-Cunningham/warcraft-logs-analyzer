# Positioning — Feature Brainstorm

> Auto-generated from a multi-agent brainstorm + adversarial KEEP / SHARPEN / CUT filter over the Warcraft Logs positional dimension (`events(includeResources:true)`). 47 ideas were generated across 7 lenses; this doc keeps the **32 that survived** the filter (the 15 cuts have been removed). Section 1 is the decision-ready synthesis; Appendices A-B list every surviving idea.

---

# 1. Synthesis

## Positioning Features — Decision-Ready Brainstorm

### 1. What positioning unlocks

The report today says *what* happened and *how much* (DPS, deaths, damage-taken by mechanic) — positioning adds the missing **where**. `events(includeResources:true)` gives every resourced hit/cast a faithful x/y, so the same gaps the report already headlines ("we eat 2.3x more Spore Cloud," "37s slower kill") can finally be split into **spacing/geometry causes vs throughput/timing causes** — which routes a raid leader to the right fix (drill spread vs chase gear). The honest, caveat-safe modality is **relative geometry** (distance, spread, clustering, in/out-of-ring) compared ours-vs-benchmark on one shared scale; absolute yards, compass directions, player HP, and mana are all off-limits, and none of the keepers need them.

### 2. Clusters

#### A. "Where the bad lands" — turning an existing damage/death gap into a *where*
*So what:* the report already ranks which abilities we over-eat; positioning says whether the cause is spatial (a fix) or not (route elsewhere).

| Idea | Where it lives | Action it drives | Leverage | Feasible? |
|---|---|---|---|---|
| Why we eat more of this ability — positional cause for the avoidable-damage gap | Execution / Bosses, beside avoidable-damage gap | clustered = spacing fix; scattered/at-range = CD/healing fix | **high** | yes |
| Void-zone overlap heatmap (where the bad accumulates) | Bosses per-boss "Positioning" sub-section | "stop fighting in the [region]; benchmark clears out" | **high** | yes |
| Death-location cluster annotation (merge of Wipes mini-map + Bosses death overlay + benchmark death-spot) | Wipes "What Ends Your Attempts" (single-side, OUR deaths) | clustered = movement/spot fix; scattered = timing/CD fix | low | yes (gate ≥4–5 deaths) |

#### B. Raid spread/stack — the root cause the Damage-Taken/Deaths tabs only state
*So what:* one curated-mechanic feature covering both "should've spread" and "should've stacked," driven by raw time-windowed samples (never medians).

| Idea | Where it lives | Action it drives | Leverage | Feasible? |
|---|---|---|---|---|
| Spread-vs-demand index per shared boss (stack-bosses vs spread-bosses, direction arrow) | Bosses badge + worst gap on Overview | "call a wider spread / tighter stack for [mechanic]" | **high** | yes |
| Spread/stack at the moment damage lands (chain-breadth form) + stack-compliance + spread-at-AoE column | folded into the Spread feature | "loosen spacing / everyone stack on [mechanic]" | medium | partial→yes (as ratio, not yards) |
| Healer spread / clumping | folded in, allowlisted void-zone fights only | "split healers so one void zone can't drop the team" | low | yes |
| Tank separation on cleave/frontal bosses | folded in, flagged cleave bosses only | "pull boss out / turn away; off-tank to far side" | medium | yes |

#### C. Spread *through time* — when in the fight geometry breaks
*So what:* narrows the drill from "this boss" to "this phase/cast window."

| Idea | Where it lives | Action it drives | Leverage | Feasible? |
|---|---|---|---|---|
| Spread-over-time gap strip (radius of gyration, phase markers) | Bosses, near DPS/HPS timeline | "drill P2 spread, not the whole fight" | **high** | yes (gate to multi-phase spread bosses) |
| Formation tightness through time (does the raid spread on cue) | merge into the strip; two anchored aggregates [cast−3s,cast] vs [cast,cast+3s] | "benchmark peaks at cast−3s, we peak at +2s: pre-spread on the timer" | medium | partial |

#### D. Melee/ranged geometry — the spatial reason behind a DPS/kill-time gap
*So what:* decomposes the existing Activity-by-Spec / DPS-gap number into a no-gear positioning lever.

| Idea | Where it lives | Action it drives | Leverage | Feasible? |
|---|---|---|---|---|
| Melee uptime gap — geometry behind a DPS/kill-time gap (merge of all 4 melee-uptime variants) | Execution under Activity-by-Spec; per-boss strip | "melee in-range 74% vs 91% — pre-position, stop chasing" | **high** | yes (anchor to time, not event count) |
| Behind-the-boss uptime (cleave/parry-haste) | Execution / per-boss, gated to cleave bosses | "get behind [boss] — eating cleave/parry-haste" | medium | partial (needs facing calibration) |
| Ranged "too close" distance | only beside a confirmed cleave/orb harm signal | "push casters back to clear the cleave zone" | low | yes (conditioned on harm) |
| Movement vs throughput attribution flag for the DPS gap | Execution, inside existing DPS-gap diagnosis | flips "drill movement" vs "chase gear" | medium | partial (directional flag only) |

#### E. The visual surface + meta
*So what:* the map is the eye-test; the rule is "embed next to the mechanic, no new tab yet."

| Idea | Where it lives | Action it drives | Leverage | Feasible? |
|---|---|---|---|---|
| Side-by-side formation map (raw-sample spread stat, median dots ok for "where they set up") | Bosses per-boss collapsible sub-section | "spread to the benchmark's footprint" | medium | partial (stat must be sampled, not median) |
| Boss-displacement scalar ("they moved it 1×, you 6× → park one tank") | Bosses, hard-gated to parkable bosses | "designate one tank position" | low | yes (tiny eligible set) |
| Embed-first / no-new-tab guardrail | meta constraint on all above | ship embedded; promote to a tab only at 3+ maps + death overlay | n/a | yes |

### 3. Build-first shortlist (ranked by leverage × feasibility × fits-existing-tab)

> **SHIPPED (2026-06-05).** All five below are implemented — `positioning.py` (analysis + stdlib-SVG
> render) reading `positions-<enc>.json` (`fetch_report._fetch_positions`), wired into `build_deepdive`
> and the template: feature 1+4+5+the map in a per-boss **Positioning** sub-tab on the Bosses card,
> feature 2 also as an Overview headline, feature 3 in Execution under Activity by Spec. No new top-level
> tab (the embed guardrail). See `references/report-anatomy.md` → "Positioning". Implementation notes that
> diverged from this plan: median-NN was replaced by a robust **spread radius** (median dist to the median
> centroid) because a stacked raid collapses NN to sub-yard; the melee ring was widened to ~12 computed-yd
> (computed yards run ~1.3× true since SCALE is a floor); the ability scatter requires ≥5 distinct non-tank
> targets so self-damage/melee can't masquerade as a mechanic; bosses are auto-classed STATIONARY/PLANT/
> MOBILE and MOBILE bosses get no section.

1. **Why we eat more of this ability — positional cause** *(flagship; flagship-tier effort)* — rides `avoidable_damage_gap`/`ability_agg` which already pick the ability + id; turns a bare intake-rate delta into a clustered-vs-scattered verdict that names the fix. Gate to the single top intake-gap ability on the one worst boss to cap the heavy fetch at 1 boss × 2 sides.
2. **Spread-vs-demand index per shared boss** *(flagship)* — the single most reusable raid-level scalar; one number + direction arrow per boss, worst gap on Overview. Needs the curated stack/spread per-boss table (small, stable, ~6–8 bosses) and phase/cast-gated windowing. This *is* the "Raid Spacing" feature everything else folds into.
3. **Melee uptime gap (geometry behind the DPS/kill-time gap)** *(quick-ish win once the fetch exists)* — slots directly under Activity-by-Spec as its spatial cause; render only when on-boss% diverges >5pts from activeTime% so it's never redundant pixels. Anchor to stationary/slow bosses (Void Reaver, Gruul) so the action stays "stop chasing," not "the boss kited."
4. **Void-zone overlap heatmap** *(quick win — renderer + ability filter both exist)* — most directly feasible *visual*; reuse `compare_fights.py` side-by-side + drive the filter from the boss's top `avoidable_damage_gap` rows so where and what agree. Describe hotspots relative to the boss marker, never compass.
5. **Spread-over-time gap strip** *(flagship)* — reuses already-fetched phase infrastructure; converts a static spread delta into "the gap opens in P2," the narrowest possible VOD-drill instruction. Bucket by phase-fraction (fights differ in length) with a min-actor floor + carry-forward.

All five ride data we'd fetch once anyway (a single new `events(includeResources:true)` pull per shared boss × side) and slot into **existing tabs** — no new tab.

### 4. The flagship

**"Why we eat more of this ability — positional cause for the avoidable-damage gap."**

It is the highest-leverage feature because it doesn't invent a metric — it **completes one the report already headlines**. Today the avoidable-damage gap says *"we take 2.3×/sec more [ability] than the benchmark"* and stops. Positioning reads the target position (`resourceActor=2`) at each hit of that exact ability and renders one ours-vs-theirs scatter:

- **Reads as a gap:** *"Spore Cloud — we eat 2.3×/sec more than the benchmark. Our hits cluster in one zone (38 of 41 within a small radius of the boss's SE); the benchmark's are scattered/at-range."*
- **Concrete action:** clustered ⇒ **"this is a spacing fix — half the raid is clipping the same hazard zone; mark a spread/clear-out spot."** Scattered/at-range ⇒ **"not positional — it's a cooldown/healing problem; assign a CD, don't drill movement."**

That single clustered-vs-scattered verdict converts an inert number into a routed decision, respects every caveat (relative clustering only — no yards, compass, HP, or texture), and is gated to one boss × one ability so the heavy fetch stays cheap. The "scattered = not positional" outcome is a *useful* negative, which is what keeps it honest.

### 5. Open calibration question

**The boss `facing` → x/y-frame affine (zero-direction + sign), calibrated once per zone on a stationary, known-orientation boss.** Everything else in the keeper set is pure isotropic distance/clustering, which is already exact and needs no calibration — the WCL→true-yard affine is *not* worth chasing (relative ratios cancel the scale; absolute yards stay banned regardless). The one genuinely locked capability is **`facing`**: calibrating it unblocks **behind-the-boss / cleave / parry-haste uptime** and a trustworthy **tank "facing toward vs away from raid"** read — the only insights that cross from the well-understood position frame into the uncalibrated facing frame. Buy that one calibration and the melee-rear% feature graduates from "partial" to shippable; skip it and that family stays out.

---

# 2. Facing-dependent family — *requested: fold boss / adds facing in*

You asked to include **boss/adds facing** in these calculations. Facing *is* present on every resourced event, but its **unit, sign, and zero-axis are uncalibrated against the x/y frame** — so this entire family is gated behind one calibration spike (see the synthesis's *Open calibration question*: prove facing on a stationary known-orientation boss like Void Reaver). The **safe** form is always a *relative* bearing (player position vs. boss heading), never absolute compass degrees.

**Surviving facing-powered ideas:**

- **Behind-the-boss uptime for melee (cleave/parry-haste avoidance)** (Mechanics & avoidable damage, _SHARPEN_) — "Melee: get behind [boss] — only 55% of your swings are from the rear vs benchmark's 90%; you're eating cleave/parry-haste."
  - _Sharpen:_ Prove a per-zone facing→x/y-frame calibration on a stationary known-orientation boss BEFORE building; gate to bosses with real frontal cleave/parry-haste only; classify each swing against boss's last-known facing-before-swing with a staleness guard, and report aggregate melee rear% ours-vs-benchmark per gated boss.
- **Melee Uptime on Boss (in-range %) by spec** (Movement & uptime, _SHARPEN_) — Tell the named melee spec to pre-position / stay stacked behind the boss and stop chasing — e.g. 'Enhance is in-range 78% vs 91%, stick to the tank's hip on movement phases.'
  - _Sharpen:_ Anchor the metric to a STATIONARY/slow boss (Void Reaver, Gruul) where in-range% is melee discipline not boss-kiting — on a mobile boss the gap measures the boss's path, breaking the "stop chasing" action; restrict the per-boss strip to bosses with low boss-displacement and use a soft band (in / edge / out) instead of a hard 8yd step.
- **Per-raider melee uptime vs world best (Optimize hook)** (Movement & uptime, _SHARPEN_) — Coach the specific raider: 'close your melee uptime to the world best — pre-position behind the boss, greedy-cast through small movement.' Concrete, per-person, recoverable without gear.
  - _Sharpen:_ Drop tanks (Optimize has NO tank world-best benchmark — it's DPS/HPS-ranking-keyed, tanks explicitly excluded), scope to melee DPS only, and rebudget honestly: this is the first positional fetch in the pipeline (resourced events for our raider + each world-best's separate report + per-report boss-id resolution + time-synced distance), not a free column. Worth it because the action is concrete and gear-independent ("83% vs 93% in-range, pre-position behind boss, greedy-cast"), but only if the fetch/parse cost is gated behind a flag so the deterministic speed-sensitive default report isn't slowed.
- **Melee-on-boss footprint vs raid footprint (role-separated spacing)** (Raid formation & spacing, _SHARPEN_) — "On [boss] our RANGED footprint is fine but MELEE is scattered (X yd vs benchmark Y) — melee, stack tight behind the boss." (or vice-versa).
  - _Sharpen:_ Keep, but: (1) require a min-delta threshold so the call fires only on a real gap, not noise in a 3-5-person melee group; (2) use the SAME shared frame/scale as the benchmark panel (rendering doc already mandates this) so the two numbers are comparable; (3) always render the number beside the map plot — the picture corroborates a small-N group metric.
- **Tank separation on multi-tank / cleave bosses** (Raid formation & spacing, _SHARPEN_) — "Our main tank faces the boss toward the raid / off-tank is X yd from where the benchmark holds it — reposition tanks to the far side on [boss]."
  - _Sharpen:_ Fold into the SAME curated-mechanic positioning module as the stack/spread idea (no second one-off); gate the tank-to-raid number to fire ONLY on flagged cleave/frontal/breath bosses with the explicit far-side expectation, show distance + side-of-boss map together, and never report facing in degrees.

**Facing-related ideas that were cut (so you know they were weighed):**

- **Time Out of Melee Range — the GCD-cost view** (Movement & uptime) — Already covered better: Execution's measured "Activity by Spec" (dd.activeTime/dur, ours vs benchmark same spec) directly captures idle GCDs and its docstring literally names "out of range" as a cause — no yard-fuzz, no GCD-throughput guess. This monetized companion re-derives a noisier slice of that and the action ("stack melee behind boss") is identical to what the in-range % sibling and Activity-by-Spec already drive. Keep the plain in-range % positional view; drop the DPS-cost monetization.
- **Tank–boss melee leash — was the boss kept in melee uptime range** (Tank & healer geography) — Redundant + confounded: tank-and-spank self-suppresses to ~100% both sides, and the only fights where it moves are scripted-knockback/phase fights where the gap is a mechanic, not a coaching lever. The actual outcomes it proxies are already measured more directly — Early Aggro/Threat Pulls (non-tank held boss aggro) and Activity-by-Spec (raid melee uptime). The "ranged-taunt faster" action rides on a noisy distance metric you can't cleanly attribute to the tank. If salvaged, drop "leash %" and instead surface only knockback-recovery time (seconds for a tank to re-close to the boss after a boss-displacement event), benchmarked — but that needs knockback-event detection and is a much bigger build than the geography strip implies.

---

# Appendix A — every surviving idea (32), ranked

Sorted KEEP-before-SHARPEN, then by leverage.

| # | Idea | Lens | Lev | Feasible | Verdict | Lives in | The action it drives |
|--:|------|------|-----|----------|---------|----------|----------------------|
| 1 | Melee uptime gap — geometry behind a DPS/kill-time gap | Benchmark gap & framing | high | yes | KEEP | Execution tab (alongside per-spec DPS) with a per-boss breakdown in Bosses | Coach melee to chase/pre-position on the named boss; or reassign a melee that chronically lags the ring. |
| 2 | Void-zone overlap heatmap (where the bad accumulates) | Mechanics & avoidable damage | high | yes | KEEP | NEW: a positioning visual inside the per-boss Bosses-tab drill-down (or a 'Positioning' sub-tab on the boss card), reusing the compare_fights.py side-by-side renderer. | "Stop fighting in the [region] of [boss]'s room — that's where we eat all the avoidable damage; benchmark clears out." |
| 3 | Melee-uptime-on-boss column on Execution → Activity by Spec | Cross-tab augmentation | medium | partial | KEEP | Execution tab — a third companion under the existing 'Activity by Spec' (which already decomposes the DPS gap into uptime). This extends uptime into spatial uptime. | If our melee spec's on-boss% trails benchmark, the fix is positioning/uptime discipline (pre-position for boss moves, use gap-closers) — distinct from the gear/rotation throughput lever, so it routes coaching correctly. |
| 4 | The one positioning fix — auto-headlined biggest geometric delta | Benchmark gap & framing | high | partial | SHARPEN | Overview (the single headline positioning callout) | The literal one-liner becomes a raid-rule for next pull (e.g. 'stack within 8yd on Reaver'). |
| 5 | Why we eat more of this ability — positional cause for the avoidable-damage gap | Benchmark gap & framing | high | yes | SHARPEN | Execution tab (next to avoidable-damage gap) or per-boss in Bosses | Confirms whether the fix for a high-intake mechanic is a spacing/spot change vs a cooldown/healing change. |
| 6 | Spread-over-time gap strip — when in the fight our geometry breaks | Benchmark gap & framing | high | yes | SHARPEN | Bosses tab (per-boss, near the existing DPS/HPS timeline with its phase markers) | Drill the named phase window in VOD ('practice the P2 spread'), not the whole fight. |
| 7 | Spread-vs-demand index per shared boss (stack bosses vs spread bosses) | Raid formation & spacing | high | yes | SHARPEN | Bosses (per-boss module, one compact row/badge); the single worst gap also surfaces on Overview top-gaps. | "On [boss] we cluster at [X]yd NN vs the benchmark's [Y]yd — call a wider spread (or tighter stack) for [named mechanic] next pull." |
| 8 | Melee-on-boss footprint vs raid footprint (role-separated spacing) | Raid formation & spacing | high | yes | SHARPEN | Bosses per-boss Positioning sub-section (pairs naturally with the map plot). | "On [boss] our RANGED footprint is fine but MELEE is scattered (X yd vs benchmark Y) — melee, stack tight behind the boss." (or vice-versa). |
| 9 | Positioning Gap Index — rank shared bosses by where geometry hurts us | Benchmark gap & framing | medium | partial | SHARPEN | Overview (one headline row) + reorders the Bosses tab | Drill the top-ranked boss first in next week's VOD review — 'fix spacing on Vashj before anything else.' |
| 10 | Spread-at-AoE column on Bosses → Deaths / Damage Taken | Cross-tab augmentation | medium | yes | SHARPEN | Bosses tab — a column/caption added to the per-boss Damage Taken or Deaths sub-tab (rides the timeline-[enc] + a new resourced fetch on the same shared boss). | If our spread at the AoE instant is far tighter than benchmark on a chain-lightning/explosion mechanic, set a spread assignment for that boss; if too loose on a stack-required mechanic, call a stack. |
| 11 | Tank separation on multi-tank / cleave bosses | Raid formation & spacing | medium | yes | SHARPEN | Bosses per-boss Positioning sub-section. | "Our main tank faces the boss toward the raid / off-tank is X yd from where the benchmark holds it — reposition tanks to the far side on [boss]." |
| 12 | Formation tightness through TIME — does the raid spread on cue? | Raid formation & spacing | medium | partial | SHARPEN | Bosses per-boss Positioning sub-section (sparkline beside the map). | "Benchmark spikes spread 3s before [mechanic cast]; we don't react — pre-spread on the cast timer for [boss]." |
| 13 | Spread Index at the moment damage lands | Mechanics & avoidable damage | medium | partial | SHARPEN | Execution -> raid-wide (a 'Raid Spacing' strip), or per-boss drill-down beside Damage Taken. | "Loosen spacing on [boss] — we're at 4yd nearest-neighbor when AoE lands, benchmark at 9yd; mark spread positions." |
| 14 | Behind-the-boss uptime for melee (cleave/parry-haste avoidance) | Mechanics & avoidable damage | medium | partial | SHARPEN | Execution -> raid-wide (melee positioning), or per-boss Damage Taken drill-down. | "Melee: get behind [boss] — only 55% of your swings are from the rear vs benchmark's 90%; you're eating cleave/parry-haste." |
| 15 | Stack compliance for stack-here mechanics (the inverse of spread) | Mechanics & avoidable damage | medium | partial | SHARPEN | Execution -> raid-wide (same Raid Spacing strip, paired with the spread metric), or per-boss. | "Everyone stack for [soak mechanic] on [boss] — we average 3 bodies in it, benchmark 8; the hit isn't being shared." |
| 16 | Melee Uptime on Boss (in-range %) by spec | Movement & uptime | medium | partial | SHARPEN | Execution raid-wide, directly under 'Activity by Spec' (it's the positional cause of that activity number), with a per-boss strip in the Bosses tab. | Tell the named melee spec to pre-position / stay stacked behind the boss and stop chasing — e.g. 'Enhance is in-range 78% vs 91%, stick to the tank's hip on movement phases.' |
| 17 | Mechanic Run Distance: cost of a spread/soak event | Movement & uptime | medium | partial | SHARPEN | Bosses tab per-boss card, alongside Deaths/Damage-Taken (it's a per-boss mechanic story). Optionally a NEW thin 'Positioning' sub-tab on bosses with a movement mechanic. | If we run far per spread, fix the assignment: pre-assign spread spots / soak groups so people glide to a known spot instead of reacting — e.g. 'pre-mark Arcane Orb spread positions.' |
| 18 | Per-raider melee uptime vs world best (Optimize hook) | Movement & uptime | medium | partial | SHARPEN | Optimize tab, melee/tank specs only, as an extra column/row in the existing optSpecBody layout (reuses the world-best report{code,fightID} already resolved). | Coach the specific raider: 'close your melee uptime to the world best — pre-position behind the boss, greedy-cast through small movement.' Concrete, per-person, recoverable without gear. |
| 19 | Movement vs throughput attribution for the DPS gap | Movement & uptime | medium | partial | SHARPEN | Execution raid-wide, inside the existing 'DPS gap diagnosis' under Output Quality (augment, don't add a tab). | Route the fix correctly: if movement-explained, run positioning drills; if not, it's a gear/rotation/buff problem — stops a raid from drilling movement when the real loss is throughput. |
| 20 | Side-by-side spread map per shared boss (ours vs benchmark, one frame) | Visual & new surface | medium | partial | SHARPEN | Bosses tab — one collapsible map per shared boss (rides alongside the per-boss data already fetched). NOT a new tab; positioning belongs next to the boss it describes. | On the named spread-sensitive boss (e.g. Void Reaver Arcane Orbs, Vashj), tell the raid to spread to the benchmark's footprint next pull (a concrete yard target), or conversely to stack tighter where they over-spread. |
| 21 | Raid-spread heatmap (raw samples, not medians) with a spread-gap headline | Visual & new surface | medium | partial | SHARPEN | Bosses tab, on spread-sensitive bosses only (gated like the existing 'silence over noise' insights). For bosses where spread is irrelevant, omit — a pretty cloud with no mechanic is a CUT. | If our cloud is visibly tighter on a chain-damage boss, the call is 'increase minimum spacing to X yd'; if our cloud is smeared where the benchmark stacks (e.g. a stack-for-healing mechanic), the call is 'stack up'. |
| 22 | Death-spot overlay — does positioning explain the death-count gap? | Benchmark gap & framing | low | partial | SHARPEN | Bosses tab (per-boss, beside the death-cause delta) and/or Wipes tab | Tells the RL whether to assign a movement/spot fix vs a cooldown/timing fix for that specific killing blow. |
| 23 | Death-location mini-map on Wipes ("What Ends Your Attempts") | Cross-tab augmentation | low | yes | SHARPEN | Wipes tab — inline next to 'What Ends Your Attempts' per boss (uses wipe-deaths.json that's already fetched). | If deaths cluster on a spot, assign a callout/repositioning for that mechanic next attempt (e.g. 'move the spawn-point group 10yd left'); if scattered, it's not a positioning fix — chase the global mechanic instead. |
| 24 | Spread-at-cast cross-link on Optimize (per-player, world-best) | Cross-tab augmentation | low | partial | SHARPEN | Optimize tab — a per-raider note on a diverging row, exactly like the existing EXPERIMENTAL hit/expertise cross-link (hit_map → optBossBody). | Tell that raider the divergence is positional (close the gap / stay in range), not a cast-priority change — coach-not-blame, the same pattern the hit-cap note already uses. |
| 25 | Side-by-side formation map (prototyped) promoted into the per-boss module | Raid formation & spacing | low | partial | SHARPEN | Bosses (per-boss module, collapsible 'Positioning' sub-section). NEW sub-section, reusing existing stdlib-SVG renderer. | "Our raid blob is half their footprint on [boss] — spread to the benchmark's shape (picture shown) before the orb/whirlwind phase." |
| 26 | Ranged max-range discipline: are casters actually using their 40yd? | Raid formation & spacing | low | yes | SHARPEN | Execution (it's an output-quality/discipline story, spec-role-level, fits the existing per-spec timeline framing) OR the per-boss Positioning sub-section. | "Our ranged sit at [X]yd vs the benchmark's [Y]yd on [boss] — push casters back to max range to clear the cleave/orb zone." |
| 27 | Where we tanked the boss vs the raid (tank–stack separation) | Tank & healer geography | low | yes | SHARPEN | Bosses tab per-boss card (geography strip) sitting next to Damage Taken; the formation is already visible on the side-by-side map, this adds the comparable number and the verdict. | "Tank stood only 6yd from the raid on Hydross vs their 14yd — pull the boss further out / turn it away so melee aren't in the frontal." |
| 28 | Healer spread / clumping — splash coverage vs single-point-of-failure | Tank & healer geography | low | yes | SHARPEN | Execution tab healer-geography block (next to the Healer Leash idea), raid/role-level; optionally a small healer-only heatmap on the boss map. | "All 4 healers stacked within 5yd on Vashj vs their 14yd spread — split healers so one Toxic Spore / void zone can't drop the whole healing team." |
| 29 | Death-location overlay: where our raid keeps dying vs where theirs does | Visual & new surface | low | yes | SHARPEN | Wipes tab (it already owns death-cause analysis) OR as an overlay toggle on the Bosses-tab map. Wipes tab is the stronger home since death-cause logic lives there. | Name the kill zone: 'X deaths clustered at the room edge during [ability] — reposition the raid / move the boss away from that wall'. A single concrete spatial instruction. |
| 30 | Boss-relative geometry strip: melee-on-boss uptime + ranged max-range, ours vs benchmark | Visual & new surface | low | partial | SHARPEN | Execution tab (it already holds output-quality + active-time). This is 'positional active-time' — a natural sibling to the existing active-time/uptime metrics. | 'Our melee sit at boss-range only 78% vs benchmark 94% — chasing the boss / overreacting to mechanics costs uptime; tighten melee positioning' — a one-line execution fix. |
| 31 | Boss-path trail vs raid centroid: who's chasing the boss around | Visual & new surface | low | yes | SHARPEN | Bosses tab, only on bosses with a meaningful positioning/kiting component (gated). Trash tab could host a kill-path variant but that's weaker. | 'Benchmark kept the boss in one spot; ours moved it 6 times — designate one tank position and stop repositioning' (or, for a kite fight, 'their kite path is one smooth lap, ours backtracks'). |
| 32 | A dedicated 'Positioning' tab — only if 2+ map insights ship, else embed | Visual & new surface | low | yes | SHARPEN | Meta — governs ideas #1-#5. Default: no new tab. NEW: Positioning tab only as a later consolidation. | Ship embedded for v1; revisit a dedicated tab after the maps prove they drive calls in playtesting. Avoids a half-empty tab that fails the worth-its-pixels bar. |


# Appendix B — what each surviving idea shows, and how to sharpen it

## Mechanics & avoidable damage

**Spread Index at the moment damage lands** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ A single raid-level number per boss: median nearest-neighbor distance (in approx yards) among non-tank, non-melee players sampled AT the timestamps of avoidable/AoE damage events — i.e. how packed the squishy raid was exactly when the bad stuff hit. Ours vs benchmark, on shared bosses. Tight spacing during AoE windows is the root cause behind chain-damage; this quantifies it without naming anyone.
- _Lives in:_ Execution -> raid-wide (a 'Raid Spacing' strip), or per-boss drill-down beside Damage Taken.
- _Action:_ "Loosen spacing on [boss] — we're at 4yd nearest-neighbor when AoE lands, benchmark at 9yd; mark spread positions."
- _Ours-vs-benchmark angle:_ A clean ours-vs-benchmark scalar gap (e.g. 'NN 4.1yd vs 9.3yd when AoE lands') that explains a damage-taken or deaths gap the current tabs only state, not explain.
- _Sharpen / verdict note:_ Strong instinct (spacing is the root cause the Damage-Taken/Deaths tabs only state, and positions are a genuinely new modality the soul rewards), but ship the honest form: count how many DISTINCT raiders each AoE-ability instance hit (chain-damage breadth per cast) instead of reconstructing absent players' positions — it is fully resolved, needs no carry-forward, no absolute yards, and no victim bias; report it as a ratio vs benchmark ("our AoE ticks hit 2.3x more raiders"), not a yard figure, and reuse the existing avoidable-ability set rather than inventing an AoE allowlist.

**Behind-the-boss uptime for melee (cleave/parry-haste avoidance)** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ Share of melee-damage-dealing time that our melee spent in the boss's rear arc vs its frontal arc, ours vs benchmark, per applicable boss. Computed from the boss's facing at each melee swing plus the bearing from boss to the swinging melee (both in the same resourced event stream). Standing behind avoids frontal cleave and parry-haste; a low 'behind %' vs benchmark is a concrete melee-positioning gap.
- _Lives in:_ Execution -> raid-wide (melee positioning), or per-boss Damage Taken drill-down.
- _Action:_ "Melee: get behind [boss] — only 55% of your swings are from the rear vs benchmark's 90%; you're eating cleave/parry-haste."
- _Ours-vs-benchmark angle:_ Aggregate melee-vs-benchmark 'behind %' gap — explains a melee-deaths or cleave-damage gap mechanically.
- _Sharpen / verdict note:_ Prove a per-zone facing→x/y-frame calibration on a stationary known-orientation boss BEFORE building; gate to bosses with real frontal cleave/parry-haste only; classify each swing against boss's last-known facing-before-swing with a staleness guard, and report aggregate melee rear% ours-vs-benchmark per gated boss.

**Stack compliance for stack-here mechanics (the inverse of spread)** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ For mechanics that REQUIRE stacking to soak/share (the opposite of spread), measure raid tightness at the soak moment: how many raiders were within the soak radius when the hit landed, ours vs benchmark. A loose raid that should be stacked takes a per-person spike (or wipes the soak). Pairs naturally with the spread idea — same machinery, opposite verdict — so the report covers both 'spread' and 'stack' failures rather than only one.
- _Lives in:_ Execution -> raid-wide (same Raid Spacing strip, paired with the spread metric), or per-boss.
- _Action:_ "Everyone stack for [soak mechanic] on [boss] — we average 3 bodies in it, benchmark 8; the hit isn't being shared."
- _Ours-vs-benchmark angle:_ Soak-participation gap: 'avg 3 in the soak vs benchmark 8' on a share-the-damage mechanic — a stack-discipline gap.
- _Sharpen / verdict note:_ Don't ship standalone: fold into ONE "Raid Spacing" feature with the spread idea, driven by a single per-mechanic table tagged stack|spread; render ONLY for vetted-list mechanics (silent otherwise) so it can never mislabel a spread fight as a stack fight.

**Void-zone overlap heatmap (where the bad accumulates)** — _KEEP · high leverage · feasible: yes_

- _Shows:_ A side-by-side raid-level heatmap of WHERE on the boss room avoidable-damage hits landed (raw DamageTaken sample positions for the avoidable mechanics), ours vs benchmark, on one shared equal-aspect frame. A hot blob in our panel that's cold in theirs shows the exact region of the room where we keep eating it (e.g. a corner the void zones spawn in that we don't clear). Raw-sample heatmap is the recommended way to show spread honestly (a median would collapse it).
- _Lives in:_ NEW: a positioning visual inside the per-boss Bosses-tab drill-down (or a 'Positioning' sub-tab on the boss card), reusing the compare_fights.py side-by-side renderer.
- _Action:_ "Stop fighting in the [region] of [boss]'s room — that's where we eat all the avoidable damage; benchmark clears out."
- _Ours-vs-benchmark angle:_ Spatial gap: our hotspot vs their absence-of-hotspot in the same room region — visually obvious 'we keep standing here.'
- _Sharpen / verdict note:_ Drive the heatmap's ability filter straight from that boss's existing top avoidable_damage_gap rows (so WHERE and WHAT agree, no hand list), gate rendering to bosses with a real positional gap, share one frame+scale+color-scale across both panels, and describe hotspots relative to the boss marker (never compass) — it turns the existing "what/how-much" gap into the missing "where," driving a one-line reposition call.

## Movement & uptime

**Melee Uptime on Boss (in-range %) by spec** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ Per melee/tank spec, the share of the fight that spec stood inside the ~8yd melee ring of the named boss, ours vs benchmark same-spec, mirrored bars. Computed by sampling each melee's distance-to-boss at every resourced event they appear in (their Casts/swings + DamageTaken landing on them), classifying each sample in/out of an ~8yd ring (relative geometry, no absolute-yard claim), and weighting by the event timeline. The boss anchor is its dense DamageDone-targeted positions interpolated to each sample time. Direct decomposition of the existing 'Activity by Spec' gap: out-of-range = the exact GCDs a melee burned walking instead of swinging.
- _Lives in:_ Execution raid-wide, directly under 'Activity by Spec' (it's the positional cause of that activity number), with a per-boss strip in the Bosses tab.
- _Action:_ Tell the named melee spec to pre-position / stay stacked behind the boss and stop chasing — e.g. 'Enhance is in-range 78% vs 91%, stick to the tank's hip on movement phases.'
- _Ours-vs-benchmark angle:_ Melee that is in-range 78% vs the benchmark's 91% is a clean better/worse throughput gap with a no-gear fix; it names which melee spec is leaking uptime to chasing the boss.
- _Sharpen / verdict note:_ Anchor the metric to a STATIONARY/slow boss (Void Reaver, Gruul) where in-range% is melee discipline not boss-kiting — on a mobile boss the gap measures the boss's path, breaking the "stop chasing" action; restrict the per-boss strip to bosses with low boss-displacement and use a soft band (in / edge / out) instead of a hard 8yd step.

**Mechanic Run Distance: cost of a spread/soak event** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ For a recurring named mechanic that forces movement (identified by a debuff-apply or a marker cast in the events stream — e.g. an Arcane Orb / Flame Wreath / spread cast), the median per-player distance travelled in the ~5s window after the cast fires, raid-aggregate, ours vs benchmark. Uses each event's timestamp to window the position samples around the mechanic. Answers 'when the spread hits, do we scramble 20yd or glide 6yd.'
- _Lives in:_ Bosses tab per-boss card, alongside Deaths/Damage-Taken (it's a per-boss mechanic story). Optionally a NEW thin 'Positioning' sub-tab on bosses with a movement mechanic.
- _Action:_ If we run far per spread, fix the assignment: pre-assign spread spots / soak groups so people glide to a known spot instead of reacting — e.g. 'pre-mark Arcane Orb spread positions.'
- _Ours-vs-benchmark angle:_ Same mechanic on both raids = a controlled, like-for-like positional comparison; a benchmark that runs half as far per spread either pre-positioned or has better assignments — a concrete tactical gap, not a vague 'they move better.'
- _Sharpen / verdict note:_ Keep the same-mechanic controlled comparison and the "pre-mark spread spots" action, but swap the fragile summed-path-distance for a robust SNAPSHOT metric the data validates: post-cast raid spread/displacement — median net displacement (start-of-window vs settle position) or raid bounding-box growth in the window — ours vs benchmark, ship only on 1-2 bosses with an unambiguous repeated movement cast.

**Per-raider melee uptime vs world best (Optimize hook)** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ In the Optimize tab's per-spec view, add a melee-uptime column for each of OUR melee raiders: their in-range % on the benchmarked boss vs the same-faction world-best player's in-range % on that same boss (the world best is already fetched there). Sits beside the cast-mix mirror bars as a second execution dimension — 'your rotation matches, but you're in-range 80% vs the world best's 93%.'
- _Lives in:_ Optimize tab, melee/tank specs only, as an extra column/row in the existing optSpecBody layout (reuses the world-best report{code,fightID} already resolved).
- _Action:_ Coach the specific raider: 'close your melee uptime to the world best — pre-position behind the boss, greedy-cast through small movement.' Concrete, per-person, recoverable without gear.
- _Ours-vs-benchmark angle:_ The single sanctioned per-player view, benchmarked against the WORLD best (not the comparison guild) — exactly the Optimize exception. Movement uptime is genuinely rotation/execution-like (it's recoverable GCDs), so it qualifies under the per-player carve-out the same way cast-mix does.
- _Sharpen / verdict note:_ Drop tanks (Optimize has NO tank world-best benchmark — it's DPS/HPS-ranking-keyed, tanks explicitly excluded), scope to melee DPS only, and rebudget honestly: this is the first positional fetch in the pipeline (resourced events for our raider + each world-best's separate report + per-report boss-id resolution + time-synced distance), not a free column. Worth it because the action is concrete and gear-independent ("83% vs 93% in-range, pre-position behind boss, greedy-cast"), but only if the fetch/parse cost is gated behind a flag so the deterministic speed-sensitive default report isn't slowed.

**Movement vs throughput attribution for the DPS gap** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ Upgrade the existing DPS-gap diagnosis (which today only ESTIMATES an activity-vs-throughput split from activeTime) so the 'activity' half is corroborated by real movement: show, raid-level, what fraction of our activity deficit coincides with measured excess movement (path length and out-of-range time) vs unexplained idle. Turns a heuristic split into an evidenced one: 'of the X DPS we trail, ~Y is movement we can see in the positions, the rest is rotation/gear.'
- _Lives in:_ Execution raid-wide, inside the existing 'DPS gap diagnosis' under Output Quality (augment, don't add a tab).
- _Action:_ Route the fix correctly: if movement-explained, run positioning drills; if not, it's a gear/rotation/buff problem — stops a raid from drilling movement when the real loss is throughput.
- _Ours-vs-benchmark angle:_ Sharpens an existing comparison feature rather than adding a standalone number — the positions either confirm 'this gap is movement, fixable by positioning' or 'movement matches benchmark, so the gap is gear/rotation,' which changes the leader's prescription entirely.
- _Sharpen / verdict note:_ Keep the routing decision, kill the percentage: have positions output a directional flag only — "movement is consistent with / does not explain the activity gap" (path length and out-of-range both above/at benchmark) — and let dps_diagnosis swap "drill movement vs chase gear" on that flag, never claiming a quantified Y/s split.

## Raid formation & spacing

**Spread-vs-demand index per shared boss (stack bosses vs spread bosses)** — _SHARPEN · high leverage · feasible: yes_

- _Shows:_ For each shared boss, classify the mechanic demand (STACK e.g. Leotheras whirlwind / heal-stack, or SPREAD e.g. Void Reaver Arcane Orb / Vashj tainted-core spacing) and compute the raid's actual median nearest-neighbor distance from time-windowed samples (NOT per-player medians — sample many timestamps so the metric is honest), ours vs benchmark. One number per boss with a direction arrow: on a SPREAD boss, higher NN = better; on a STACK boss, lower = better. The gap is the headline.
- _Lives in:_ Bosses (per-boss module, one compact row/badge); the single worst gap also surfaces on Overview top-gaps.
- _Action:_ "On [boss] we cluster at [X]yd NN vs the benchmark's [Y]yd — call a wider spread (or tighter stack) for [named mechanic] next pull."
- _Ours-vs-benchmark angle:_ Pure gap metric: our spread number vs benchmark's on the identical boss/mechanic. A ratio >1 or <1 against the demand direction is the actionable deficit.
- _Sharpen / verdict note:_ Score NN over the MECHANIC-RELEVANT time window (phase/cast-gated), not the whole kill — a single whole-fight NN washes out phase-specific demand (Vashj P1-spread vs P2-stack; Leotheras whirlwind-stack vs Inner-Demons-spread) and can even point the wrong way; and carry-forward last-known position per actor into each bin so sparse idle ranged aren't dropped.

**Side-by-side formation map (prototyped) promoted into the per-boss module** — _SHARPEN · low leverage · feasible: partial_

- _Shows:_ The existing compare_fights.py top-down dual-panel plot (ours vs benchmark, one shared frame & scale, role-colored dots, boss marker, 8yd melee ring) embedded per shared boss. A raid leader literally sees our blob vs their blob: are we stacked when they're fanned, is our melee off the boss, are ranged at max range. Most decisions are obvious at a glance from the picture, not a number.
- _Lives in:_ Bosses (per-boss module, collapsible 'Positioning' sub-section). NEW sub-section, reusing existing stdlib-SVG renderer.
- _Action:_ "Our raid blob is half their footprint on [boss] — spread to the benchmark's shape (picture shown) before the orb/whirlwind phase."
- _Ours-vs-benchmark angle:_ Two panels, identical frame and zoom — the comparison IS the feature; the eye does the gap detection.
- _Sharpen / verdict note:_ Drop the median renderer; render a mid-phase raw-sample heatmap (the only view that shows spread) and gate it to the few spread-sensitive bosses (Void Reaver-type) with a quantified gap caption (our footprint X yd vs benchmark Y yd) — a static map on temporal-mechanic bosses is vivid but inert.

**Ranged max-range discipline: are casters actually using their 40yd?** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ For ranged DPS+healers only, the distribution of their distance-to-boss across the fight (time-windowed samples). The metric: median (or 25th-pct) ranged-to-boss distance, ours vs benchmark. Benchmark ranged typically anchor near max cast range to maximize spread room and dodge frontal/cleave/orb mechanics; if our ranged hug at ~15yd they crowd melee, eat avoidable cleave, and leave no spread margin. Show as a single ranged-standoff number per boss plus a small histogram.
- _Lives in:_ Execution (it's an output-quality/discipline story, spec-role-level, fits the existing per-spec timeline framing) OR the per-boss Positioning sub-section.
- _Action:_ "Our ranged sit at [X]yd vs the benchmark's [Y]yd on [boss] — push casters back to max range to clear the cleave/orb zone."
- _Ours-vs-benchmark angle:_ Ranged standoff distance ours vs theirs — a clean relative gap that implies push-back-or-not.
- _Sharpen / verdict note:_ Standoff distance is a proxy: median ranged-to-boss is driven by fight geometry, not discipline, and "push back to clear cleave" is harm the report already measures directly (DamageTaken-by-mechanic / death-cause table). Keep ONLY if conditioned on a confirmed harm signal — e.g. show the standoff gap as the EXPLANATION beside a boss where our ranged also eat more avoidable cleave/orb damage than the benchmark; a bare distance gap with no harm attached is interesting-but-inert and should be cut.

**Melee-on-boss footprint vs raid footprint (role-separated spacing)** — _SHARPEN · high leverage · feasible: yes_

- _Shows:_ Two spread numbers per boss instead of one blended one: (a) MELEE cluster tightness around the boss (should be tight — stacked behind), and (b) RANGED/HEALER footprint (should be wide on spread fights). Benchmarks show a clean bimodal formation: melee dot-cluster on the boss, ranged fanned out. If OUR melee is scattered (chasing adds, bad uptime positioning) or our ranged is bunched, the role-separated metric exposes which ROLE owns the formation problem — actionable per assignment group, still raid/spec-level not per-player.
- _Lives in:_ Bosses per-boss Positioning sub-section (pairs naturally with the map plot).
- _Action:_ "On [boss] our RANGED footprint is fine but MELEE is scattered (X yd vs benchmark Y) — melee, stack tight behind the boss." (or vice-versa).
- _Ours-vs-benchmark angle:_ Per-role-group spread ours vs theirs — pinpoints WHICH role's spacing is the gap, driving a targeted assignment call.
- _Sharpen / verdict note:_ Keep, but: (1) require a min-delta threshold so the call fires only on a real gap, not noise in a 3-5-person melee group; (2) use the SAME shared frame/scale as the benchmark panel (rendering doc already mandates this) so the two numbers are comparable; (3) always render the number beside the map plot — the picture corroborates a small-N group metric.

**Tank separation on multi-tank / cleave bosses** — _SHARPEN · medium leverage · feasible: yes_

- _Shows:_ On bosses where tanks must be apart (e.g. cleave/frontal where off-tank stands clear, or boss faced away from raid), measure tank-to-tank distance and tank-to-raid distance, ours vs benchmark. A correct formation has tanks on the FAR side from the raid (the documented Void Reaver validation signal). If our tanks stand near the raid, the boss's frontal/cleave/breath hits the stack. One distance number + the map showing tank dots' side.
- _Lives in:_ Bosses per-boss Positioning sub-section.
- _Action:_ "Our main tank faces the boss toward the raid / off-tank is X yd from where the benchmark holds it — reposition tanks to the far side on [boss]."
- _Ours-vs-benchmark angle:_ Tank-to-raid distance and tank-side ours vs benchmark on cleave bosses — drives a concrete tank-placement call.
- _Sharpen / verdict note:_ Fold into the SAME curated-mechanic positioning module as the stack/spread idea (no second one-off); gate the tank-to-raid number to fire ONLY on flagged cleave/frontal/breath bosses with the explicit far-side expectation, show distance + side-of-boss map together, and never report facing in degrees.

**Formation tightness through TIME — does the raid spread on cue?** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ A small sparkline per shared boss: raid nearest-neighbor (or footprint) plotted over fight time, ours vs benchmark overlaid. Reveals not just average spread but TIMING — does the benchmark spread sharply right before the orb/AoE/phase cast and re-stack after, while we stay flat (never spread) or spread late? The shape of the curve at the mechanic's timestamp is the insight: reaction discipline, not just average position.
- _Lives in:_ Bosses per-boss Positioning sub-section (sparkline beside the map).
- _Action:_ "Benchmark spikes spread 3s before [mechanic cast]; we don't react — pre-spread on the cast timer for [boss]."
- _Ours-vs-benchmark angle:_ Spread-over-time curve ours vs theirs, anchored at the mechanic cast — exposes reaction-timing gaps a single average hides.
- _Sharpen / verdict note:_ Drop the noisy continuous sparkline; scope to ONE high-cast-volume spread mechanic and report two anchored aggregates — raid spread in [cast-3s,cast] vs [cast,cast+3s], ours vs benchmark — so the action is "benchmark peaks at cast-3s, we peak at cast+2s: pre-spread on the timer."

## Benchmark gap & framing

**Positioning Gap Index — rank shared bosses by where geometry hurts us** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ One headline number per shared boss: a 0-100 'positioning gap' built from 2-3 relative-geometry deltas vs the benchmark (raid footprint / radius-of-gyration delta, median melee-on-boss distance delta, and ranged max-spread delta), each normalized and signed so positive = we are worse. Sorts the Bosses tab and feeds an Overview line: 'Biggest positioning gap: Vashj (+38) — our raid is 9yd tighter where the benchmark spreads.' Mirrors the existing death-cause 'biggest improvable delta first' sort, but for geometry instead of killing blows.
- _Lives in:_ Overview (one headline row) + reorders the Bosses tab
- _Action:_ Drill the top-ranked boss first in next week's VOD review — 'fix spacing on Vashj before anything else.'
- _Ours-vs-benchmark angle:_ A single signed ours-vs-benchmark score per boss that says 'this is where our geometry is worst,' directly parallel to how the report already ranks death causes by improvable delta.
- _Sharpen / verdict note:_ Kill the composite index and the false 'mirrors the death-cause sort' claim — I verified the death-cause/Biggest-Gaps sort ranks by a single physical quantity (avoidable killing blows / player-minutes) with hand-tuned per-dimension severity, NOT a normalized blend; a +38 composite tells a leader nothing to fix and its three parts can cancel. Also drop the 'we are WORSE' sign: geometric divergence != deficit (tighter is correct on stack/cleave fights, wrong on spread fights — and footprint is driven by comp/mechanics, not just execution), so signing it as worse overclaims. Reframe as a triage: rank shared bosses by raw geometric DIVERGENCE from the benchmark (unsigned), surface the 1-2 component deltas in relative terms (e.g. 'our footprint 0.6x theirs', no yards), and let the leader judge direction in the VOD. That keeps the genuinely useful 'which boss to review first' action without the unjustified sign or the uninterpretable index.

**The one positioning fix — auto-headlined biggest geometric delta** — _SHARPEN · high leverage · feasible: partial_

- _Shows:_ Picks the single largest, most-actionable positioning delta across all shared bosses and states it in one sentence on the Overview, with the side-by-side mini-plot inline: e.g. 'Stack tighter on Void Reaver: our raid spreads to a 22yd footprint vs the benchmark's 11yd — Arcane Orbs chain through the gap.' Chooses among a small set of pre-classified boss archetypes (stack-boss vs spread-boss) so the verb ('stack' vs 'spread') is correct per fight.
- _Lives in:_ Overview (the single headline positioning callout)
- _Action:_ The literal one-liner becomes a raid-rule for next pull (e.g. 'stack within 8yd on Reaver').
- _Ours-vs-benchmark angle:_ Reduces the whole positioning lens to one ours-vs-benchmark gap + the exact verb to fix it — the report's core thesis in a sentence.
- _Sharpen / verdict note:_ Right destination (one headline gap + correct verb = the thesis), wrong engine: (1) compute spread from time-windowed/heatmap samples, NOT the degenerate median metrics; (2) drop auto-rank-by-magnitude — largest geometric delta != most actionable; restrict to a tiny curated set of bosses where geometry is known to punish, with hard-coded verb; (3) gate it — fire only when ours is past threshold by a real margin, else suppress (a wrong/inert headline is worse than none).

**Death-spot overlay — does positioning explain the death-count gap?** — _SHARPEN · low leverage · feasible: partial_

- _Shows:_ For each (killing-blow cause × boss) row where we out-die the benchmark, plot OUR death locations (sampled at each death's timestamp from the nearest resourced event) against the benchmark's, on the shared frame. Reveals whether our extra deaths cluster in a specific zone (e.g. all 'Toxic Spore' deaths in one corner = a spawn nobody moved from) vs scattered (a timing/reaction problem, not a position problem). Annotates the existing death-cause delta row with 'positional: deaths cluster at X' or 'non-positional: scattered.'
- _Lives in:_ Bosses tab (per-boss, beside the death-cause delta) and/or Wipes tab
- _Action:_ Tells the RL whether to assign a movement/spot fix vs a cooldown/timing fix for that specific killing blow.
- _Ours-vs-benchmark angle:_ Directly converts an existing ours-vs-benchmark death-count gap into a YES/NO 'is it a positioning problem' verdict — the join the report can't currently make.
- _Sharpen / verdict note:_ Drop the benchmark overlay (their side is ~empty) and the per-row gating; instead, for OUR deaths only, run the clustered/scattered verdict on the rare cause that actually has N>=4 on a SINGLE boss (e.g. Whirlwind/Melee on Vashj), annotating the death-cause row only when the verdict is real — silence otherwise. This keeps the one genuinely actionable case (movement vs timing fix) and honestly admits the data can't support a vs-benchmark spatial comparison.

**Why we eat more of this ability — positional cause for the avoidable-damage gap** — _SHARPEN · high leverage · feasible: yes_

- _Shows:_ For the top rows of the existing 'avoidable damage by mechanic' gap (where our per-second intake of an ability exceeds the benchmark's), overlay the positions of OUR actors at the moment they took that ability vs theirs. Distinguishes 'we stand in the AoE' (hits cluster on a hazard zone) from 'we're hit while spread correctly but it's unavoidable' (hits scattered/at-range). Turns a bare intake-rate delta into 'we eat 2.3x more Spore Cloud because half the raid clips the same zone.'
- _Lives in:_ Execution tab (next to avoidable-damage gap) or per-boss in Bosses
- _Action:_ Confirms whether the fix for a high-intake mechanic is a spacing/spot change vs a cooldown/healing change.
- _Ours-vs-benchmark angle:_ Adds the missing 'why' to an existing ours-vs-benchmark intake gap, splitting it into positional vs non-positional so the fix is unambiguous.
- _Sharpen / verdict note:_ Gate to the SINGLE top intake-gap ability on the ONE worst-gap boss (not "top rows") to cap the heavy events fetch at 1 boss × 2 sides; render one ours-vs-theirs target-hit scatter and label the verdict explicitly: clustered = spacing fix, scattered/at-range = CD/healing fix.

**Melee uptime gap — geometry behind a DPS/kill-time gap** — _KEEP · high leverage · feasible: yes_

- _Shows:_ Per shared boss, the % of melee-attribution samples inside ~8yd of the boss, ours vs benchmark (relative ring, no absolute-yard claim needed since both use the same scale). A lower melee-uptime is a concrete geometric reason our melee DPS — and thus kill time — trails. Pairs the number with the existing kill-time delta: 'Benchmark melee sit on the boss 91% vs our 74% — part of the 37s slower kill.'
- _Lives in:_ Execution tab (alongside per-spec DPS) with a per-boss breakdown in Bosses
- _Action:_ Coach melee to chase/pre-position on the named boss; or reassign a melee that chronically lags the ring.
- _Ours-vs-benchmark angle:_ Ties a positioning metric (melee ring uptime) directly to an already-shown kill-time/DPS gap, giving the geometric reason behind a number the report already headlines.
- _Sharpen / verdict note:_ Anchor the in-range % to fight time / time-windowed samples (not raw event count) so a melee that runs out and stops swinging isn't credited as "in range"; present it explicitly as the geometric "why" beneath the existing Activity-by-Spec / DPS-gap-diagnosis activity component, and keep the display melee-cohort aggregate (the "reassign a melee" action is fine as derived coaching, not a new per-player module). Resolves the now-stale BACKLOG "where does the melee stand" entry that the includeResources flag unblocked.

**Spread-over-time gap strip — when in the fight our geometry breaks** — _SHARPEN · high leverage · feasible: yes_

- _Shows:_ A small multiples / sparkline per shared boss of raid footprint (radius of gyration) over fight time, ours vs benchmark, with phase markers overlaid (phases already in the timeline). Surfaces WHEN the gap opens: 'both spread fine until P2, then our footprint collapses to 8yd while theirs holds 18yd' — pinpointing the exact mechanic window to drill, not just that a gap exists.
- _Lives in:_ Bosses tab (per-boss, near the existing DPS/HPS timeline with its phase markers)
- _Action:_ Drill the named phase window in VOD ('practice the P2 spread'), not the whole fight.
- _Ours-vs-benchmark angle:_ Turns a static spread delta into a WHEN-it-happens ours-vs-benchmark timeline, narrowing the fix to a specific phase the benchmark survives and we don't.
- _Sharpen / verdict note:_ Gate to scripted multi-phase bosses with a real spread mechanic (else the strip is noise on flat fights); bucket by phase-fraction with a per-bucket min-actor floor + last-known carry-forward, and label the named phase where the gap opens.

## Tank & healer geography

**Where we tanked the boss vs the raid (tank–stack separation)** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ The distance between the tank cluster (tanks' median positions) and the raid stack (melee+healer cluster centroid), per shared boss, ours vs benchmark. This is the canonical 'boss faced away, melee behind, ranged spread' check expressed as one role-geometry number. Too SHORT a tank↔raid separation on a cleave/frontal/breath boss (e.g. boss not turned away) means the raid is eating frontal damage; the benchmark's larger separation is the fix. It's the role-level version of the validated 'tanks on the far side, raid opposite' formation, turned into a comparable scalar + drawn on the map.
- _Lives in:_ Bosses tab per-boss card (geography strip) sitting next to Damage Taken; the formation is already visible on the side-by-side map, this adds the comparable number and the verdict.
- _Action:_ "Tank stood only 6yd from the raid on Hydross vs their 14yd — pull the boss further out / turn it away so melee aren't in the frontal."
- _Ours-vs-benchmark angle:_ Role-centroid separation is a single scalar with a per-boss benchmark; the gap drives a concrete 'tank further / turn the boss' instruction.
- _Sharpen / verdict note:_ Don't ship a freestanding separation scalar — its good/bad direction is boss-specific and uncurated (big=good on a frontal boss, bad on a stack boss), and it only PROXIES frontal damage that the existing Avoidable Damage by Mechanic already measures directly (exact ability, exact per-sec gap vs benchmark). Instead make it a derived annotation ON the already-planned side-by-side map, surfaced ONLY for bosses where Avoidable Damage by Mechanic shows a frontal/cleave/breath gap: "tanks 6yd from raid vs their 14yd — explains the +X frontal dmg/s." Geometry then earns pixels as the WHY/fix for a damage gap the report already flags, not as an inert standalone number.

**Healer spread / clumping — splash coverage vs single-point-of-failure** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ Healer-cluster spread (radius of gyration over the healers' positions, sampled at MANY timestamps not a single median, to avoid the median-collapse pitfall), per shared boss, ours vs benchmark. Too TIGHT a healer clump = all healers eat the same AoE / one bad GTAOE drops healing throughput and is a wipe risk; too LOOSE can mean poor group coverage. The benchmark sets the reference. This is the healer analogue of the already-shipped raid spread metric, scoped to the healer role where clumping is uniquely dangerous (lose 3 healers to one void zone = wipe).
- _Lives in:_ Execution tab healer-geography block (next to the Healer Leash idea), raid/role-level; optionally a small healer-only heatmap on the boss map.
- _Action:_ "All 4 healers stacked within 5yd on Vashj vs their 14yd spread — split healers so one Toxic Spore / void zone can't drop the whole healing team."
- _Ours-vs-benchmark angle:_ Single spread scalar with a benchmark; gap drives a 'spread your healers' or 'group up for chain-heal coverage' decision depending on direction.
- _Sharpen / verdict note:_ Don't ship as a standalone descriptive scalar — the fix flips direction by boss (spread vs stack-for-Chain-Heal), so a bare gap is inert. Fold healer spread into a general raid-spread positioning feature and only fire a verdict on a hardcoded allowlist of known void-zone/splash fights (Vashj Toxic Spore, Kael, Leotheras) where a tight healer clump is an unambiguous wipe risk; elsewhere stay silent, not descriptive. Note: the pitch's premise is false — there is NO shipped positional spread metric (parse_spread is statistical decomposition of Avg Raid Parse), so this can't free-ride on existing infra; it must justify the whole positioning fetch, which a healer-only sub-metric alone doesn't.

## Visual & new surface

**Side-by-side spread map per shared boss (ours vs benchmark, one frame)** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ Two faithful equal-aspect top-down panels on ONE shared frame+scale (union of both fights' boundingBoxes), each dot a player's median position over the kill, colored by role, boss as a neutral diamond with an ~8yd melee ring. Beneath: the spread stat row already proven in compare_fights.py (median nearest-neighbor yd, raid footprint / radius of gyration) for both sides. The eyeball read is 'their ranged fan to ~40yd in an arc; ours bunches at ~12yd', made quantitative by the footprint delta.
- _Lives in:_ Bosses tab — one collapsible map per shared boss (rides alongside the per-boss data already fetched). NOT a new tab; positioning belongs next to the boss it describes.
- _Action:_ On the named spread-sensitive boss (e.g. Void Reaver Arcane Orbs, Vashj), tell the raid to spread to the benchmark's footprint next pull (a concrete yard target), or conversely to stack tighter where they over-spread.
- _Ours-vs-benchmark angle:_ Direct ours-vs-benchmark on identical geometry: a footprint-yard gap on a chain/bounce mechanic IS the gap-and-fix the report's thesis demands.
- _Sharpen / verdict note:_ Keep the faithful side-by-side panels, but compute the footprint/NN spread NUMBER from raw time-sampled positions (all samples, or a heatmap of raw points), NOT per-player medians — else the yard target it recommends is noise; dots can stay median ('where they set up'), stat must be sampled.

**Raid-spread heatmap (raw samples, not medians) with a spread-gap headline** — _SHARPEN · medium leverage · feasible: partial_

- _Shows:_ A density heatmap of ALL raw resourced (x,y) samples for the raid over the kill — a true cloud, not one dot per player — so genuine spread/clumping is visible (the median-collapse pitfall is exactly why a heatmap is the honest spread visual). Rendered as binned alpha rectangles in stdlib SVG. Paired ours-vs-benchmark, both on the shared frame. One headline number: 90th-percentile pairwise distance (or footprint) ours vs theirs.
- _Lives in:_ Bosses tab, on spread-sensitive bosses only (gated like the existing 'silence over noise' insights). For bosses where spread is irrelevant, omit — a pretty cloud with no mechanic is a CUT.
- _Action:_ If our cloud is visibly tighter on a chain-damage boss, the call is 'increase minimum spacing to X yd'; if our cloud is smeared where the benchmark stacks (e.g. a stack-for-healing mechanic), the call is 'stack up'.
- _Ours-vs-benchmark angle:_ The heatmap shape difference is the gap; the percentile-distance number quantifies it and drives the spacing decision.
- _Sharpen / verdict note:_ Lead with a raid-aggregate spread NUMBER (footprint area or time-windowed median nearest-neighbor, stated RELATIVE — "our footprint is 60% of the benchmark's"), NOT absolute yards and NOT a pairwise-distance metric the per-event sampling can't cleanly support; keep the heatmap as supporting evidence, gate strictly to spread-sensitive bosses (reuse the >=3 "silence over noise" precedent), and caption "weighted toward active combat."

**Death-location overlay: where our raid keeps dying vs where theirs does** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ On the same faithful frame, plot a marker at each death's position (the killing-blow damage event carries x/y when fetched with includeResources), colored/sized by killing-blow cause, ours vs benchmark. Clusters reveal a spatial failure: 'our deaths pile up in the SW corner = people not leaving the bad / standing in a frontal'. This is the spatial twin of the existing tier-wide death-cause table (which has the what+when but not the where).
- _Lives in:_ Wipes tab (it already owns death-cause analysis) OR as an overlay toggle on the Bosses-tab map. Wipes tab is the stronger home since death-cause logic lives there.
- _Action:_ Name the kill zone: 'X deaths clustered at the room edge during [ability] — reposition the raid / move the boss away from that wall'. A single concrete spatial instruction.
- _Ours-vs-benchmark angle:_ Benchmark deaths are few and scattered (or absent); ours cluster spatially — the cluster IS the gap and points at the exact spot to fix.
- _Sharpen / verdict note:_ Drop the two-sided "vs theirs" framing — it is structurally hollow (benchmark clean kills = ~0 deaths; data shows benchmark 0 wipe-deaths vs our 43, and the idea itself concedes "few or absent"). Reframe as a single-side OUR-deaths spatial cluster annotation that ADDS the WHERE to the existing raid-level death-cause table's WHAT+WHEN — gated to bosses with >=5 deaths, output as one auto-named instruction ("N deaths clustered at the room edge during [ability] — reposition") rather than a standalone plotted map. Without that, it is the existing death-cause count plus pixels.

**Boss-relative geometry strip: melee-on-boss uptime + ranged max-range, ours vs benchmark** — _SHARPEN · low leverage · feasible: partial_

- _Shows:_ Not a map but a derived-from-position bar/strip per shared boss: % of samples melee dps are inside ~8yd of the boss (uptime proxy), and median ranged distance-to-boss. Two small bars per metric (ours vs theirs). This converts the geometry into the spec/raid-level numbers the report already speaks in, sidestepping the map's readability and orientation caveats entirely.
- _Lives in:_ Execution tab (it already holds output-quality + active-time). This is 'positional active-time' — a natural sibling to the existing active-time/uptime metrics.
- _Action:_ 'Our melee sit at boss-range only 78% vs benchmark 94% — chasing the boss / overreacting to mechanics costs uptime; tighten melee positioning' — a one-line execution fix.
- _Ours-vs-benchmark angle:_ A melee-in-range % gap or a ranged-too-close gap is a clean, benchmarked, actionable execution delta — no map needed to act on it.
- _Sharpen / verdict note:_ Melee-in-range % is largely REDUNDANT with the existing free Activity-by-Spec metric (idle GCDs from chasing/overreacting already show as low melee activeTime, named by spec, benchmarked, no fetch) and carries the scale+sampling-bias holes; cut that half. Keep only the NOVEL half — ranged median distance-to-boss / "too close" — which activeTime cannot see (a ranged hugging the boss shows full activity yet eats avoidable cleave/positional damage); gate it on bosses where being-too-close is an actual mechanic, or CUT.

**Boss-path trail vs raid centroid: who's chasing the boss around** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ A path/trail plot of the BOSS's reconstructed track (dense from DamageDone targeting it) with the raid CENTROID track overlaid, ours vs benchmark, on the shared frame. Reveals tank kiting/repositioning discipline: a tidy benchmark boss path (boss parked, raid stable) vs our scribbled path (boss dragged around, raid chasing) on a boss that's supposed to stay put.
- _Lives in:_ Bosses tab, only on bosses with a meaningful positioning/kiting component (gated). Trash tab could host a kill-path variant but that's weaker.
- _Action:_ 'Benchmark kept the boss in one spot; ours moved it 6 times — designate one tank position and stop repositioning' (or, for a kite fight, 'their kite path is one smooth lap, ours backtracks').
- _Ours-vs-benchmark angle:_ Two paths side by side make tank/raid movement discipline a visible, benchmarked gap.
- _Sharpen / verdict note:_ Kill the trail (it's the pretty-but-inert part) and the centroid overlay; ship ONE benchmarked scalar per gated boss — boss total displacement + count of distinct reposition clusters ("they moved it 1×/7yd, you 6×/40yd → park one tank") — and gate hard, since on TBC SSC/TK most bosses are stationary (Void Reaver et al.), so the eligible set is tiny and there is no existing gating infra to lean on.

**A dedicated 'Positioning' tab — only if 2+ map insights ship, else embed** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ A decision, not a chart: whether positioning gets its own top-level tab or rides inside Bosses/Wipes/Execution. Recommendation: EMBED first (maps in Bosses, deaths in Wipes, geometry strip in Execution) because each insight is most actionable next to the boss/mechanic it explains; promote to a standalone 'Positioning' tab ONLY once 3+ per-boss maps + the death overlay justify a single navigable home with a shared legend and frame.
- _Lives in:_ Meta — governs ideas #1-#5. Default: no new tab. NEW: Positioning tab only as a later consolidation.
- _Action:_ Ship embedded for v1; revisit a dedicated tab after the maps prove they drive calls in playtesting. Avoids a half-empty tab that fails the worth-its-pixels bar.
- _Ours-vs-benchmark angle:_ N/A (structural). Keeps every positioning artifact tied to a benchmarked gap rather than a standalone gallery.
- _Sharpen / verdict note:_ Demote from a standalone feature to a one-line shipping constraint on ideas #1-#5 ("embed each map next to its boss/mechanic; no new tab until 3+ maps + death overlay exist") — it governs other ideas and produces zero pixels of its own, so it earns a place as a guardrail, not a tracked deliverable.

## Cross-tab augmentation

**Death-location mini-map on Wipes ("What Ends Your Attempts")** — _SHARPEN · low leverage · feasible: yes_

- _Shows:_ A tiny equal-aspect SVG per wall-boss plotting the X/Y where wipe-pull deaths occurred (from wipe-deaths.json death events, positioned via the resourceActor rule on the killing-blow/last DamageTaken event), colored by killing-blow cause. Tells you the deaths cluster in one spot (a bad-zone/positioning fail) vs scattered (a global/healing fail). Pairs the existing 'most common first death + killing blows' table with WHERE it happened.
- _Lives in:_ Wipes tab — inline next to 'What Ends Your Attempts' per boss (uses wipe-deaths.json that's already fetched).
- _Action:_ If deaths cluster on a spot, assign a callout/repositioning for that mechanic next attempt (e.g. 'move the spawn-point group 10yd left'); if scattered, it's not a positioning fix — chase the global mechanic instead.
- _Ours-vs-benchmark angle:_ First-party by nature (benchmark rarely wipes) — same honest framing the whole Wipes tab already uses; the value is the spatial pattern of OUR wipe deaths, not an ours-vs-them delta.
- _Sharpen / verdict note:_ The cluster-vs-scatter conclusion is largely ALREADY computed by the existing wipe block's causeMechanic/causeSustained split + topMechanics naming (the named killing blow usually implies the fix). Don't ship a per-boss SVG that re-derives it visually. Fold ONE spatial scalar into the existing "What Ends Your Attempts" text — a median-pairwise-distance "clustered/scattered" flag — and only surface the actual map when the killing-blow name is ambiguous (generic Melee/Fireball) and the spatial pattern flips the recommended action; keep the >=4-death gate.

**Spread-at-AoE column on Bosses → Deaths / Damage Taken** — _SHARPEN · medium leverage · feasible: yes_

- _Shows:_ For each shared boss, a single raid-spread number sampled at the moments a known raid-wide AoE / avoidable mechanic hit (read the timestamps of the avoidable killing-blow / big DamageTaken events, then measure the raid's positional spread — e.g. median nearest-neighbor or bounding radius — across all living players at that instant). Ours vs benchmark. Answers 'were we stacked when we should've been spread (or vice-versa)' at the exact mechanic moment.
- _Lives in:_ Bosses tab — a column/caption added to the per-boss Damage Taken or Deaths sub-tab (rides the timeline-[enc] + a new resourced fetch on the same shared boss).
- _Action:_ If our spread at the AoE instant is far tighter than benchmark on a chain-lightning/explosion mechanic, set a spread assignment for that boss; if too loose on a stack-required mechanic, call a stack.
- _Ours-vs-benchmark angle:_ Direct ours-vs-benchmark spread delta at the SAME mechanic on a shared boss — a clean gap that names a concrete spacing fix.
- _Sharpen / verdict note:_ Don't ship it as a standalone spread column — join it to the EXISTING avoidable-damage / death gap: only surface spread-delta on a boss where we already take more of a spread/stack-sensitive mechanic than the benchmark, so the number explains an existing gap ("we eat more Chain Lightning AND were 4yd tighter → set a spread"); otherwise it's true-but-inert geometry, especially on unavoidable-AoE bosses.

**Melee-uptime-on-boss column on Execution → Activity by Spec** — _KEEP · medium leverage · feasible: partial_

- _Shows:_ Per melee DPS spec, the fraction of the fight that spec's players were within ~melee range (~8yd ring) of the boss, pooled across shared bosses, ours vs benchmark same spec. This is the POSITIONAL cause behind the existing activity/uptime gap: a melee spec with low active-time because it's chasing a moving boss or standing out of range shows up here as low melee-uptime — a spacing/assignment fix, not a rotation one.
- _Lives in:_ Execution tab — a third companion under the existing 'Activity by Spec' (which already decomposes the DPS gap into uptime). This extends uptime into spatial uptime.
- _Action:_ If our melee spec's on-boss% trails benchmark, the fix is positioning/uptime discipline (pre-position for boss moves, use gap-closers) — distinct from the gear/rotation throughput lever, so it routes coaching correctly.
- _Ours-vs-benchmark angle:_ Ours-vs-benchmark same-spec on-boss% — clean better/worse, spec-level, mirrors the existing Activity-by-Spec bars exactly.
- _Sharpen / verdict note:_ Render the on-boss% bar ONLY when it diverges from the existing activeTime% bar (e.g. gap >5pts) — that divergence is the entire payload (spatial cause vs throughput); when they track, it's redundant pixels on an already-EXPERIMENTAL section. Interpolate to wall-clock seconds, not per-event, and label the ring "~8yd (relative)" to honor the FLOOR caveat.

**Spread-at-cast cross-link on Optimize (per-player, world-best)** — _SHARPEN · low leverage · feasible: partial_

- _Shows:_ For a raider whose rotation diverges in the Optimize tab, a positional note: their average distance-from-boss or time-out-of-optimal-range while casting their key abilities, vs the same-faction world-best player on the same boss. A melee/hunter whose 'rotation gap' is really a uptime/positioning gap (casting from too far, or out of melee) gets the honest cause — mirrors the existing hit-cap cross-link that explains a divergence with a fixable lever instead of blaming the rotation.
- _Lives in:_ Optimize tab — a per-raider note on a diverging row, exactly like the existing EXPERIMENTAL hit/expertise cross-link (hit_map → optBossBody).
- _Action:_ Tell that raider the divergence is positional (close the gap / stay in range), not a cast-priority change — coach-not-blame, the same pattern the hit-cap note already uses.
- _Ours-vs-benchmark angle:_ Per-player vs SAME-FACTION WORLD BEST on the same boss — fits the explicit Optimize exception; the world player's casts+positions come from their ranked report, which Optimize already fetches.
- _Sharpen / verdict note:_ Narrow to a MELEE-uptime note only (% of swings/casts inside the 8yd ring vs world-best); drop undefined caster 'optimal range'; gate on a min cast-sample count so a thin world-best fight degrades to no-note — and rank it last (own risk note agrees: ship only after cheaper ideas land).

---

# Addendum — ideas added in discussion (2026-06-05)

> Hand-added after the workflow run (the generator above was a one-time bootstrap; edit this section by hand). These were proposed in conversation and validated against the live `pkHqfrBbhQK9GP1a` (Imminent) report.

## Boss / add "planted position" detection — a per-phase anchor *primitive* — _KEEP · high leverage (as infrastructure) · feasible: yes (validated)_

Not a display feature on its own — a **foundational primitive** that the keeper features should be built on. Detect when the boss (or an add) **stops moving** after the pull / after a phase transition, and snapshot that **planted position**. The shipped prototype anchors everything to a *single whole-fight median* boss position, which smears across phases and re-plants and is simply wrong on any boss that moves; per-phase planted anchors fix that.

- _Shows:_ Per boss, the sequence of **planted positions** — when the boss settled, where, and for how long — derived with **zero phase metadata**. Method: pull the boss's own positions (dense, from `DamageDone targetID:<boss>` → `resourceActor 2` → target = boss), bin by time (~2s), and start a new "plant" whenever the bin-to-bin step exceeds a move threshold (~4yd); stable runs are the plants. Same method on any NPC id covers **adds** (their spawn/plant snapshot).
- _Lives in:_ Upstream of the position-based keepers (it produces the boss anchor they consume); the *classification* it yields can also surface as a one-line per-boss caption in Bosses.
- _Action:_ (a) Gives every melee-uptime / ranged-standoff / tank-separation / behind-the-boss / formation metric a **correct per-phase anchor** instead of a smeared whole-fight median. (b) Auto-classifies each boss **STATIONARY / PLANT-AND-MOVE / MOBILE**, which *gates* which features even make sense (e.g. "melee uptime on a MOBILE boss measures the boss's path, not your discipline — suppress it"). (c) The planted instant is the clean moment to **snapshot raid formation** (avoids both the median-collapse and the movement-smear). (d) Becomes its own comparison: **did we plant the boss where the benchmark did, and re-plant cleanly per phase, or drag it around?**
- _Ours-vs-benchmark angle:_ Plant count + plant locations + first-settle time, ours vs benchmark on a shared boss — "they parked it once and held; we re-planted 6×" is a tank/raid-control gap; and per-phase planted anchors make every *other* geometry comparison phase-accurate instead of phase-blurred.
- _Feasibility / caveats:_ Strong — the boss is the **densest-sampled actor** in the log (the whole raid hits it), so settle-detection is most reliable for exactly the actor we want; it's pure relative displacement (no `facing`, no calibration, no texture, no absolute yards). Thresholds (bin width, move yd, hold time) are tunable. Gaps appear when the boss is untargetable (between phases) — which is a *feature*: it tells you when the boss is actually engaged.

**Validated live on the Imminent report (TK):**

| Boss | Boss travel | Auto-class | Plants (settle-detected) |
|---|---|---|---|
| Void Reaver | ~11 yd | STATIONARY | 1 plant, settles **t=0**, holds 193s (ground-truth: a stationary boss *should* plant immediately) |
| Al'ar | ~1448 yd | MOBILE | 16 short plants, x flips ±6000 between platforms → "no stable plant" (correct verdict) |
| Solarian | ~122 yd | PLANT-AND-MOVE | 3 plants (tank spot → blink/teleport → re-plant) |
| Kael'thas | ~72 yd | PLANT-AND-MOVE | **first settle t=328s** (he's untargetable until P3), then re-plants at 360 / 386 / 400 / 460s — i.e. the per-phase snapshots, falling out for free |

_Spike: `boss_settle_spike.py` (scratch) — 2s bins, 4yd move threshold, 6s min hold._

## Add plant positions = a readout of the tank plan — _KEEP · high leverage · feasible: yes (validated)_

Same settle-detection applied to **every enemy NPC** in a fight (from `fights.enemyNPCs`), not just the boss. **Where an add plants — and whether it plants at all — reveals the tanking intent**, which nothing else in the report captures. A held add → tanked-and-assigned; a MOBILE add → fixate / kite / ranged-at-distance (deliberately *not* tanked in place). Comparing add-plant spots ours-vs-benchmark surfaces **two different tank strategies on the same fight**.

- _Shows:_ Per add: its plant location(s), hold duration, and STATIONARY / PLANT-AND-MOVE / MOBILE class. Together these reconstruct the add **assignment map** — which adds were tanked together, which were isolated, which roamed.
- _Lives in:_ Bosses tab (per-boss "add control" caption / mini-map on add fights); the class also gates per-add metrics.
- _Action:_ Read/compare the add plan: "they tanked both advisors together on the left; we let them drift apart" / "their off-tank pre-staged where the add spawns; ours grabbed it late." Drives a concrete tank-assignment or pre-positioning call.
- _Ours-vs-benchmark angle:_ Add-plant spots + which adds were held vs roamed, ours vs benchmark — a direct tank-strategy comparison on a shared add fight.
- _Feasibility / caveats:_ Works on uniquely-named adds directly. Same-type swarms share one actor id, **but every event carries a native `targetInstance` / `sourceInstance` counter (1..N)** — so grouping by `(actorId, targetInstance)` separates instances **exactly** (validated: `Solarium Agent ×12` → `targetInstance` 1–12, ~45 events each, each with its own HP curve and position cluster). So per-instance plants/positions/facing are available for swarms too; only group by instance before settle-detecting (don't disambiguate by HP — even-damaged instances share overlapping HP curves). Same no-`facing`-calibration, relative-geometry guarantees as the boss anchor.

**Validated live (Kael'thas P2 advisors, Imminent report):** Sanguinar held @(−2647, 77057) and Telonicus @(−3061, 77755) — **both tanked together on the left**; Capernian MOBILE, drifting to (+3717, 72569) — **caster isolated on the right**; Thaladred MOBILE/~381yd — **the fixate add, never planted**. The entire P2 add plan, recovered from positions alone.

_Spike: `add_settle_spike.py` (scratch)._

## Facing is DECODED — available for every actor, all the time — _supersedes §1's "open calibration question"_

The earlier "facing is gated behind a calibration spike" framing conflated *"we hadn't decoded the integer yet"* with *"it's hard / per-boss."* Neither is true:

- **Coverage = position coverage.** Facing rides on the *same* resourced events as x/y — a `DamageDone`-to-boss event carries the boss's `facing` right next to its position — so it's present for every boss, add, and player wherever a position sample exists. There is no per-boss availability problem.
- **The encoding is one universal constant, now solved from the data.** `facing` is **centiradians** (radians × 100) — proven by the observed value span = 628 = 2π×100, and a unit-fit where centiradians dominated (R=0.35 vs ~0.05 for radians/degrees). The transform to a bearing in the WCL x/y frame is **`heading_rad ≈ −facing / 100`** (sign −1, zero-offset ≈ 0°; from a 216-pair forward-run fit where −1/offset≈0 beat +1 decisively, 49% vs 26% within 30°). Solve once → applies to every actor in every fight, forever.
- **The residual scatter is the calibration *proxy's* noise, not facing's.** I calibrated against "players face their direction of travel," which is only true for forward running (strafing/backpedaling breaks it). The per-event facing value itself is exact. A densely-hit boss has current facing; a rarely-hit add can have stale facing (same staleness caveat as its position).
- **CONFIRMED against an independent ground truth (a boss faces its current target).** 9,101 boss→tank pairs across all four bosses; the clean stationary case nails the constant: **Void Reaver R=0.93, circ-std 22°, offset ≈ 357° ≈ 0°**; global median calibration error **6°** (45% within 5°). Sign −1 beat +1 decisively (R 0.67 vs 0.28). Solarian fit is noisy (R=0.18) *by mechanic, not decode* — she faces her ranged cast targets (Wrath/Arcane Missiles) and blinks, so "boss faces tank" is a poor proxy for her; the decode itself is fine (the real feature uses the boss's exact per-event facing, not this proxy).
- **Consequence:** facing is now a first-class, decoded per-actor field — `heading_xy_rad ≈ −facing / 100` (offset ≈ 0°) — that can be attached to any position we already read. E.g. a planted boss/add records both *where* it sat and *which way it pointed*. It's a building block, not a feature; no calibration gate. The only live caveat is staleness (a rarely-hit add's facing lags, same as its position).

_Spikes: `facing_calib_spike.py`, `facing_calib_mobs.py`, `facing_mode.py`, `facing_boss_target.py` (scratch)._
