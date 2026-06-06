# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> change how a raid leader runs next week — and can they read it and trust it in seconds?

---

## TODO: Parse Spread — remove

> remove parse spread

**Cut reason:** *Silly* — all three conditions met. No decision hangs on it: the floor-spec breakdown ("which specs are anchors?") is already answered, more precisely, by **DPS by Spec** in Execution — a leader who wants to know which specs to coach goes there. The gap shown is noise: median vs floor parse repackages the same `rankPercent` signal the Avg Raid Parse headline already carries. And it was mined because `rankPercent` was already in the parses file, not because a leader was asking for a parse distribution. An EXPERIMENTAL label on a feature that doesn't survive the worth-it test is still a dead-weight block in the Overview.

**Cleanup checklist:**

- `scripts/build_deepdive.py:3215` — delete `def parse_spread(...)` builder function and its docstring
- `scripts/build_deepdive.py:3610` — delete the `parse_spread_payload = parse_spread(...)` call site
- `scripts/build_deepdive.py:4036` — delete the `"parseSpread": parse_spread_payload` key from the DATA dict
- `templates/report.html:490` — remove the `+parseSpreadView(d)` call from the Overview renderer
- `templates/report.html:494–~530` — delete the full `function parseSpreadView(d){...}` block (and any scoped CSS inside it)
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — delete the **Parse Spread** bullet under the Overview section

---

## TODO: Provider Count & Coverage — Bloodlust scope bug (TBC Anniversary)

> bug PROVIDER COUNT & COVERAGE — shaman lust is raidwide in tbc anniversary, not party wide

Accuracy floor violation. The Composition tab's Provider Count & Coverage section currently classifies Bloodlust as `group`-scoped, meaning it treats more Shaman providers as "more groups covered" — a leader reading this could think a second Shaman is needed when one already covers the whole raid. In TBC Anniversary, Bloodlust/Heroism is raid-wide, so the right classification is `raid`-scoped: one provider delivers it in full, and count >1 is a single-point-of-failure note, not a coverage gap. Fix the scope entry for Bloodlust (and verify Heroism) in `PROVIDER_CHECKS` to match Anniversary reality.

---

## TODO: Drums Uptime — remove from Consumables Coverage

> DRUMS UPTIME remove from consumables coverage

**Cut reason:** *Silly / redundant.* No prep decision hangs on it — a leader can't "fix" drums uptime the way they fix missing flasks; Drums coverage depends on group composition and fight length, not an individual raider showing up ready. It's already visible in the per-boss **Buff Uptime** sub-tab via `KEY_BUFFS` ("Drums of Battle"), so it's also *redundant* in Consumables. The hint text on the Coverage section already hedges it as an uptime %, not a prep signal — which is the tell that it doesn't belong here.

**Cleanup checklist:**

- `scripts/build_deepdive.py:483` — delete `DRUM_NAMES` constant (only used by the drums uptime path)
- `scripts/build_deepdive.py:555–556` — remove `if name in DRUM_NAMES: return "drums"` branch from `_consumable_cat`
- `scripts/build_deepdive.py:582` — delete `drum_upt = []` initialization
- `scripts/build_deepdive.py:595–600` — delete the drums uptime computation block (the `# Drums uptime` comment + loop)
- `scripts/build_deepdive.py:647` — delete `"drumsUptime": iavg(drum_upt)` from the consumable_report DATA dict
- `templates/report.html:628` — remove "Drums shown as uptime" clause from the Consumables Coverage `<span class="hint">`
- `templates/report.html:632` — delete the `acard("Drums Uptime", ...)` render line
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — remove the "Drums uptime % = fight-uptime from aggregate Buffs" clause from the Consumables Coverage bullet

---

## TODO: Hit & Expertise — verify accuracy for Feral/Guardian bear tanks

> confirm no bug in Imminent — hit & expertise by raider for calculating beartreebear hit for standard tanking feral/guardian in tbc

