# Map image assets

## There is NO map image in the WCL API

Confirmed by a full schema scan (every type's fields + every field description):
- `GameMap` exposes only `id` + `name`; `ReportMap` only `id`. No url / filename /
  texture / icon field anywhere relevant.
- `ReportFight` gives `maps{id}` + `boundingBox` (the coordinate frame) — no art.
- `Encounter.journalID` is the Blizzard **journal** id → encounter/creature art, **not**
  a coordinate-aligned floor map. Dead end for backdrops.
- The replay image lives on `assets.rpglogs.com` (the bucket is live — returns S3
  *AccessDenied*, not no-host — for guessed paths), but the object path is
  undocumented and scraping it is fragile + a ToS gray area. **Don't depend on it.**

## You don't need a texture

Every actionable positioning insight is **relative geometry** — computable from x/y +
boundingBox alone, on a blank scaled rectangle:

| insight | needs | texture? |
|---|---|---|
| spread / stacking | pairwise distances | ❌ |
| melee uptime / in-range of boss | distance to boss x/y | ❌ |
| who ate the avoidable AoE | clustering at the hit timestamp | ❌ |
| boss-facing / cleave / "get behind" | `facing` + relative bearing | ❌ |
| movement / "stop dancing" | path length per player | ❌ |

A map texture is **cosmetic polish**, not a requirement. Ship the blank-backdrop
version first.

## If you do want a real texture (one-time, vendor it)

1. **Calibration bounds** — from `wago.tools` DB2 CSVs (sandbox-reachable via `curl`):
   - `curl https://wago.tools/db2/UiMap/csv` → find the map id (`Name_lang, ID`); WCL's
     `mapID` matches it directly (334 = "Tempest Keep").
   - `curl https://wago.tools/db2/UiMapAssignment/csv` → `Region_0..5` world bounds for
     that `UiMapID` (see coordinate-system.md).
2. **Texture** — extract from WoW Classic TBC client data: `wago.tools` map viewer,
   `wow.tools`/CASC Explorer, or community texture dumps. For map 334 it's `MapID 550`'s
   art tiles (16 tiles composited).
3. **Transform** — apply the world→map formula in coordinate-system.md, after
   calibrating the WCL→world affine against WCL's replay.
4. **Vendor** the texture + a `{mapID → texture, bounds, affine}` table into the repo →
   rendering stays offline, deterministic, dependency-free (fits the project ethos). No
   build-time network calls.
