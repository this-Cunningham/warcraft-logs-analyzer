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
