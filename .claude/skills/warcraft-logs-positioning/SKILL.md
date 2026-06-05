---
name: warcraft-logs-positioning
description: >-
  Extract and render per-actor POSITIONAL data (x/y/facing/HP) from Warcraft
  Logs reports (verified on TBC Classic / Anniversary) — player & boss positions,
  movement paths, raid spread/stacking, melee-range & uptime, "who stood in the
  bad," and faithful top-down map plots of a fight (single or side-by-side
  comparison). Use whenever the user asks where players stood, about spacing /
  spread / clumping, to visualize or plot positions, draw a fight map, compare
  two raids' positioning, or analyze movement. Reuses the warcraft-logs-analyzer
  skill's API client (`lib.invoke_query`).
---

# Warcraft Logs Positioning

Per-actor positions **are** available from the public client-credentials API — the
one requirement is the **`includeResources: true`** flag on `events` (default is
`false`; omitting it is why positions were once wrongly thought unavailable).
Everything here was verified live 2026-06-05 on TBC report `pkHqfrBbhQK9GP1a`.

This skill is **knowledge + recipes**, not a pipeline. For the API client, reuse the
sibling skill:

```python
import sys, os
sys.path.insert(0, os.path.join(REPO, ".claude/skills/warcraft-logs-analyzer/scripts"))
from lib import invoke_query   # client-credentials, retries, rate-limit aware
```

## The one fact that unlocks it

```graphql
events(fightIDs:[N], dataType:DamageTaken, includeResources:true, limit:10000){ data nextPageTimestamp }
```

Every *resourced* event then carries `x, y, facing, mapID, hitPoints/maxHitPoints`
and a **`resourceActor`** index telling you **whose** position it is
(`1`=source, `2`=target — Blizzard logs resources for **one actor per event**).
See [references/data-access.md](references/data-access.md).

## References (read the one you need)

- **[data-access.md](references/data-access.md)** — how to pull positions: the
  `includeResources` flag, `resourceActor` attribution rule, fields & their
  reliability, reconstructing a player's vs the boss's path, roster/role lookup.
- **[api-cost.md](references/api-cost.md)** — point cost (~2 pts/request flat,
  resources are free); an 8-boss × 2-side fetch is ~1% of the hourly budget. The
  real cost is payload/parse, not points.
- **[coordinate-system.md](references/coordinate-system.md)** — what WCL's x/y
  actually are, the confirmed WCL-`mapID` = Blizzard-UiMap linkage, world bounds,
  the world→map transform math, and how to calibrate to real yards.
- **[map-assets.md](references/map-assets.md)** — there is **no map image in the
  API**; you don't need one; and if you want one, where to get the texture +
  calibration bounds (wago.tools / CASC).
- **[rendering.md](references/rendering.md)** — building a faithful plot: equal
  aspect, framing strategies, aggregation pitfalls (median collapses a stack!),
  side-by-side comparison, validation against a stationary boss, stdlib SVG.

## Quickstart: a faithful plot in ~40 lines

1. Find the boss NPC actor id (`masterData.actors(type:"NPC")`, match by name — it
   differs per report) and the kill `fightID`.
2. Page `DamageTaken` + `Casts` (+ `DamageDone, targetID:<boss>` for the boss) with
   `includeResources:true`; for each event record `(sourceID if resourceActor==1
   else targetID, x, y)`.
3. Aggregate per actor (median = "where they set up"; for *spread* use time-windowed
   samples or a heatmap — a median collapses a stack).
4. Plot on a blank rect at **equal aspect ratio** (no texture needed). Validate on a
   stationary boss (Void Reaver): tanks cluster on the boss's far side, raid stacks
   opposite, ranged at max range.

Runnable worked examples (write to repo-root `reports/`, gitignored):
- [`examples/plot_fight.py`](examples/plot_fight.py) — single fight, role-colored.
- [`examples/compare_fights.py`](examples/compare_fights.py) — side-by-side
  ours-vs-benchmark on one shared full-map frame.

Both resolve the repo root automatically and reuse `warcraft-logs-analyzer`'s `lib`.
Edit the report code / fight / boss-id constants at the top to retarget.
