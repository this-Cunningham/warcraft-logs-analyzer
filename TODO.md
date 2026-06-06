# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> change how a raid leader runs next week — and can they read it and trust it in seconds?

---

## TODO: Positioning snapshots — fetch add positions + per-actor facing

> the remaining half of the formation-snapshot reframe — adds shown too, and the direction each is facing

**Status of the reframe so far:** the phase-anchored snapshot half shipped — the Positioning sub-tab now
shows the raid's *settled formation at the opening + each phase* (ours vs benchmark per moment) instead of
one whole-fight median smear, with a graceful fallback to the single map on single-phase bosses. What's
left is the half the **fetch pipeline can't yet feed**: the cached `positions-<enc>.json` carries only
roster actor x/y bins + the single boss anchor track — **no `facing` field and no non-boss hostile (add)
actors**. So facing arrows and add dots can't be drawn without first capturing that data.

**Investigation — DONE (verified live against report `pkHqfrBbhQK9GP1a`, 2026-06-06). Both pieces are
already in the events stream we fetch; no new query type, only plumbing + a re-fetch:**

- **Per-actor facing — available NOW, not captured.** Every resourced event (`includeResources:true`)
  already carries a `facing` field right next to `x`/`y` (`mapID` too). It's **centiradians** (radians ×
  100); decode `heading = -facing / 100.0` (confirmed in the positioning skill's `coordinate-system.md`).
  `_page_resourced` in `fetch_report.py` simply drops it on the floor — it yields `(ts, aid, x, y, tid,
  gid)` and never reads `e["facing"]`. **Fix:** yield `facing` too, and store a per-bin median *heading*
  per actor in `positions-<enc>.json`.
- **Add (non-boss hostile) positions — already in the sweep, just discarded.** The boss track is built by
  the `DamageDone` resourced sweep, keeping only the event whose resourced actor *is the boss* (`targetID`
  pinned to the boss id). Dropping that restriction surfaces **every enemy NPC as a resourced actor** —
  verified on the Solarian fight, the same sweep returned the boss (`High Astromancer Solarian`, 1598
  position samples) **and** the add (`Solarium Agent`, 322 samples), each with `facing`. **Fix:** in
  `_fetch_positions`, bucket every resourced **NPC** actor (id → name via `masterData.actors type:NPC`),
  store each non-boss NPC as its own track (bins + facing) in `positions-<enc>.json` under e.g. `adds`.
  Cost note: removing `targetID:boss` widens the sweep (more pages); cap pages or add a dedicated enemy
  sweep if it gets heavy.

**Then build (render):** add facing arrows to player + add dots in `_formation_at`/`_formation_panel`
(`positioning.py`) — **only when `facing` is present** for that actor at that moment, never inferred — and
draw adds as distinct shapes/colours (add facing = cleave/cone-threat arcs). Extend the snapshot caption.
Requires regenerating the cached `positions-<enc>.json` (a live re-fetch) before the render half can show.

---

## TODO: Buff & Debuff Coverage Gaps — zoom on enemy targets with debuffs

> BUFF & DEBUFF COVERAGE GAPS zoom on enemy targets with debuffs and compare across raids

**Current grain:** `tier_uptime_gap()` in `build_deepdive.py` pulls from WCL's aggregate Buffs/Debuffs table
(`_auras(rep, "debuffs")`), which returns per-name uptime **pooled across all enemies on all shared bosses**.
The renderer (`tierUptimeGapView(d)` in `report.html`) shows mirrored bars sorted by deficit — ours vs theirs
for each buff/debuff name. No enemy target breakdown.

**Proposed deeper grain:** per-target debuff attribution — which specific enemy (main boss vs named adds, e.g.
Void Reaver vs pylons, Solarian vs Solarium Agents) each key debuff lands on, ours vs theirs, so the leader
can see whether a gap is a boss-coverage problem or an add-coverage problem. *"Sunder Armor is 90% uptime
overall but only 15% on the main boss — the off-tank's coverage is good, the main-tank assignment isn't"* is
the lever. The bare aggregate can't name that.

**Leader decision this serves:** *"Is the debuff gap an assignment problem (wrong enemy) or a throughput
problem (not enough application)?"* — a different fix each way.

**Magnitude gate:** only worth the complexity if at least one shared boss has named adds that absorb a
meaningful share of debuffs at different rates than the main boss. Verify on a real report before building.

**Feasibility flag:** the current pipeline reads WCL's Buffs/Debuffs **summary table** — no `targetID`.
Per-target debuff uptime likely requires switching to a per-target Buffs query (WCL supports filtering by
`targetID` in the Buffs table, but it's a separate query per target) or event-level data. Cost: N queries per
boss per enemy NPC of interest. Assess whether the WCL API exposes a single multi-target Buffs call before
building.

**Judge as consumer first:** view the rendered Buff & Debuff Coverage Gaps section in a live report before
implementing — confirm the overall uptime gap is large enough that knowing *which target* the debuff is
missing from would meaningfully change the assignment. If the section already reads clearly and the gap is
explained by a single target, the zoom earns its place. If the aggregate gap is trivially small, re-rate
downward.

---

## TODO: Cooldown & Trinket Usage — per-cooldown mirror bars, class label above group

> COOLDOWN & TRINKET USAGE — BY SPEC — thanks for zooming on the cooldown data , just make a horizontal mirror bar comparison for each cooldown instead if shoving a bunch of text, and cleanly separate with class in center and above the classes bars

**What to change:** the current `cdUsageView()` renderer ships per-cooldown text rows beneath each trailing
spec (`r.byAbility` list — name, ours/min, theirs/min, Δ). Replace that text dump with **horizontal mirror
bars per cooldown** (ours left ← | → theirs right, same mirrored-bar idiom the rest of the section uses)
so the deficit reads at a glance instead of parsing numbers. Each bar row is one cooldown; the Δ is encoded
in bar length, not typed out.

**Layout:** group the cooldown bars by class, with the **class name centered above its group** as a separator
— not inline in the spec row. Spec rows become the anchor; their cooldown bars nest beneath them, visually
separated from the next class by the centered class label.

**Legibility rationale:** the soul's *prefer the plain number to the clever chart* cuts the other way here —
the current text output is *less* readable than a bar because the reader must mentally subtract ours/min from
theirs/min for every row. A bar encodes the gap pre-attentively. This is a floor fix, not decoration.

**Data is already present:** `byAbility` is built in `cd_usage_pool()` / `tier_cd_usage()` in
`build_deepdive.py` and shipped in the payload. Only the renderer (`cdUsageView()` in `report.html`) needs to
change — no builder work required.

**Scope:** renderer-only change. Match the existing `.dval`/`.lbar`/`.rbar` mirror-bar CSS already used in
the section; extend with a `.cdclass-label` separator row if needed.

---

## TODO: Mirror bars — drop side value columns, show Δ with units in center

> for our horizontal mirror bars, we currently have: val1 - bar1 - label and other info - bar2 - val2 — (sometimes optional context on rightmost column (keep))
>
> Lets get rid of the val1 and val2 on the sides and just put the difference in val with proper units in center under label

**Current layout:** `val1 | bar← | LABEL (Δ) | →bar | val2 | (optional ctx)`
The outer `dval.lo` / `dval.ro` columns (46px each) hold the raw ours/theirs values.

**New layout:** `bar← | LABEL · Δval+units | →bar | (optional ctx)`
Drop the two side value divs and their grid columns entirely. The center `.dmid` block
already renders a `.delta` child — extend it to also show the signed difference with
proper units (e.g. `−2.3k DPS`, `+12%`, `−8s`) directly under the label, formatted the
same way as the bar scale. The `Δ` carries the sign; units make it self-explanatory
without the raw values.

**CSS change:** `.ugrid` columns shrink from 5 to 3: `1fr · <label-width> · 1fr` (plus
optional `.dctx` for `ugridc`). `.dgrid` same treatment. Bars get the full space the
outer columns freed up → signal reads more clearly at smaller widths. Remove `.dval`
CSS rules; the `.delta` inside `.dmid` already handles colour (good/bad/flat/warn).

**Scope:** renderer + CSS only. Pairs naturally with the `mirrorGrid()` refactor TODO
already in this file — best done together so the column-drop is implemented once in the
extracted function rather than at 14 call-sites independently. Do **not** remove the
optional `.dctx` context column (rightmost, `ugridc` variant).

---

## TODO: Early Aggro — verify Feral Druid bear-tank false positive in Threat Pulls

> possible bug — EARLY AGGRO — THREAT PULLS — make sure you arent counting tanks in this calculation, i see feral druid and i immediately think you are counting tanks accidentally

**Short answer — not a blanket bug, but a real edge case exists:**

`threat_pulls()` (`build_deepdive.py:1340`) already excludes players whose `role_map` entry is `"tank"`:
`if nm not in role_map or role_map.get(nm) == "tank": continue`. A dedicated bear tank would be skipped.

**The edge case:** `role_map` is built from `primary_spec_map` — majority role across all fights in the
report. A Feral Druid who cat-DPS'd most fights but bear-tanked one would have `role_map = "dps"` and be
INCLUDED in threat-pull counting for the fight where they were actually tanking. Result: a false positive —
they "pulled aggro" from themselves.

**The fix pattern already exists:** `_druid_form(abil)` (`build_deepdive.py:1888`) distinguishes bear vs cat
from cast mix on a per-fight basis (Lacerate/Maul/Swipe = bear; Shred/Rake/Mangle(Cat) = cat). It's used in
the Optimize section to avoid phantom rotation gaps but NOT called in `threat_pulls()`. Applying it there
would catch the "dps-classified bear" case: if their cast mix on that fight is bear-dominant, skip them.

**Verify first:** check a real report where Feral Druid appears in Threat Pulls — confirm whether the named
player is cat-DPS (correct inclusion) or a bear-tanking Feral classified as dps by role_map (false positive).
If the former, no bug. If the latter, wire `_druid_form()` into the non-tank check inside `threat_pulls()`.

---

## TODO: Ghost Run — clip dashed projection line at the ghost kill marker

> for ghost run — what dying cost you — make the green dashed line stop where the vertical green ghost line is (and it should update when it changes from selecting/deselecting dead players)

**What to fix:** in `tlChart()` (`report.html:1326`), the dashed ghost DPS line is drawn for the full
`gDur` duration — it runs past the vertical "ghost kill" marker at `ghost.killSec`. The line should end
exactly at `killSec`: a projection beyond the projected kill is meaningless and clutters the read.

**Fix:** when building the dashed path, filter out points where `i/(n-1)*gDur > ghost.killSec` — i.e. only
draw points up to and including the bucket that crosses `killSec`. The filled gap polygon (lines 1323-1325)
should be clipped the same way so the green shaded area also stops at the kill line.

**Already updates on toggle:** `ghostInner()` re-renders the whole chart block on every death toggle, so
clipping by the recomputed `killSec` will update automatically — no additional wiring needed.

**Scope:** renderer-only, one-line path filter in `tlChart()`. No builder changes.

---

## TODO: BUG — mobile bosses hide ALL positioning; should snapshot their plant windows

> No why are we hiding positioning if labelled mobile, "BUG", it is still possible for mobile bosses to plant and for us to find relatively stable positioning states

**The bug:** `boss_positioning()` (`positioning.py:468-474`) classifies a boss by **whole-fight** boss travel
(`boss_travel_yd`) and bails entirely when `bclass == "mobile"`. Al'ar's flight between platforms smears to
~1448yd, so it's tagged mobile and gets **no Positioning tab at all** — even though Al'ar (and other "mobile"
bosses) repeatedly **plant** on a platform, and during those windows the raid's formation around the planted
boss is exactly as meaningful as on any stationary boss. Whole-fight travel is the wrong grain: a boss that
teleports/flies between stable stands is mobile *between* plants but stationary *during* them.

**The fix — per-window classification, not whole-fight:** the phase-anchored snapshot machinery already
exists and already solves this — it's just gated out by the early `return None`. `_snapshot_windows()` +
`_formation_at()` (`positioning.py`) detect settled windows and render a per-moment formation map. The change:

1. **Don't bail on mobile.** Instead of returning None for `bclass == "mobile"`, detect the **stable
   sub-windows** within the fight — bins where the boss anchor is locally stationary (low travel over a
   short rolling window), i.e. the plant phases. Phase boundaries (`o_phases`/`t_phases`) are a strong prior
   for where plants begin.
2. **Anchor each snapshot's frame to that window's planted boss position**, not a whole-fight frame (which is
   what makes the mobile smear meaningless). Per-plant frame = relative geometry is honest again.
3. **Render only the planted windows** as phase-anchored snapshots; skip the flight gaps. If no stable window
   is found (truly always-moving boss), fall back to the current suppression with the honest one-liner.

**Why it matters (soul):** Al'ar is a real shared boss; hiding positioning entirely is a coverage hole, not a
clean omission. Plant-phase formation surfaces the same lever as any stationary boss (spread/stack vs the
benchmark when it actually counts). Magnitude gate: only worth it if the plant windows hold enough position
samples to compute a stable spread radius — verify on the live Al'ar fight before building.

**Verify the data:** confirm the cached `positions-<enc>.json` for Al'ar has enough per-bin boss anchor +
roster samples *during* the plant windows to compute spread (it should — the suppression happens after fetch,
on classification, so the data is already there).

---

## TODO: BUG — Positioning snapshots clip outliers and use whole-fight frame instead of window frame

> bug — you are clipping the positioning viz, and also reframing them, i need the same perspective for both raids for all positioning viz snapshots with no clamping outliers

**Two bugs in `_robust_frame` (`positioning.py:302`) and `_formation_at` / `_formation_panel`:**

**Bug 1 — 3rd/97th-percentile clipping:** `_robust_frame` computes the bounding box as the 3rd–97th
percentile of actor median positions (`pct(xs, 0.03)` / `pct(xs, 0.97)`). Any actor whose median position
falls outside that range has their dot clamped to the border and shown hollow. A leader sees a fake
formation: actors who were genuinely far out are pinned to the edge, misrepresenting the spread. **Fix:**
use the full min–max range (or at most 1st–99th with a large roster — never 3rd/97th). Every actor is shown
where they actually were; if the frame gets wide, that's the honest read.

**Bug 2 — frame built from whole-fight medians, not window positions:** `_robust_frame` collects each
actor's `_actor_median(a)` (median over the ENTIRE fight), then derives the shared bounding box from those
whole-fight medians. Phase-anchored snapshots (`_formation_at`) then use that same frame even though a
snapshot represents a specific 5–10s window where the raid may have been positioned very differently from
their whole-fight average. An actor who camped the far side of the room during Phase 1 but stood on the boss
median for the rest of the fight will have a whole-fight median near center — and their Phase 1 dot will
appear outside the frame and get clamped, or the frame will be too tight to show Phase 2's spread. **Fix:**
for snapshot panels, derive the frame from the WINDOW positions (the actual actor positions in bins [lo, hi)),
not from whole-fight medians. The frame expands to show where everyone actually stood in that moment.

**Shared frame across both raids must be preserved:** the shared frame (both sides combined into one box) is
correct and must stay — the fix is in the DATA used to build the shared frame (window positions, not
whole-fight medians), not in separating ours vs theirs into independent frames. A raid leader comparing ours
vs benchmark must see both at the same scale and origin.

**Where to fix:**
- `positioning.py:302` — `_robust_frame`: remove 3rd/97th percentile; use full min/max (or pass the actual
  window-bin positions rather than whole-fight medians for snapshot contexts)
- `positioning.py:417` — `_formation_at`: compute the frame inside this function from the window-bin
  positions `[lo:hi)` across both sides (pass both sides' pos objects, not a pre-baked frame), then pass
  that window frame into `_projector`
- `positioning.py:505` — call site in `boss_positioning`: the single-panel fallback (`_formation_panel`) can
  keep a whole-fight frame since it shows the whole fight, but the phase-snapshot path must compute per-window
  frames (or one combined window frame across all shown windows)

---

## TODO: Refactor — extract mirrorGrid() as a single reusable mirror-bar function

> is it possible to make horizontal mirror bar viz a reusable function that can be configured or is this bad idea

**Yes, it's a good idea.** The horizontal mirror-bar idiom (ours ← label → theirs, with a delta tag and
optional context column) appears **14 times** across `report.html` as hand-rolled boilerplate — same 5-column
div sequence, same `.dbarL`/`.dbarR`/`.dval`/`.dmid` CSS, different formatters and delta functions per site.
Two partial extractions (`topSources`, `uptimeCompare`) already exist but don't share a common core. A recent
centering bug had to be fixed in 4 simultaneous places; that's the maintenance signal.

**Proposed abstraction — one JS function, param-configured:**

```js
mirrorGrid(rows, {label, grid, rowFn, oTitle, tTitle})
```

- `rows` — array of data objects
- `label` — center column header text
- `grid` — `'ugrid'` (default) | `'dgrid'` | `'ugrid ugridc'` (with context column)
- `oTitle` / `tTitle` — left/right header labels (default: `DATA.ours.title` / `DATA.theirs.title`)
- `rowFn(r, w)` — caller-supplied function: takes one row + a `w(v)` bar-width calculator, returns the
  5 (or 6 with `.dctx`) column divs as a string. Caller controls formatters, delta class, sub-rows.

The `w(v)` calculator is derived inside `mirrorGrid` from `max(all rows' ours + theirs values)`. Sub-rows
(the CD `byAbility` rows, threat-pull `bySpec` sub-rows) are returned by `rowFn` as additional divs spanning
all columns — the grid allows that naturally.

**What this unblocks:** the CD mirror-bars TODO (per-cooldown rows per class) and the debuff-per-target zoom
both need new mirror-bar instances. Building them with `mirrorGrid` instead of copy-pasting the 5-column
boilerplate keeps the codebase consistent and makes future layout changes (column widths, delta styling, media
breakpoints) a one-line fix.

**Scope:** `report.html` only — no builder changes. Replace existing boilerplate call-sites incrementally,
starting with the two that need new sub-row logic (CD Usage, threat pulls) since they benefit most from the
abstraction. The existing `topSources` and `uptimeCompare` functions can be re-expressed as thin wrappers
around `mirrorGrid` or left as-is — don't refactor them for its own sake, only when touching them for
another reason.

---

## TODO: BUG — CD & Trinket Usage breakdown numbers don't add up to the spec total

> bug COOLDOWN & TRINKET USAGE — BY SPEC, it seems the breakdown numbers dont add up to the overall number?

**The bug:** in the CD & Trinket Usage section, the per-cooldown sub-rows (`byAbility` entries — each ability's
ours/min and theirs/min) do not sum to the spec-level activation rate shown in the anchor row above them. A
leader comparing "Paladin total" to "Holy Light + Divine Shield + ..." can see the numbers don't reconcile,
which breaks trust in both.

**Likely cause:** `cd_usage_pool()` in `build_deepdive.py` builds the spec total (`r.ours`, `r.theirs`) and
the `byAbility` list in separate passes — or the spec total counts all tracked CD activations for that spec
combined (including CDs that only appear in one of the two raids), while `byAbility` is filtered to a subset
(e.g. only CDs present in both raids, or only trailing ones). If the total includes abilities not in
`byAbility`, or the two use different fight-length normalizations, the numbers will never reconcile.

**Fix:** verify whether `r.ours`/`r.theirs` at the spec level is derived as the sum of `byAbility` values or
computed independently in the builder. If independently, either (a) make the spec total *exactly* the sum of
the listed sub-rows, or (b) clearly label what each level represents (e.g. "all tracked CDs" vs "CDs active
in both raids") so a leader can read it without suspecting the math is wrong.

**Soul floor:** this is an **accuracy** violation — the product's non-negotiable first floor. A discrepancy a
leader can't reconcile makes the whole section untrustworthy. Fix before shipping further CD improvements.