Accuracy floor check. The Hit & Expertise view is the one per-player gear fix in Prep — a false flag or a silent miss on a tank directly misleads the leader about what to gem/enchant. The code path for bears looks correct on a read: `_hit_kind("Druid", "Guardian"/"Feral", "tank")` returns "melee" — right, since bears use melee attacks; `SPEC_TALENT_HIT` deliberately omits Feral/Guardian (0 talent hit — correct, bears gear to the 9% cap through gear alone, no standard hit talent); `HIT_CAP["melee"]` = 9% — correct vs a +3 raid boss; and `stat_audit` iterates the "tanks" bucket in `playerdetails.json` so Beartreebear is included.

**The one thing to verify in the live report:** whether `spec_map` resolves Beartreebear to "Guardian" or "Feral" (both miss `SPEC_TALENT_HIT`, giving 0 talent hit — the correct answer either way), and whether their effective hit reads plausibly against the 9% cap. Open the rendered Hit & Expertise table in the Imminent report and spot-check Beartreebear's gear/talent/effective columns.

---

## TODO: Activity by Spec — remove from Execution tab

> ACTIVITY BY SPEC in execution tab

**Cut reason:** *Silly* — no decision hangs on it. The section names which spec is trailing on active-GCD uptime but explicitly disclaims it can't say *why* (movement, range, target swaps — the hint itself tells the leader to go diagnose elsewhere). That's a raw dimension, not a lever. The cause — the thing a leader can actually act on — is already surfaced in Add Control, Damage Taken, and per-boss Positioning. Mined because `activeTime` was available; the activity aggregate (raid-wide) already lives in Output Quality and feeds the Overview scorecard — the spec breakdown adds noise, not resolution.

**Important:** `activity_pct` (raid-wide aggregate, line 1366) and the per-boss `oursActivity`/`theirsActivity` fields (line 3857) are **not** touched — they feed Output Quality and the Overview scorecard independently. Only the *spec-level* rollup is removed.

**Cleanup checklist:**

- `scripts/build_deepdive.py:1435` — delete `def activity_buckets(...)` function
- `scripts/build_deepdive.py:1732` — delete `def tier_activity_gap(...)` function
- `scripts/build_deepdive.py:3698` — delete `tier_o_act, tier_t_act = {}, {}` initialization
- `scripts/build_deepdive.py:3781–3788` — delete the `# Pool per-spec activity` comment + accumulation loop block
- `scripts/build_deepdive.py:3921` — delete `tier_activity = tier_activity_gap(tier_o_act, tier_t_act)` call
- `scripts/build_deepdive.py:4043` — delete `"tierActivityGap": tier_activity` from the DATA dict
- `templates/report.html:749` — remove `h+=activityGapView(d)` call from the Execution renderer
- `templates/report.html:1084–~end` — delete the full `function activityGapView(d){...}` block
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — delete the **Activity by Spec** bullet under Execution

---

## TODO: Ghost Run — reframe as interactive Timeline overlay on Bosses tab

> turn GHOST RUN — WHAT DYING COSTS YOU into a visualization instead of text, can also show up to top 5 players deaths stats per boss in this section
>
> Make it like a mini timeline and draw the dmg lost over time from where they died — ooo maybe do we move this section/stats/projection onto the bosses timeline tab, and theres a toggle that when clicked, rerenders our dps line based on if they never died, and would also update the kill time, yeah lets do this timeline thing on bosses tab thats cool
>
> And you can toggle each person that died, and it would incrementally update the kill time / DPS trendline when toggling each player death on/off
>
> Make sure this section is moved/integrated into bosses per-boss timeline tab. Should just project the raider-that-died's average DPS across all bosses for the ghost DPS projection.

**Mandate: view the rendered HTML as a raid leader first.** Open the current report (`reports/` or the published link), navigate to the Ghost Run section as it exists today, and read it cold — as a leader who hasn't seen the code. Only after forming that impression, build the reframe below.

