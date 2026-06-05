# Rendering a faithful plot

No texture needed (see map-assets.md). Plot dots on a blank rectangle.

## Equal aspect ratio is mandatory

Use the **same px-per-WCL-unit on both axes**. Never stretch the data to fill a fixed
box — that distorts every distance and angle and makes the plot lie. (`scale = W / dx`,
then `H = dy * scale`.)

## Framing strategies (pick per intent)

| frame | how | good for | cost |
|---|---|---|---|
| **Full map** | fight `boundingBox` (union across compared fights for a shared frame) | "where in the room," true spread, comparisons | core stack looks small if the room is large |
| Boss-centered, fit-all | square around boss sized to the farthest player | one fight, keep boss central | outliers (max-range ranged ~40yd) still compress the core |
| Percentile + clamp | window to the dense core; draw outliers hollow at the border | most readable core | hides true outlier positions — users often dislike this |

For **side-by-side comparison**, use **one shared frame and one scale** for both panels
(TBC fights share the same coordinate system, so WCL units are identical across
reports) — only then are positions/distances directly comparable.

## Aggregation pitfalls (important)

- **Per-player median position collapses a stacked raid into ~one point.** Good for
  "where did the raid set up," useless for spread. Symptom: median nearest-neighbor
  comes out <1 yd.
- **Spread metrics from medians are degenerate / outlier-skewed** (median NN ≈ 0; radius
  of gyration dominated by a couple of far players). For honest spread, sample positions
  at **many timestamps** (time-windowed) and aggregate, or render a **heatmap of raw
  samples**, rather than one median per player.
- "Outliers" are usually **legitimate max-range ranged** (hunters/locks at ~40yd), not
  errors — showing them at true position is correct.

## Roles & color

Color by role: tank, melee, ranged, healer. `playerDetails` only splits
tank/healer/dps — classify dps melee vs ranged by class/spec (see data-access.md). A
working palette: tank brown/orange `#b45309`, melee red `#ef4444`, healer yellow-green
`#a3e635`, ranged purple `#a855f7`. **Reserve red for melee → draw the boss a neutral
color** (e.g. silver `#e5e7eb`) so it doesn't read as a melee dot.

## Orientation

Which way is North, and the E-W / N-S flips, are **provisional until you calibrate to a
texture** (coordinate-system.md). Relative geometry (who's near whom, spread,
melee-on-boss) is unaffected, so insights hold regardless of final orientation.

## Validation — use a stationary boss as ground truth

**Void Reaver** is the ideal test (immobile boss). A correct extraction + frame shows:
tanks clustered on the boss's **far side** from the raid, the **raid stacked opposite**,
and **ranged spread to ~max range**. If that formation appears, your `resourceActor`
attribution and framing are right.

## Rendering tech

Pure **stdlib SVG** is enough (no matplotlib): emit a `<rect>` background, a faint grid
(`10yd = 10*SCALE*scale` px), the boss marker + a dashed `~8yd` melee ring, and a
`<circle>` per actor. Write a standalone `.html` wrapping the SVG; serve via the
project's `.claude/preview-server.py` (port 8753, serves `reports/`) and screenshot.

## Gotchas

- **Windows console mangles UTF-8 player names** in stdout (cosmetic `�`); the written
  HTML file is correct UTF-8.
- Filter stale `zzOLD…` actors from `masterData`.
- Guard `if "x" not in e` — miss/dodge events carry no resources.
