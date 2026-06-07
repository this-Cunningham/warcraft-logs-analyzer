# Report Explanation-Correctness Audit — do the words match the math?

> **⚠ Point-in-time snapshot (2026-06-05).** Several features named here have since been **cut** and are no
> longer in the report: *Parse Spread* (Overview), and the EXPERIMENTAL Execution views *DPS Ramp*,
> *Target Focus*, *Healing Efficiency by Spec*, and *Rotation — Ability Mix*. See `references/report-anatomy.md`
> for the current feature map.

**Date:** 2026-06-05 · **Scope:** every user-facing explanation in the deep-dive report
(`templates/report.html`) — tab hints, "how to read" paragraphs, card labels, column headers,
tooltips — across **all 8 tabs**: Overview, Composition, Prep, Execution, Bosses, Wipes, Optimize,
Trash. · **Method:** each explanatory string was traced to the Python that produces the data it
describes (`scripts/build_deepdive.py`, `fetch_report.py`, `fetch_worldbest.py`) and checked for
agreement.

This is a *correctness* audit, not a style pass: the only question asked of each sentence is **"is
this true of what the code actually computes?"** Per the [product soul](../PRODUCT_MANAGER_SOUL.md),
a clean better/worse signal is worthless if the label lies about what it measures — a raid leader who
trusts a wrong caption coaches the wrong thing.

**Result:** 12 mismatches found (2 `WRONG`, 3 `MISLEADING`, 1 `STALE`, 6 `MINOR`) across 6 of the 8
tabs. **All 12 are fixed in this PR** (13 edits — one issue had two instances). Overview/Wipes/Optimize
were the cleanest; the Prep tab carried the most. Every fix is a text-only change to an explanation;
no calculation was altered.

---

## TL;DR — findings table

| # | Severity | Tab | The claim | Reality | Fixed |
|---|----------|-----|-----------|---------|:---:|
| 1 | **WRONG** | Prep | In-combat matrix lists an **"HP health"** column | No HP column exists — `SUB` is `P/MP/HS`; health pots are deliberately not tracked | ✅ |
| 4 | **WRONG** | Composition | Misery = **"+3% spell damage taken"** | It's **+5%** — the code's own comments say so in two other places | ✅ |
| 2 | **MISLEADING** | Prep | "Prepared = flask **OR** full battle+guardian pair" | A **DPS** passes on a battle elixir alone (no guardian) | ✅ |
| 3 | **MISLEADING** | Prep | Same "flask or battle+guardian pair" rule restated | Same undisclosed DPS battle-elixir exception | ✅ |
| 9 | **MISLEADING** | Optimize | **"World #7 Horde Fire Mage"** | `globalRank` is the **all-faction** rank; the row is the *best Horde* player, #7 *overall* | ✅ |
| 5 | **STALE** | Prep | "(Potion use **isn't tracked** in Classic logs.)" | Five potion-tracking views sit in the same tab | ✅ |
| 6 | MINOR | Execution | Activity = **"active-casting time"** (×2 hints) | WCL `activeTime` counts melee swings & attacks too, not just casts | ✅ |
| 7 | MINOR | Bosses | Uptime examples: "Sunder/Expose Armor"; Misery omitted | Sunder & Expose are separate rows; Misery *is* a tracked `KEY_DEBUFF` | ✅ |
| 8 | MINOR | Execution | DPS Gaps: "**Per-player**, so roster-count… doesn't skew it" | Denominator is player-**boss** samples, not unique players | ✅ |
| 10 | MINOR | Overview | Card labeled **"Boss Kill Time"** (singular) | It's the **summed total** kill time across all shared bosses | ✅ |
| 11 | MINOR | Wipes | "avoidable = a named non-melee **killing hit**" | Classifier is the death-**window damage mix**, not just the killing blow | ✅ |
| 12 | MINOR | Trash | "**Clear Time**" | Summed **in-combat pull** time, not wall-clock elapsed | ✅ |

---

## Findings in detail

### 1 — `WRONG` · Prep · In-combat matrix advertises a column that doesn't exist

