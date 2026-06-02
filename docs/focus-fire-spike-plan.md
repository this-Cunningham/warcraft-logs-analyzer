# Focus-fire / target-switch latency — spike plan

**Status (updated 2026-06-02):** **M1 (focus concentration) is BUILT** — shipped as the "Target Focus —
Multi-Target Fights" view (`focus_view` → `focusFireView`), computed for *zero extra API cost* by binning
the Timeline's existing DamageDone pull by `targetID` (see `_binned_curves`). **M2 (switch-latency to a new
add) and named-add labels remain unbuilt** — the rest of this doc is the design for those. This is
candidate **#3** from the [GraphQL audit](graphql-audit.md) (the flagship time-resolved idea, also TODO #1).

## The gap it reveals

On **multi-target** fights, is the raid actually focusing the right thing, and how fast does it react to
a new add? The thing we want the report to be able to say:

> *"Your melee took 24s to switch to the Tainted Elemental; the benchmark switched in 6s."*
> *"Your raid's damage was split across two targets for the first 30s; the benchmark concentrated 85%."*

This is a behavior the report can't see today — every current view is a fight-total aggregate.

## Why it's a spike (the honesty + cost tension)

1. **No hardcoded "correct target."** The soul forbids a blame machine and forbids false precision.
   We must measure *boss-agnostic* quantities — **focus concentration** and **switch latency to a
   newly-engaged enemy** — not "you should have hit X." Only where we deliberately encode a TBC add
   priority do we label it explicitly as our assumption.
2. **Events are the only source, and they're the expensive modality.** `graph()` can't do per-target.
   So this is the one candidate that meaningfully draws on the event budget — hence cache-to-disk and
   filter-server-side are mandatory, and we restrict to multi-target bosses, the kill only.

## Data — verified reachable (audit E3)

- `events(dataType:DamageDone, fightIDs:[fid], …)` carries **`targetID`** on every event, plus
  **`targetInstance`** to tell apart multiple copies of the same add. (Confirmed populated: all Solarian
  damage events carried `targetID:175`.)
- `masterData.actors(type:"NPC")` maps every enemy `id → name` (we already fetch this for Trash; extend
  to boss fights). Filter the stale `zzOLD…` totem actors (TODO note).
- **Not reachable (don't design around it):** per-actor x/y positions — dead via the public API
  (TODO, exhaustively verified). So this is a *targeting* insight, never a *spread/stack* one.

## Metric design (two, ranked by cleanliness)

**M1 — Focus concentration (the safe flagship).** Bin the fight into the same N buckets the Timeline
uses. In each bucket, of all raid damage to **enemies**, compute the **concentration** = share on the
single most-damaged enemy (or a Herfindahl index Σ(share²) across enemies — 1.0 = all on one target,
lower = split). Report the fight-average ours vs benchmark, and overlay the concentration curve on the
existing per-boss Timeline. *Boss-agnostic, no "correct target," clean better/worse on fights where
focusing matters.* Only shown on multi-target fights.

**M2 — Switch latency to a new enemy (needs a guard).** Detect a new add's appearance = first event
whose `(targetID,targetInstance)` hasn't been seen this fight. Switch latency = time from that first
appearance to the first **significant** raid damage on it (e.g. ≥X% of raid DPS for ≥1 bucket). Report
per side: "median time to engage a new add." *Guard:* this measures reaction to *any* new enemy; calling
one a "priority" add requires an encoded TBC priority list, which we either omit or label as our
assumption. Pairs with the add-handling-speed idea (TODO #6: spawn→death duration).

## Cost plan (stay well under 3600/hr)

- **Only multi-target bosses, only the kill.** Of the test shared set: Solarian (adds), Kael'thas
  (weapons/advisors), Al'ar P2 — yes; **Void Reaver — single-target, skip.** Detect via distinct enemy
  `targetID`s with non-trivial damage (or `enemyNPCs` length).
- **`filterExpression`** server-side (`type="damage"`, hostile target) to cut volume before it leaves WCL.
- **Page with `limit:10000`** (the Timeline already does this; most fights are one page).
- **Cache to disk** (`events-dmg-<enc>.json` under `data/<code>/`) — a finished fight's events never change.
- Estimated ~10–20 pts/boss/side; ~3 multi-target bosses × 2 sides ≈ 60–120 pts for a full comparison —
  comparable to the Timeline's event cost, well under the cap.

## Where it lives in the report

- A per-boss **"Focus"** sub-tab under Execution (next to Timeline), present **only on multi-target
  bosses** — the concentration curve (M1) overlaid ours vs benchmark, plus the switch-latency line (M2)
  as a caption. Reuses the `tlChart`/`timelineChart` SVG plumbing the Timeline established.
- Optionally a tier-wide **"Target Focus"** one-liner in the Execution raid-wide stack (avg concentration
  gap across multi-target bosses), feeding the Biggest Gaps scorecard if the gap is large.

## Implementation phases

1. **Spike (1 boss, ~1 hour of points):** fetch DamageDone events for Kael'thas (ours) only; map
   `targetID→name` via masterData; compute the concentration curve + a switch-latency probe on the
   weapons/advisors. **Decision gate:** is the signal legible and does cost match the estimate? Write the
   findings back here. (Mirrors how the Timeline was spiked first.)
2. **Generalize fetch:** add a multi-target-boss detector + `events-dmg-<enc>.json` to `fetch_report.py`
   (shared bosses only), with `filterExpression` + disk cache. Extend `masterData` to boss-fight NPCs.
3. **Build + render:** `focus_concentration()` / `switch_latency()` in build_deepdive → a `focus` block
   per boss; the **Focus** sub-tab in `report.html`; graceful when the data/file is absent (single-target
   bosses and older data folders just don't show the tab).
4. **Honesty pass:** confirm no hardcoded priority leaks in unlabeled; single-target fights excluded;
   concentration framed as "share on the most-focused target," not "share on the correct target."

## Open questions for you

- **Encode TBC add priorities** (e.g. Solarian's Wrath adds, Kael's weapons order) to enable a labeled
  "priority switch latency", or keep it strictly boss-agnostic (concentration + any-new-add latency)?
  *Recommendation: ship M1 boss-agnostic first; add labeled priorities only per-boss, clearly flagged.*
- **Bucket vs event-level** for concentration — reuse the Timeline's N-bucket binning (cheaper, aligns
  visually) or compute at event resolution (finer, more code)? *Recommendation: reuse the buckets.*
- Is this worth prioritizing over the **threat / early-aggro** spike (audit #1), which is cheaper
  (`table(Threat)`, no event pull) and also a new modality? *They're complementary; threat is the cheaper
  first build if we want a quick new-modality win.*