**This is a MOVE, not a copy.** The standalone Ghost Run text block is removed from wherever it lives today and lives **only** inside the per-boss **Timeline** sub-tab (Bosses tab) as an interactive overlay. No duplicate section remains behind.

**The overlay:** a toggle re-renders our raid-DPS curve as if the DPS deaths never happened — the ghost line sits above the actual line, the area between them is the output the deaths consumed, and a projected kill time updates alongside it. Up to 5 costliest DPS deaths per boss annotated on the timeline (the death tick already exists; this adds the DPS-cost label). The benchmark line stays untouched — the ghost is ours-only.

**Projection method (pinned):** the ghost rate for each dead raider = **that raider's average DPS across all shared bosses**, NOT their noisy pre-death rate on this one fight. A raider who died 20s into a pull has too short/erratic a same-fight sample to project from; their all-boss average is the stable per-raider rate. Apply that rate to the dead window (death → kill) to get the recovered output, then re-derive the projected kill time. (Open question for the build: their all-boss average is per-second, so the dead window in seconds × avg DPS = recovered damage — straightforward.)

**Per-death toggles (the interactive core):** each dead player is its own toggle, not one all-or-nothing switch. Flipping a single raider's death on/off **incrementally** recomputes the ghost DPS curve and the projected kill time — so a leader can isolate "what did *just* the warrior dying at 40% cost us?" vs. the full set. The toggles compose: the ghost line and kill-time projection reflect whichever subset of deaths is currently switched off. This is the lever — it lets a leader weigh individual deaths against each other and see which one actually decided the kill.

**Why the Timeline is the right home:** it's already where a leader reads the fight shape; the gap between actual and ghost DPS lands in exactly the right context (you can see *when* in the fight the deaths hurt most). The current text block answers "how much?" but not "when?", "relative to what?", or "which death?" — the interactive timeline answers all four.

**Before building, validate from the rendered view:**
- Does the current Ghost Run text block read as useful or as a curiosity? Does the player-minutes framing land?
- Is the timeline already dense enough that an overlay + per-death toggles would clutter it, or is there room?
- Would a leader actually toggle individual deaths, or would they read the headline number and move on?
- Honesty check: the all-boss-average projection is an *estimate* (assumes the dead raider would have sustained their average rate, no battle-res, no compounding) — the surface must label it an upper-bound projection, not a counterfactual fact.

If the rendered section already reads clearly and the timeline feels like overengineering, a `/todo-remove` may be the right verdict instead.

---

## TODO: Buff & Debuff Coverage Gaps — verify debuff target scoping

> check that BUFF & DEBUFF COVERAGE GAPS aren't only checking the main boss, maybe the paladin tank can't apply his debuff to the main boss because he is tanking an add

Accuracy floor concern. Debuff uptime is read from the WCL aggregate Buffs table via `_auras(report, "debuffs")` and `uptime_pct(..., totalUptime)`. The open question: does WCL scope that table to the **main boss only**, or does it aggregate debuff uptime across **all hostile targets** in the encounter? If it's main-boss-only, a Prot Paladin tanking adds who applies Judgement/Sunder to the add — not the main boss — reads as a false debuff gap on the main target, misleading the leader into a coverage problem that isn't one (or masking a real one if the debuff should be on the main boss).