- **Location:** `templates/report.html:636` (Per-Player Consumables — In Combat hint)
- **Current text:** *"Consumables pressed **during** the fight: **P** combat potion · **HP** health · **MP** mana · **HS** healthstone."*
- **What the code does:** `inCombatMatrix()` defines its sub-columns as
  `const SUB=[["P","Combat Potion"],["MP","Mana Potion"],["HS","Healthstone"]]`
  (`report.html:348`) — three columns, no HP. The data side agrees: `fetch_report._incombat_casts`
  tracks only mana potions and healthstones; health potions are explicitly excluded (*"Health potions
  are not tracked (unused in TBC raids)"*, `references/wcl-api.md:75`, and the build docstring at
  `build_deepdive.py:796`).
- **Mismatch:** The hint names a fourth column ("HP health") that appears nowhere in the UI or the
  pipeline. A reader scans the matrix for an HP column that will never render. The order is wrong too
  (hint says P·HP·MP·HS; columns are P·MP·HS).
- **Fix applied:** dropped "HP health" → *"…**P** combat potion · **MP** mana · **HS** healthstone."*

### 4 — `WRONG` · Composition · Misery debuff value contradicts the rest of the codebase

- **Location:** `scripts/build_deepdive.py:160` (`PROVIDER_CHECKS`, rendered into the Composition
  "Provider Count & Coverage" table's *Why it matters* cell)
- **Current text:** *"+3% spell damage taken by boss, plus a mana battery for casters"*
- **What the code does:** The same file states the correct value twice elsewhere: the hit-modeling
  comment *"(Note: Misery is +5% spell DAMAGE, not hit.)"* (`build_deepdive.py:333-334`) and the
  Hit & Expertise tab's "NOT modeled" note. TBC's Misery applies **+5%** spell damage taken.
- **Mismatch:** "+3%" is simply wrong, and self-inconsistent — the codebase argues against itself.
- **Fix applied:** `+3%` → `+5%`.
- *Note:* the legitimate **+3%** references in this file are all Improved Faerie Fire (+3% spell
  **hit**, `build_deepdive.py:161,330,338`) and were left untouched.

### 2 & 3 — `MISLEADING` · Prep · "Prepared" rule hides the DPS battle-elixir exception

- **Location:** `templates/report.html:618` (Consumables Coverage hint) and `:629` (Per-Player
  Consumables — Prep hint)
- **Current text:** *"'Prepared' = a flask OR a full battle + guardian elixir pair"* (618) and
  *"'Prepared' = a flask or a battle + guardian pair, plus food"* (629)
- **What the code does:** `_cell_for()` (`build_deepdive.py:661-695`) sets the strict
  `consumed = flask or (battle>=1 and guardian>=1) or total_elixirs>=2`, then **relaxes it for DPS**:
  ```python
  # A DPS is prepared on throughput with just a battle elixir — guardian is optional for them.
  if role == "dps" and battle >= 1:
      consumed = True
  ```
  (`build_deepdive.py:691-693`). The function's own docstring spells out the intent: for a DPS only
  the battle (offensive) elixir affects throughput, so a DPS with a battle elixir and no guardian
  counts as prepared (and the matrix renders the missing guardian faint, not red).
- **Mismatch:** Both hints state a flask *or the full pair* is required, with no DPS carve-out. A
  raid leader checking a DPS who ran a battle elixir but no guardian sees ✓ — contradicting the stated
  rule. (The rule as written *is* correct for healers/tanks.)
- **Fix applied:** both hints now read *"a flask, a battle elixir (DPS), or a full battle + guardian
  pair (healer/tank)"*.

### 9 — `MISLEADING` · Optimize · "World #N {faction}" conflates two different leaderboards

- **Location:** `templates/report.html:1561` (`optBossBody` benchmark line)
- **Current text (rendered):** e.g. *"…— World #7 Horde Fire Mage on Al'ar"*
- **What the code does:** `fetch_worldbest._best_same_faction` (`fetch_worldbest.py:51-64`) walks the
  full **all-faction** `characterRankings` and returns the first entry matching our faction, tagged
  `globalRank = i + 1` — *"its 1-based GLOBAL rank in the full (all-faction) leaderboard"* (docstring,
  `fetch_worldbest.py:52-54`). So the player is the **best same-faction** parse, sitting at rank #7
  among **all** players of that spec.
- **Mismatch:** Printing "#7" immediately before "Horde" reads as *the 7th-best Horde player*. It's
  actually *the best Horde player, who ranks #7 overall across both factions*. The number and the
  faction word describe different leaderboards.
- **Fix applied:** → *"top {faction} {spec} {class} (World #{rank} overall)"* — the faction now
  qualifies "top", and the rank is explicitly tagged "overall".

### 5 — `STALE` · Prep · "Potion use isn't tracked" — but the same tab tracks it five ways

- **Location:** `templates/report.html:646` (Enchants & Weapon Oils hint)
- **Current text:** *"(Potion use isn't tracked in Classic logs.)"*
- **What the code does:** The Prep tab renders, above this line: the in-combat potion matrix
  (`P` column), the **Throughput Potions — By Spec** section, and the **Opener Potion — Prepot**
  section — driven by `potion_usage_by_spec()`, `potion_gap()`, and `prepot_timing()` in
  `build_deepdive.py`. The Prep matrix's `F` column also tracks flasks.
- **Mismatch:** Stale parenthetical — almost certainly true before potion tracking was added, never
  removed. It now contradicts five sibling views.
- **Fix applied:** → *"(This section covers enchants and weapon oils only; potion use is tracked in
  the matrices above.)"*

