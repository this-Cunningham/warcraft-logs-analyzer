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

**Cut reason:** *Silly / redundant.* No prep decision hangs on it — a leader can’t "fix" drums uptime the way they fix missing flasks; Drums coverage depends on group composition and fight length, not an individual raider showing up ready. It’s already visible in the per-boss **Buff Uptime** sub-tab via `KEY_BUFFS` ("Drums of Battle"), so it’s also *redundant* in Consumables. The hint text on the Coverage section already hedges it as an uptime %, not a prep signal — which is the tell that it doesn’t belong here.

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

## TODO: Hint text — trim all to ≤50 words

> all class="hint" should be less than 50 words across the entire report, do not lose meaning when cutting

Legibility floor. A leader reads hints cold, in seconds — a 100-word tooltip is a wall they skip. The soul's rule: a correct signal nobody reads transfers zero value. **23 of ~30 hints** currently exceed 50 words (the longest runs 114). Trim each to ≤50 words, preserving the signal: what the section shows, what direction is better, and any honest caveat the leader needs to act on it. No new hedges, no new examples — just cut filler and redundant framing. All changes are in `templates/report.html` hint `<span>` blocks only.

---

## TODO: Activity by Spec — remove from Execution tab

> ACTIVITY BY SPEC in execution tab

**Cut reason:** *Silly* — no decision hangs on it. The section names which spec is trailing on active-GCD uptime but explicitly disclaims it can't say *why* (movement, range, target swaps — the hint itself tells the leader to go diagnose elsewhere). That’s a raw dimension, not a lever. The cause — the thing a leader can actually act on — is already surfaced in Add Control, Damage Taken, and per-boss Positioning. Mined because `activeTime` was available; the activity aggregate (raid-wide) already lives in Output Quality and feeds the Overview scorecard — the spec breakdown adds noise, not resolution.

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

**Mandate: view the rendered HTML as a raid leader first.** Open the current report (`reports/` or the published link), navigate to the Ghost Run section as it exists today, and read it cold — as a leader who hasn’t seen the code. Only after forming that impression, consider the reframe below.

**The idea:** retire the standalone text block and fold the signal into the per-boss **Timeline** sub-tab as an interactive overlay. A toggle re-renders our raid-DPS curve as if the DPS deaths never happened — the ghost line sits above the actual line, the area between them is the output the deaths consumed, and a projected kill time updates alongside it. Up to 5 costliest DPS deaths per boss annotated on the timeline (death tick already exists; this adds the DPS-cost label). The benchmark line stays untouched — the ghost is ours-only.

**Per-death toggles (the interactive core):** each dead player is its own toggle, not one all-or-nothing switch. Flipping a single raider's death on/off **incrementally** recomputes the ghost DPS curve and the projected kill time — so a leader can isolate "what did *just* the warrior dying at 40% cost us?" vs. the full set. The toggles compose: the ghost line and kill-time projection reflect whichever subset of deaths is currently switched off. This is the lever — it lets a leader weigh individual deaths against each other and see which one actually decided the kill.

**Why this might be the right home:** the Timeline is already where a leader reads the fight shape; the gap between actual and ghost DPS lands in exactly the right context (you can see *when* in the fight the deaths hurt most). The current text block answers "how much?" but not "when?", "relative to what?", or "which death?" — the interactive timeline answers all four.

**Before building, validate from the rendered view:**
- Does the current Ghost Run text block read as useful or as a curiosity? Does the player-minutes framing land?
- Is the timeline already dense enough that an overlay + per-death toggles would clutter it, or is there room?
- Would a leader actually toggle individual deaths, or would they read the headline number and move on?
- Honesty check: the incremental recompute is a *projection* (assumes the dead raider keeps dealing their pre-death rate, no battle-res, no compounding effects) — make sure the surface labels it as an upper-bound estimate, not a counterfactual fact.

If the rendered section already reads clearly and the timeline feels like overengineering, a `/todo-remove` may be the right verdict instead.