**How to verify:** pull the raw WCL API response for a known multi-add fight (e.g. Al'ar, Kael) and inspect whether the `debuffs` auras table contains uptime contributions from the off-tank's add, or only from the main boss. If main-boss-only, the section needs an inline caveat for multi-target fights — or, if the key debuffs (`KEY_DEBUFFS`: Sunder, Expose, CoE, Faerie Fire, Misery, Judgements) are all expected on the main boss regardless, confirm the off-tank scenario actually produces a false flag before treating it as a bug.

---

## TODO: Cooldown & Trinket Usage — reframe (or zoom?) the by-spec cut

> Reframe or todo-zoom for COOLDOWN & TRINKET USAGE — BY SPEC — im not sure

**Mandate: view the rendered HTML as a raid leader first.** Open the current report, go to Execution → **Cooldown & Trinket Usage** (`cd_usage_pool`/`tier_cd_usage` → `cdUsageView`), and read it cold — major DPS cooldowns + on-use trinkets fired per minute, pooled by (class, spec), ours vs benchmark. Form the consumer impression *before* opening the builder/renderer.

**The hunch (user unsure: reframe vs zoom):** the by-spec cut may be the wrong axis, or the right axis at the wrong grain. Decide which from the rendered view:
- **Reframe (different axis, same data)** — if the per-spec rows read as a scoreboard a leader can't act on, re-cut: **by cooldown/trinket** (which specific CD is the raid under-firing, across everyone?), **by phase/window** (are CDs landing where they matter?), or fold the better/worse delta into a single "who's leaving a cooldown on cooldown" lever.
- **Zoom (one cut deeper, finer grain)** — if the axis is right but the row is too coarse, go deeper: the per-minute *number* per spec hides *which* cooldown is missed (a Fury warrior at 0.8 Death Wish/min vs the benchmark's 1.1 is the lever; "cooldowns: 3.2/min" is not). Break the spec's pooled rate into its individual cooldowns/trinkets.
- **Note the overlap with Bloodlust:** the "CDs in window" column already lives in the Bloodlust section. Whatever reframe lands here must not duplicate that — decide whether cooldown *alignment* belongs there and cooldown *frequency* belongs here, or whether they should merge.

**Verdict path:** if the rendered view already names a clear lever, leave it. If it's a true better/worse signal buried by the axis/grain — reframe or zoom per above. If no decision hangs on it at any cut, it's a `/todo-remove`.

---

## TODO: Bloodlust — reframe "are you stacking burst into it?"

> reframe BLOODLUST — ARE YOU STACKING BURST INTO IT?

**Mandate: view the rendered HTML as a raid leader first.** Open the current report, go to Execution → **Bloodlust — Timing & Payoff** (`lust_window_mult` + per-boss `lust_sec` → `bloodlustView`), and read it cold. Today it shows three things per boss: **when** lust popped (descriptive), the **window payoff** (raid DPS in the 40s lust window ÷ fight-average DPS, >1× = burst stacked), and **CDs in window** (share of major-cooldown TYPES whose buff overlapped the window). Form the consumer impression *before* opening the code.

**The hunch:** the section's whole question is "are you stacking burst into Bloodlust?" — but it may not *answer* that legibly. Three columns (timing / payoff multiplier / CDs-in-window) ask the leader to synthesize the verdict themselves. From the rendered view, decide:
- **Reframe (clearer presentation of the same data)** — if the three columns are individually true but collectively unreadable, collapse them into the one read the heading promises: a single "did burst land in the window?" signal (payoff × alignment), with timing as context, not a co-equal column.
- **Reframe (different slice)** — if the raid-aggregate payoff hides *who* failed to align, re-cut **by spec**: which spec's cooldowns missed the window (the actionable assignment — "tell the mages to hold Icy Veins for lust"), instead of a raid-wide multiplier that names no one.
- **Honesty guard:** timing is explicitly descriptive (on-pull vs saved-for-a-phase is strategy, not a target) — any reframe must keep timing neutral and not imply a "correct" lust time.

**Verdict path:** if the rendered view already answers "are you stacking burst into it?" at a glance, leave it. If the signal is real but buried across three columns or hidden at raid-aggregate grain — reframe per above. If no decision hangs on it, it's a `/todo-remove`.

---

## TODO: Early Aggro — Threat Pulls — zoom in by spec

> /todo-zoom EARLY AGGRO — THREAT PULLS

**Current grain:** per-boss count of times a non-tank held the named boss's aggro, plus an opener count (first 30s). Clean better/worse (fewer = better). Under-counts by design (only brief holds ≤15s tagged). Opener count feeds the Overview scorecard.

**Proposed deeper grain:** break the pull count by **spec** — which spec's players are responsible for the threat events per boss? The total-count row already tells the leader *that* there's an aggro problem; the spec split tells them *who to address*: "your Fire Mages are pulling on the opener" → Misdirection assignment or hold-for-tanks cue; "your Combat Rogues" → Vanish/Feint discipline. Same data, one cut down from a boss-level tally to a spec-level attribution — from scoreboard to lever.

**Builder / renderer:** `threat_pulls` (builder, `scripts/build_deepdive.py`) → `threatPullsView` (renderer, `templates/report.html`). The DATA payload today is a per-boss object `{ count, openerCount, better }`. To add the spec cut, accumulate a `bySpec: { [specKey]: count }` map inside the per-boss object, sourced from the raw threat-event records already iterated in `threat_pulls`. The renderer then renders a compact spec breakdown row beneath each boss's count.

**Before building, judge it as a consumer first.** Open the rendered report, navigate to Execution → **Early Aggro — Threat Pulls**, and read it cold:
- Does the current per-boss count read as a lever or as a bare scoreboard? (If it already feels actionable — maybe pull counts are so low they name the single offender — the spec breakdown may be overkill.)
- Is the opener count the real signal, and the per-boss total just context? If so, the zoom may belong *there* (which specs fire the opener?), not on the general pull count.
- Honesty check: the under-count caveat (brief holds only) means the spec attribution is also an under-count — label it as a floor, not a full accounting.

If the rendered view shows low pull counts that don't warrant a breakdown, or if the opener count is already the only number that matters, this may resolve as a cosmetic polish rather than a structural zoom.

---

## TODO: Add Control — Kill Speed — center rightmost column values

> Move the rightmost column values to be centered under the add name

Legibility fix. In `targetEngagementView` (`templates/report.html:1315–1342`), each add row uses the `ugridc` grid: `[ours value] [ours bar→] [add name + delta] [←theirs bar] [theirs value] [counts]`. The theirs-lifespan value (`<div class="dval ro">`) currently sits flush to the right edge of the container rather than visually centering under the add name column. A leader scanning the row has to hunt for the benchmark number.

Fix: adjust CSS alignment so the rightmost lifespan value centers under (or directly adjacent to) the add name. The `ugridc` grid is defined at `report.html:236` (`grid-template-columns:38px 1fr 90px 1fr 38px minmax(48px,auto)`); `.dval.ro` may need `text-align:center` or a grid placement tweak. Match whatever the fix is to `.dval.lo` (the ours side) so both sides read symmetrically.

---

## TODO: Execution tab — move Output Quality and Clear Efficiency to top

> OUTPUT QUALITY move to top of tab section
> Same for CLEAR EFFICIENCY

Legibility improvement. Currently **Output Quality** renders as item 4 (lines 780–802 of `renderExecution`) and **Clear Efficiency** as item 5 (lines 807–818), both at the very bottom of the Execution tab. They are macro "are we winning?" reads — Raid DPS, activity, damage taken, HPS, overheal, wall-clock vs fight time — and a leader must scroll past all the sub-gap detail (What's Killing Us, Spec DPS, Buff Gaps, Interrupts, Cooldowns…) before reaching them.

Fix: in `renderExecution` (`report.html:729`), move the Output Quality block (section `/* 4. Output quality */`) and the Clear Efficiency block (section `/* 5. Clear efficiency */`) to render **before** What's Killing Us (currently section `/* 1. */`). The macro view first, then the drill-down — consistent with how the Overview tab leads with the summary cards. No builder changes — pure render-order move in the renderer.

Note: the `dmgMode` toggle inside Output Quality also re-renders the Bosses tab (`renderBossesPanel`). That coupling is unaffected by the move.

---

## TODO: Kill Summary &amp; Rosters — remove from Bosses tab

> Kill Summary &amp; Rosters

**Cut reason:** *Redundant / data dump.* The Kill Summary block (`bossSummaryBlock`) appears beneath each boss's execution panel on the Bosses tab and contains: kill time bars, Raid DPS/HPS bars, avg parse bar, deaths bar, wipes before kill, wipe depth, and two full roster tables. Every signal in it is already present elsewhere: kill time and DPS curve are on the Timeline; deaths and killing blows are on the Deaths sub-tab; wipes and wipe depth are on the Wipes tab; composition + rosters are on the Composition tab. The roster tables in particular are a data dump — a list of names with parses that doesn't surface a lever. No decision hangs on the Kill Summary block that isn't already made by the tabs above it.

**Note on data payload:** some per-boss builder fields (`oursRaidDps`, `theirsRaidDps`, `oursRaidHps`) may also be read by the Timeline chart or the Overview scorecard — grep before deleting them from the builder. The `ours.players`/`theirs.players` arrays are very likely exclusive to this block.

**Cleanup checklist:**

- `templates/report.html:78–80` — delete `.rostergrid`, `.rostergrid h4`, `.rostergrid h4.ours`, `.rostergrid h4.theirs` CSS rules
- `templates/report.html:283–292` — delete `function rosterTable(...)` (only called by `sideRosters`)
- `templates/report.html:295–301` — delete `function sideRosters(...)` (only called by `bossSummaryBlock`)
- `templates/report.html:519–540` — delete `function bossSummaryBlock(...)` and its preceding comment
- `templates/report.html:879` — remove `${bossSummaryBlock(b,d)}` from the bsub div (keep `${panel}` + the wrapper)
- `scripts/build_deepdive.py` — grep for `"players"` in the per-boss build loop; delete the `players` payload builder that populates `b.ours.players`/`b.theirs.players`. Verify `oursRaidDps`/`theirsRaidDps`/`oursRaidHps`/`theirsRaidHps` per-boss fields before removing — if used only by `bossSummaryBlock`, delete; if used by Timeline, leave.
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — remove the `sideRosters`/`rosterTable` references in the Overview "Boss-by-Boss" bullet (the rosters half); update or remove the note that kill-summary content moved to the Bosses tab

---

## TODO: Positioning — remove Spread over time and Why we eat more

> bosses tab — positioning Spread over time
> Also remove "why we eat more…" from positioning subtab

**Cut reason (Spread over time, feature 5):** EXPERIMENTAL, buried three levels deep (Bosses tab → boss → Positioning sub-tab), and the time-series detail — "the gap opens around 60% into the fight" — is precision a leader can't act on beyond what the spread-vs-demand verdict (feature 2, which **stays**) already names. The verdict says *what to do*; the strip just adds a *when* that's too fine-grained for the report's legibility floor.

**Cut reason (Why we eat more + Void-zone heatmap, features 1 and 4):** EXPERIMENTAL scatter/heatmap; the avoidable-damage mechanic is already surfaced and ranked in Execution → Avoidable Damage by Mechanic. The spatial "is it clustered or scattered?" verdict is real but rendered in a sub-tab most leaders won't reach, and it only fires when a qualifying mechanic has ≥5 distinct non-tank targets — i.e. it's usually absent. Cut and let Execution's Avoidable Damage carry the signal.

**What stays:** feature 2 (Raid formation & spread maps + spread-vs-demand verdict) — the formation map and the spread direction call are the primary lever the Positioning sub-tab provides.

**Cleanup checklist — `scripts/positioning.py`:**

- `positioning.py:225–~230` — delete `def spread_series(...)` (feature 5 data builder)
- `positioning.py:476–~530` — delete `def _strip_svg(...)` (feature 5 SVG renderer)
- `positioning.py:598–626` — delete the `# ---- feature 5: spread-over-time strip ----` block inside `boss_positioning()` (the `strip_html` assembly)
- `positioning.py:318–~400` — delete `def ability_cluster(...)` (feature 1 spatial analysis)
- `positioning.py:428–~441` — delete `def _scatter_panel(...)` (feature 1 scatter SVG)
- `positioning.py:443–~474` — delete `def _heatmap_panel(...)` (feature 4 heatmap SVG)
- `positioning.py:692–~714` — delete `def _top_avoidable_with_hits(...)` (features 1+4 ability picker)
- `positioning.py:628–659` — delete the `# ---- feature 1 + 4: the top avoidable ability ----` block inside `boss_positioning()` (the `ability_html` assembly)
- `positioning.py:541–543` — update the `boss_positioning()` docstring (currently says "features 1, 2, 4, 5") to "feature 2 only"
- `positioning.py:1–12` — update the module docstring: remove items 1, 4, 5 from the features list
- `positioning.py:540` / call site in `build_deepdive.py` — the `avoidable_rows` parameter is only used by feature 1; after removing that block, drop the parameter from `boss_positioning()` and its call site

**Cleanup checklist — `templates/report.html`:**

- `report.html:842–843` — update the Positioning sub-tab comment (currently mentions "spread over time, the avoidable-ability scatter + heatmap") to just "the formation map and spread verdict"

**Cleanup checklist — `references/report-anatomy.md`:**

- Delete the **Spread over time (feature 5, `spread_series`)** bullet under Positioning
- Delete the **Why we eat more `<ability>` (feature 1, `ability_cluster`) + Void-zone density (feature 4)** bullet under Positioning

---

## TODO: Positioning formation map — reframe as snapshots at meaningful moments

> we should be showing positioning snapshots between raids for:
> - once positions roughly stabilized immediately after pulls
> - when it is clear that a boss mechanic triggered a repositioning of the raid (label the mechanic)
> - at the beginning of each phase once the boss/adds positions stabilize
> - make sure adds shown too and the direction each is facing

**Mandate: view the rendered HTML as a raid leader first.** Open the current report, navigate to the Bosses tab → any boss with a Positioning sub-tab, and read the existing Raid formation & spread maps cold — as a leader who hasn't seen the code. Note what story the current formation maps tell (or fail to tell) before evaluating the reframe below. **Do not open `positioning.py` or `report.html` to form your initial verdict.**

**The hunch:** the current formation map is a single whole-fight median-position snapshot per player — everyone's average position across the entire fight squashed into one picture. That collapses the fight's spatial story into a static smear. A leader wants to know *where was the raid when it mattered*: the opening position, the moment a mechanic lands and forces repositioning, the start of each phase. Multiple moment-specific snapshots — each labeled by what triggered them — would let a leader compare "where were we in Phase 2 vs the benchmark's Phase 2?" and "did the Arcane Orbs scatter us or did we hold formation?"

**What to decide from the rendered view:**
- Does the current single-median map actually read as useful? Can a leader understand their raid's shape from it, or does it look like a noise cloud?
- Is the signal that's latent here (where the raid held vs where the benchmark held at key moments) genuinely decision-changing, or is "spread your raid better" already captured by the spread-vs-demand verdict text beneath the maps?
- Would a leader read multiple labeled snapshots, or would they check one and move on? (Legibility: each snapshot adds a map; three snapshots = three SVGs to parse.)

**If the reframe is worth it — the axis to re-cut along:**
- **By when** (temporal axis): replace the single median-position map with 2–4 moment-specific snapshots, each labeled with what defined that moment:
  - *Opening formation* — positions once the raid stabilized after the pull (first ~5s after the initial flurry of movement dies down; detect via median pairwise-position variance dropping below a threshold)
  - *Post-mechanic repositioning* — when a trackable AoE mechanic fires and the raid noticeably shifts (label the mechanic and the time into the fight; detect via a spike in median pairwise-distance change after an ability hit)
  - *Phase transitions* — a snapshot ~5s after the phase boundary stabilizes (from `phaseTransitions`; skip if fewer than 2 raiders changed position by >5yd)
- **Adds & facing:** include non-boss hostile actors (the named adds that appear in `masterData`) as distinct shapes/colors on the same map. Facing direction per actor: WCL's `facing` field (centiradian-encoded; see the positioning skill's `coordinate-system.md`) as a small directional arrow on each dot — both for players AND adds, since add facing is what determines cleave/cone-ability threat arcs.

**Honesty guards to carry into the build:**
- Each snapshot caption must name its trigger ("Phase 2 start", "Arcane Orbs at 45s", "pull opener") so the leader isn't guessing why this moment was chosen.
- The stabilization heuristic (movement variance dropping below threshold) is approximate — label the snapshot time, not just the label, so a leader can cross-reference the Timeline.
- Facing arrows only when `facing` data is available for that actor at that moment; don't infer or interpolate.
- If fewer than 2 defined moments can be detected (e.g. a single-phase stationary boss with no qualifying mechanics), fall back to the current single median-position map with no regression in coverage.

**If the rendered view shows the current map is already too hard to read as a static image** — the reframe may be solving the wrong problem. In that case, consider whether the Positioning sub-tab's real failure is legibility of a single map (a rendering fix — bigger SVG, cleaner role colors, boss ring more prominent) rather than needing more maps.

---

## TODO: DPS by Spec (Bosses tab) — remove ×N vs ×N count badge

> on dps by spec in bosses tab, remove the "x2 vs x2" type value in the center of the viz

**Cut reason:** *Scoreboard noise / redundant.* The count badge `×${r.oursCount} vs ×${r.theirsCount}` sits inside the already-crowded center label of each spec row alongside the spec name and the per-player gap delta. It exists to justify why avg-DPS is a fair comparison (3 mages vs 2 mages stays per-player), but the section intro prose already makes that point explicitly and the hint text says the same. Displaying the raw roster counts inline on every row adds visual noise to the center column without adding a lever — the composition question ("they run 3 mages, we run 2") is for the Composition tab, not a DPS bar chart.

**Cleanup checklist — one ref, renderer only:**

- `templates/report.html:1360` — in `specDpsView`, delete `<span class="role">×${r.oursCount} vs ×${r.theirsCount}</span>` from the `dmid` div

**Note:** `.role` CSS (line 75) is shared across many other rendering contexts (roster table role column, consumables matrix spec labels, potion-by-spec table) — do **not** delete the CSS rule. The `oursCount`/`theirsCount` fields in the DATA payload also stay — they may be used to compute `oursAvg`/`theirsAvg` in the builder; verify before touching them.

**Note:** `tierSpecGapView` (Execution tab equivalent, line 1067) does **not** have the count badge — no change needed there.

---

## TODO: Hint text — trim all to ≤50 words  *(EXECUTE LAST)*

> all class="hint" should be less than 50 words across the entire report, do not lose meaning when cutting

**⏳ Sequencing: do this AFTER every other TODO above has settled.** Trimming hints now would be wasted or wrong work — several pending items remove sections outright (Activity by Spec, Drums Uptime, Parse Spread, Kill Summary & Rosters, Positioning strip+scatter), and others rewrite a section's surface entirely (Ghost Run move, the Cooldown and Bloodlust reframes). Their hints will be deleted or rewritten anyway. Trim the hints once the set of sections — and their wording — is final, so this is a single clean pass over the report's *actual* final hints, not a moving target.

Legibility floor. A leader reads hints cold, in seconds — a 100-word tooltip is a wall they skip. The soul's rule: a correct signal nobody reads transfers zero value. At last count **23 of ~30 hints** exceeded 50 words (the longest ran 114) — re-count after the section churn settles. Trim each to ≤50 words, preserving the signal: what the section shows, what direction is better, and any honest caveat the leader needs to act on it. No new hedges, no new examples — just cut filler and redundant framing. All changes are in `templates/report.html` hint `<span>` blocks only.