### 6 — `MINOR` · Execution · "active-casting time" undersells what Activity measures *(two instances)*

- **Location:** `templates/report.html:775` (Output Quality → Activity card) **and** `:1069`
  (Activity by Spec, experimental) — both phrased identically.
- **Current text:** *"Activity = active-casting time ÷ fight duration…"*
- **What the code does:** `activity_pct()` reads WCL's `DamageDone.activeTime`
  (`build_deepdive.py:1365-1371`), and `tier_activity_gap`/`activity_by_spec` (~`:1433-1450`) do the
  same per spec. `activeTime` is the share of the fight a player spent in **any** damage action —
  melee swings and special attacks included, not only spell GCDs. A rogue's or warrior's score has
  nothing to do with casting.
- **Mismatch:** "active-casting time" implies spell GCDs only, mislabeling melee specs' activity.
- **Fix applied (both):** → *"active GCD time (casts, swings, or attacks) ÷ fight duration"*.

### 7 — `MINOR` · Bosses · uptime "how to read" omits Misery and conflates two debuff rows

- **Location:** `templates/report.html:854` (Per-Boss Breakdown reading guide)
- **Current text:** *"…key debuffs (Curse of the Elements, Faerie Fire, Sunder/Expose Armor) should
  sit near 100%…"*
- **What the code does:** `KEY_DEBUFFS` (`build_deepdive.py:984-985`) is
  `["Sunder Armor", "Expose Armor", "Curse of the Elements", "Faerie Fire", "Misery",
  "Judgement of Wisdom", …]` — Sunder and Expose are **separate** named rows, and **Misery** is
  tracked but absent from the example list.
