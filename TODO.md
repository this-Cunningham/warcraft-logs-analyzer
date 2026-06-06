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

**The data gap to close (investigation in progress):**

- **Per-actor facing** — WCL's position/`facing` exposure. Determine whether the v2 API surfaces facing
  (centiradian-encoded; see the positioning skill's `coordinate-system.md`) for players AND adds, via which
  query (the events/`graph` position stream vs the table we use), and at what extra fetch cost.
- **Add (non-boss hostile) positions** — today `fetch_report._fetch_positions` records only the roster +
  the boss. Find how to enumerate the encounter's named adds (`masterData` NPCs / `enemyNPCs`) and pull
  their position tracks into `positions-<enc>.json` as distinct actors, so the snapshot can draw them as
  their own shapes/colours with facing arrows (add facing = cleave/cone-threat arcs).

**Then build:** once the data is captured, add facing arrows (only when `facing` is present for that actor
at that moment — never inferred/interpolated) and add markers to `_formation_at` in `positioning.py`, and
extend the snapshot caption to cover them.
