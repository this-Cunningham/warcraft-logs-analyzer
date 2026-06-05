# Coordinate system & calibration

## What WCL's x/y are (and aren't)

WCL's event `x`/`y` are a **linear transform of WoW world coordinates**, NOT raw
yards. They are:
- **Isotropic** — same unit on both axes (combat-log positions are yards; WCL just
  scales/offsets/rotates them). So **equal-aspect plotting preserves true shape and
  relative distance** — this is why a faithful plot needs no calibration.
- **Axis-swapped + scaled + offset** relative to Blizzard's frame.

Working scale ≈ **52.8 WCL units per yard** — but this is a **FLOOR** (derived by
fitting the 4 TBC bosses' bounding boxes to the map's world bounds; bosses don't fill
the map, so true scale is higher). **Treat yard distances as approximate until
calibrated; relative geometry is exact regardless.**

## `mapID` IS the Blizzard UiMap id (confirmed)

`wago.tools` `UiMap` CSV row **`id=334` = "Tempest Keep"** — exact match to WCL's
`mapID` and `gameData.map(id:334){name}`. So no id-guessing: WCL's `mapID` resolves
directly in Blizzard game data.

## `boundingBox` ≠ map span

`ReportFight.boundingBox{minX,maxX,minY,maxY}` is the **data extent** (min/max of
logged actor positions for that fight), **not** the map's world rectangle. Each TBC
boss shares one `mapID` but reports a **distinct** boundingBox (a different room /
sub-area). Use the boundingBox as a *frame* for plotting (see rendering.md); use
UiMap world bounds (below) for *true-yard* calibration.

## The world → map transform

WoW's world frame: **+X is North, +Y is West**. So the map's **horizontal** axis is
world **Y** (W→E) and the **vertical** axis is world **X** (N→S) — an axis swap.

Using map bounds (`WorldMapArea` Loc fields, or `UiMapAssignment` Region corners):

```
mapX_norm = (LocLeft − worldY) / (LocLeft − LocRight)     # 0 at West edge → 1 at East
mapY_norm = (LocTop  − worldX) / (LocTop  − LocBottom)     # 0 at North edge → 1 at South
pixelX = mapX_norm * textureWidth
pixelY = mapY_norm * textureHeight
```

This is the standard HereBeDragons / addon math.

## Map 334 (Tempest Keep) bounds — `UiMapAssignment`

Columns: `UiMin_0,UiMin_1,UiMax_0,UiMax_1, Region_0..5, ID, UiMapID, OrderIndex,
MapID, ...`. `Region_0..2` = world min corner (x,y,z); `Region_3..5` = world max
corner. For UiMap 334 (all 16 art tiles share it):

- worldX ∈ **[-100, 950]**, worldY ∈ **[-787.5, 787.5]** (yards), `MapID` 550.

(WCL coords for Void Reaver were x≈-37614, y≈42981 — far outside [-100,950]; that
mismatch is the proof WCL coords aren't raw yards.)

## Calibrating WCL units → real map (when you want true yards / a texture overlay)

The exact WCL→world transform (scale, offset, which flips) is the one empirical
unknown. Two ways to pin it, **once per map**:

1. **Against WCL's own replay** (recommended) — WCL already aligns positions to the
   room perfectly. Read 2–3 actors' replay positions at a timestamp, pull the same
   actors' WCL x/y, and least-squares-fit an affine map (scale + offset + flip per
   axis ≈ 4 params, 2 point-pairs suffice). The plot then matches WCL by construction.
2. **Against known layout** — match boss-room positions to the known map.

Store a small `{mapID → (texture, world_bounds, wcl_to_world_affine)}` table. TBC is
only ~7 raid maps (Kara, Gruul/Mag, SSC, TK, Hyjal, BT, Sunwell).