- **Mismatch:** "Sunder/Expose Armor" reads as one row (they're two); a reader can't tell why a Misery
  row appears when the guide never names it.
- **Fix applied:** → *"(Curse of the Elements, Misery, Faerie Fire, Sunder Armor, Expose Armor)"*.

### 8 — `MINOR` · Execution · DPS Gaps "per-player" claim is imprecise about its denominator

- **Location:** `templates/report.html:1040` (DPS Gaps — By Spec hint)
- **Current text:** *"…**Per-player**, so roster-count differences don't skew it."*
- **What the code does:** `tier_spec_gap` (`build_deepdive.py:1692-1712`) pools every `(player, boss)`
  DPS sample per spec into a flat list and averages it: `o_avg = round(sum(o_d)/len(o_d))`. A spec
  with 2 players over 5 bosses contributes 10 samples; the denominator is player-**boss** pairs.
- **Mismatch:** It *is* a mean (so raw roster size doesn't inflate a *total*), but "per-player" is the
  wrong grain — it's per player-boss sample, and uneven boss attendance still weights the average.
- **Fix applied:** → *"Averaged per player-boss sample, so roster size doesn't inflate it."*

### 10 — `MINOR` · Overview · "Boss Kill Time" is an aggregate, labeled like a single fight

- **Location:** `templates/report.html:477` (Raid Summary card)
- **Current text:** card label *"Boss Kill Time"* over an `m:ss` value.
- **What the code does:** `oursDurationMs = ssum([b["ours"]["durationMs"] for b in bosses])`
  (`build_deepdive.py:3584`) — the **sum** of every shared boss's kill duration.
- **Mismatch:** Singular "Boss Kill Time" next to one `m:ss` reads like one boss's kill. The card's
  own follow-up ("Per-fight kill time … live on the Bosses tab") confirms this is the aggregate.
- **Fix applied:** → *"Total Boss Kill Time"*.

### 11 — `MINOR` · Wipes · "avoidable" footnote oversimplifies the classifier

- **Location:** `templates/report.html:1892` (Likely cause footnote)
- **Current text:** *"'avoidable' = a named non-melee killing hit."*
- **What the code does:** `_classify_wipe_death` (`build_deepdive.py:~3395-3415`) buckets a death as
  "mechanic" when melee is **< 50%** of the death-window damage **and** a named non-melee ability is
  present; the displayed label is the killing blow if non-melee, else the top named ability. It's a
  window-damage-mix test, not strictly "the killing blow was named non-melee" (a Melee killing blow
  can still bucket as mechanic if a named ability dominated the window).
- **Mismatch:** The footnote reduces a damage-composition heuristic to one event.
- **Fix applied:** → *"'avoidable' = a death window dominated by named, non-melee damage."*

### 12 — `MINOR` · Trash · "Clear Time" is in-combat pull time, not wall-clock

- **Location:** `templates/report.html:1653` (hint) / `:1656` (card label)
- **Current text:** card *"Trash Clear Time"*; hint *"clear time is a rough proxy"*.
- **What the code does:** `clearMs` is the sum of trash segment durations (`endTime − startTime`) —
  in-combat pull time only, excluding walking/regen between pulls (`_trash_glance`,
  `build_deepdive.py:~2774`).
- **Mismatch:** "Clear Time" implies elapsed time to clear; the value is summed combat time. The
  existing "rough proxy" caveat was about route/skip differences, not the in-combat-only nature.
- **Fix applied:** hint now reads *"clear time (summed in-combat pull time, not wall-clock) is a
  rough proxy"*.

---

## Verified clean (checked, no mismatch)

These explanations were traced to their producers and **match** the code — recorded so the fan-out is
demonstrably complete, not just sampled:

- **Overview:** Biggest Gaps (`gapsScorecard`, ranked by distance), What You're Doing Well
  (`didWell`, by margin), Avg Raid Parse (higher-better), Total Deaths (+ conditional "trash + all
  pulls" gate on `nightWideDeaths`), Total Wipes (lower-better), **Parse Spread** (median higher-better,
  floor `<25` lower-better, lowest-parsing specs at spec grain).
- **Composition:** every other provider impact string (Improved Faerie Fire +3% spell hit, etc.) and
  the Hit & Expertise tab's hit-source attribution.
- **Prep:** the F/B/G/Fd matrix legend, Throughput Potions, Prepot timing, enchant/oil/Windfury
  coverage (aside from the four fixes above).
- **Execution:** Overheal (healing on full HP), Damage Taken (tank-excluded, per-second toggle), the
  DPS-by-spec mirrored bars (aside from the wording fix).
- **Bosses:** uptime = time-coverage not player-count, higher-better/red-trails, short-CD caveat
  (aside from the example-list fix).
- **Wipes:** Closest Attempt (lowest `fightPercentage` = boss HP remaining), "the wall" (last-phase
  mode + median %), trend viz (`prog = 100 − HP-remaining`), "what ends attempts" (first death's
  killing blow ×count), mechanics-vs-sustained verdict thresholds (`m≥2s` / `s≥2m`), Wipe Recovery
  (wall-clock dead-time between pulls, lower-better, first-party caveat).
- **Optimize:** cast-mix = share of casts per ability, "within 5 points on every ability" collapse
  (`max|diff| ≤ 5.0`), form/role-aware exclusion (Feral bear vs cat), neutral Δ (aside from the rank
  fix).
- **Trash:** Trash Pulls = segment count, deaths lower-better, What's Killing Us (killing blow +
  source mob), Chain-Pulling (`bigThreshold=10`), Deaths by Pull Size (rate per bucket, lower-better),
  Kill Order same-pack matches & pairwise priority, Crowd Control by mob (aside from the two fixes
  above).

---

## Method & evidence

Two independent fan-outs read every line of `templates/report.html` (1944 lines) and the producing
Python, then cross-referenced each claim against the function/variable that drives it. Every finding
above cites a `file:line`. After the fixes, the report was **re-rendered from cached data**
(`build_deepdive.py` directly on `data/pkHqfrBbhQK9GP1a` vs `data/BxZPrhXYDfL1VKm8` — no API call) and
the output was grepped to confirm all 13 corrected strings are present and all 7 buggy strings are
gone, with the embedded JS still rendering a complete 342 KB report.
