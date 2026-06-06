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
