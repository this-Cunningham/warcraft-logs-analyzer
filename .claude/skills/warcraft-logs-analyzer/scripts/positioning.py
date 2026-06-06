"""positioning.py - the Positioning views for the deep-dive report.

Turns the per-boss `positions-<enc>.json` artifacts (per-actor x/y over the fight, the boss anchor track,
and per-ability hit spots; written by fetch_report._fetch_positions) into the five flagship positioning
features, all rendered as self-contained stdlib SVG/HTML fragments that build_deepdive injects into the
template. No new top-level tab — each view embeds next to the boss/mechanic it explains:

  1. Why we eat more of this ability  -> per-boss Positioning sub-tab (avoidable-hit scatter + verdict)
  2. Spread-vs-demand index           -> per-boss Positioning sub-tab + an Overview headline
  3. Melee uptime gap                 -> Execution, under Activity by Spec (tier aggregate)
  4. Void-zone overlap heatmap        -> per-boss Positioning sub-tab
  5. Spread-over-time gap strip       -> per-boss Positioning sub-tab

Honesty rules baked in (see references/coordinate-system.md + the brainstorm's KEEP/SHARPEN filter):
  * WCL x/y are a LINEAR transform of yards (isotropic), so relative geometry — distance, spread, in/out
    of a ring — is exact; the ~52.8 units/yd SCALE is a FLOOR, so every yard number is labelled ~approx
    and only the ours-vs-benchmark RATIO is leaned on. Never an absolute yard target, compass bearing, or HP.
  * Spread is sampled across many time bins (per-bin medians), never a single per-player median (which
    collapses a stacked raid to a point); footprint/NN come from those time-windowed samples.
  * The spread/stack VERDICT fires only for a curated set of vetted bosses (DEMAND); elsewhere the map +
    numbers are shown descriptively with no "you should…" arrow.
  * Melee-uptime is gated to STATIONARY/PLANT bosses (on a MOBILE boss the metric measures the boss's
    path, not melee discipline) and only surfaced where it diverges from the free Activity-by-Spec number.
"""

import math
import os

from report_common import read_json

SCALE = 52.8  # WCL units per yard — a FLOOR (UiMap 334 bounds fit); yard figures are approximate, ratios exact.

# Role palette (matches references/rendering.md): red is reserved for melee, so the boss is neutral silver.
COLORS = {"tank": "#f59e0b", "melee": "#ef4444", "healer": "#a3e635", "ranged": "#a855f7"}
BOSS_COLOR = "#e5e7eb"
MELEE_CLASSES = {"Warrior", "Rogue", "DeathKnight"}
RANGED_CLASSES = {"Mage", "Warlock", "Hunter", "Priest"}

# Curated mechanic demand per boss (the only place a spread/stack VERDICT is allowed to fire). Keyed by the
# boss's encounter NAME (stable across reports, unlike per-report actor ids). `cohort` is whose spacing the
# call is about: "squishies" = ranged+healers (who must fan out on a spread fight). Bosses absent here get
# the descriptive map + numbers but no directional verdict — exactly the brainstorm's "vetted list only".
DEMAND = {
    "Void Reaver": {"demand": "spread", "mechanic": "Arcane Orbs", "cohort": "squishies"},
    "High Astromancer Solarian": {"demand": "spread", "mechanic": "Wrath of the Astromancer", "cohort": "squishies"},
    "Lady Vashj": {"demand": "spread", "mechanic": "tainted cores / spore spacing", "cohort": "squishies"},
    "Leotheras the Blind": {"demand": "stack", "mechanic": "Whirlwind / Inner Demons", "cohort": "squishies"},
}

# Boss-travel thresholds (yards) for the auto STATIONARY / PLANT-AND-MOVE / MOBILE class (brainstorm
# addendum "planted-position detection"). Validated live: Void Reaver ~11yd STATIONARY, Al'ar ~1448yd MOBILE.
_STATIONARY_YD = 25.0
_MOBILE_YD = 160.0
# Melee ring (COMPUTED yd). SCALE is a FLOOR, so computed yards run ~1.3x true — calibrated live, melee
# sitting in true ~8yd range read ~10-11 computed yd. So the in-range ring is widened to ~12 computed yd
# (≈ true melee range) and the band is soft (in / edge / out) per the feature's sharpen note.
_RING_YD = 12.0
_EDGE_YD = 17.0


# ----------------------------------------------------------------------------- data loading + small geom

def load_positions(directory, enc):
    """positions-<enc>.json for one boss, or None if this data folder predates the positions fetch."""
    p = os.path.join(directory, "positions-{}.json".format(enc))
    if not os.path.isfile(p):
        return None
    try:
        return read_json(p)
    except (OSError, ValueError):
        return None


def classify_dps(cls, spec):
    """Split a DPS into melee vs ranged by class/spec (playerDetails only gives tank/healer/dps; see
    data-access.md). The hybrids resolve by spec; everything unknown falls to ranged (the safer default —
    a misclassified ranged just isn't counted toward melee-uptime, which never invents a melee problem)."""
    spec = spec or ""
    if cls in MELEE_CLASSES:
        return "melee"
    if cls in RANGED_CLASSES:
        return "ranged"
    if cls == "Druid":
        return "melee" if "Feral" in spec else "ranged"
    if cls == "Shaman":
        return "melee" if "Enha" in spec else "ranged"
    if cls == "Paladin":
        return "melee" if "Retribution" in spec else "ranged"
    return "ranged"


def role_map(roster, name_to_id):
    """{str(actorId): 'tank'|'melee'|'ranged'|'healer'} for one side, from its shared-boss roster.
    DPS are split melee/ranged; tanks/healers pass through. Keyed by actor id so it joins the positions file."""
    out = {}
    for p in roster:
        aid = name_to_id.get(p["name"])
        if aid is None:
            continue
        role = p["role"]
        if role == "dps":
            role = classify_dps(p.get("class"), p.get("spec"))
        out[str(aid)] = role
    return out


def _yd(d):
    return d / SCALE


def _median(vals):
    s = sorted(vals)
    n = len(s)
    if not n:
        return None
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0


def _actor_median(actor):
    pts = [p for p in actor["bins"] if p]
    if not pts:
        return None
    return (_median([p[0] for p in pts]), _median([p[1] for p in pts]))


def _fill(track):
    """Carry-forward fill of an actor's per-bin position track (and back-fill the leading gap with the
    first known point), so a sparse/idle actor isn't dropped from a time bin. All-None stays all-None."""
    nb = len(track)
    out = list(track)
    last = None
    for i in range(nb):
        if out[i]:
            last = out[i]
        elif last is not None:
            out[i] = last
    first = next((p for p in track if p), None)
    for i in range(nb):
        if out[i] is None:
            out[i] = first
        else:
            break
    return out


def boss_travel_yd(pos):
    """Total boss path length (yd) across its anchor track — drives the STATIONARY/PLANT/MOBILE class."""
    b = (pos.get("boss") or {}).get("bins") if pos.get("boss") else None
    if not b:
        return None
    pts = [p for p in b if p]
    if len(pts) < 2:
        return 0.0
    return _yd(sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
                   for i in range(1, len(pts))))


def boss_class(travel):
    if travel is None:
        return None
    if travel <= _STATIONARY_YD:
        return "stationary"
    if travel >= _MOBILE_YD:
        return "mobile"
    return "plant-and-move"


def boss_median(pos):
    b = (pos.get("boss") or {}).get("bins") if pos.get("boss") else None
    if not b:
        return None
    pts = [p for p in b if p]
    if not pts:
        return None
    return (_median([p[0] for p in pts]), _median([p[1] for p in pts]))


# ------------------------------------------------------------------------------------ spread + footprint

def _cohort_ids(roles, cohort):
    if cohort == "squishies":
        want = ("ranged", "healer")
    elif cohort == "ranged":
        want = ("ranged",)
    else:
        want = ("tank", "melee", "ranged", "healer")
    return [aid for aid, r in roles.items() if r in want]


def _bin_spread_radius(pts):
    """Robust spread radius of a cohort in one bin: median distance of its members from the cohort's MEDIAN
    centroid (yd). Median-on-both-ends resists the two failure modes the rendering doc warns about — it
    won't collapse to ~0 on a tight clump (it's a spread radius, not nearest-neighbour) and it isn't blown
    out by a couple of max-range ranged (the median centroid + median distance ignore the far outliers)."""
    if len(pts) < 3:
        return None
    cx = _median([p[0] for p in pts])
    cy = _median([p[1] for p in pts])
    return _median([math.hypot(p[0] - cx, p[1] - cy) for p in pts])


def spread_radius_yd(pos, roles, cohort="squishies"):
    """Time-windowed raid spread radius (yd) for a role cohort — the honest single spread number (feature 2).
    Per bin we fill every cohort actor's position (carry-forward) and take the robust per-bin spread radius,
    then median across bins. Sampling many time bins (not one per-player median) is what keeps a stacked raid
    from collapsing to ~0. None when the cohort is too small."""
    ids = _cohort_ids(roles, cohort)
    if len(ids) < 3:
        return None
    tracks = [_fill(pos["actors"][a]["bins"]) for a in ids if a in pos["actors"]]
    tracks = [t for t in tracks if any(p for p in t)]
    if len(tracks) < 3:
        return None
    per_bin = []
    for bi in range(pos["nBins"]):
        r = _bin_spread_radius([t[bi] for t in tracks if t[bi]])
        if r is not None:
            per_bin.append(r)
    if not per_bin:
        return None
    return round(_yd(_median(per_bin)), 1)


def spread_series(pos, roles, cohort="squishies", buckets=8):
    """Raid spread radius (yd) over fight-fraction buckets — the spread-over-time curve (feature 5). Bins are
    grouped into `buckets` equal fractions of the fight; each bucket is the median per-bin spread radius in
    that window. Same robust metric as the headline number, so the strip and the scalar agree. Returns a list
    of `buckets` values (None where a bucket lacks enough actors), comparable across fights via the fraction."""
    ids = _cohort_ids(roles, cohort)
    tracks = [_fill(pos["actors"][a]["bins"]) for a in ids if a in pos["actors"]]
    tracks = [t for t in tracks if any(p for p in t)]
    if len(tracks) < 3:
        return None
    nb = pos["nBins"]
    out = []
    for k in range(buckets):
        lo = int(round(k * nb / buckets))
        hi = max(lo + 1, int(round((k + 1) * nb / buckets)))
        vals = []
        for bi in range(lo, hi):
            r = _bin_spread_radius([t[bi] for t in tracks if t[bi]])
            if r is not None:
                vals.append(r)
        out.append(round(_yd(_median(vals)), 1) if vals else None)
    return out if any(v is not None for v in out) else None


def melee_uptime(pos, roles):
    """Melee in-range share vs the boss, time-anchored (feature 3). For each bin we fill every melee actor's
    position + the boss's, and score the distance with a SOFT band: <=8yd counts 1.0, 8-12yd 0.5, else 0.0
    (so a melee hovering at the ring edge isn't a hard miss). The mean over all (melee,bin) samples is the
    in-ring %. Returns {pct, inPct, edgePct, outPct, samples, meleeCount} or None when there's no boss anchor
    or no melee. The CALLER gates this to non-mobile bosses (on a mobile boss it measures the boss's path)."""
    boss = (pos.get("boss") or {}).get("bins") if pos.get("boss") else None
    if not boss:
        return None
    bfill = _fill(boss)
    melee_ids = [aid for aid, r in roles.items() if r == "melee" and aid in pos["actors"]]
    tracks = [_fill(pos["actors"][a]["bins"]) for a in melee_ids]
    tracks = [t for t in tracks if any(p for p in t)]
    if not tracks:
        return None
    nb = pos["nBins"]
    score = 0.0
    n = 0
    cin = cedge = cout = 0
    for bi in range(nb):
        bp = bfill[bi]
        if not bp:
            continue
        for t in tracks:
            p = t[bi]
            if not p:
                continue
            d = _yd(math.hypot(p[0] - bp[0], p[1] - bp[1]))
            n += 1
            if d <= _RING_YD:
                score += 1.0
                cin += 1
            elif d <= _EDGE_YD:
                score += 0.5
                cedge += 1
            else:
                cout += 1
    if not n:
        return None
    return {"pct": round(score / n * 100), "inPct": round(cin / n * 100),
            "edgePct": round(cedge / n * 100), "outPct": round(cout / n * 100),
            "samples": n, "meleeCount": len(tracks)}


# ------------------------------------------------------------------------- avoidable-ability hit geometry

def _hit_points(pos, ability, tank_ids):
    """Non-tank target hit positions for one ability on one side: [(x,y), ...] (drops tank targets to match
    the ex-tanks avoidable-damage gap). tank_ids is the set of str(actorId) tanks."""
    rec = (pos.get("hitsByAbility") or {}).get(ability)
    if not rec:
        return []
    out = []
    for x, y, tid in rec["points"]:
        if tid is not None and str(tid) in tank_ids:
            continue
        out.append((x, y))
    return out


def _gyration_yd(pts):
    """Radius of gyration (yd) of a point cloud about its own centroid — low = clustered, high = scattered."""
    if len(pts) < 2:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return round(_yd(math.sqrt(sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts) / len(pts))), 1)


def ability_cluster(pos, t_pos, ability, o_tank_ids, t_tank_ids):
    """The clustered-vs-scattered read behind an avoidable-damage gap (feature 1). Returns the hit clouds +
    each side's radius of gyration + a verdict. A tight cloud (low gyration) = the raid keeps clipping ONE
    hazard zone (a spacing/spot fix); a scattered/at-range cloud = the hits aren't a positioning problem
    (route it to a cooldown/healing fix). None when our side lacks enough hits to judge."""
    o_pts = _hit_points(pos, ability, o_tank_ids)
    t_pts = _hit_points(t_pos, ability, t_tank_ids) if t_pos else []
    if len(o_pts) < 6:
        return None
    o_gyr = _gyration_yd(o_pts)
    t_gyr = _gyration_yd(t_pts) if len(t_pts) >= 6 else None
    clustered = o_gyr is not None and o_gyr <= 14.0
    return {"ability": ability, "oursPoints": o_pts, "theirsPoints": t_pts,
            "oursGyr": o_gyr, "theirsGyr": t_gyr, "clustered": clustered,
            "oursN": len(o_pts), "theirsN": len(t_pts)}


# --------------------------------------------------------------------------------------- SVG rendering

def _robust_frame(sides, pad_frac=0.06):
    """One shared frame (minx,miny,maxx,maxy) for side-by-side panels: the 3rd-97th percentile box of every
    actor's median position + boss medians across BOTH fights, padded. Clipping the extremes keeps a single
    max-range hunter from compressing the core to a blob; true outliers are drawn clamped at the border."""
    xs, ys = [], []
    for pos in sides:
        for a in pos["actors"].values():
            c = _actor_median(a)
            if c:
                xs.append(c[0])
                ys.append(c[1])
        bm = boss_median(pos)
        if bm:
            xs.append(bm[0])
            ys.append(bm[1])
    if len(xs) < 2:
        return None

    def pct(v, q):
        s = sorted(v)
        return s[max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))]

    minx, maxx = pct(xs, 0.03), pct(xs, 0.97)
    miny, maxy = pct(ys, 0.03), pct(ys, 0.97)
    if maxx - minx < 1 or maxy - miny < 1:
        return None
    pad = pad_frac * max(maxx - minx, maxy - miny)
    return (minx - pad, miny - pad, maxx + pad, maxy + pad)


def _projector(frame, W):
    minx, miny, maxx, maxy = frame[0], frame[1], frame[2], frame[3]
    dx, dy = maxx - minx, maxy - miny
    scale = W / dx
    H = dy * scale
    return scale, H, (lambda x: (x - minx) * scale), (lambda y: H - (y - miny) * scale)


def _grid_and_border(W, H, scale):
    parts = ['<rect x="0" y="0" width="{:.0f}" height="{:.0f}" fill="#0f1420"/>'.format(W, H)]
    step = 10 * SCALE * scale  # a ~10yd grid
    g = step
    while g < W:
        parts.append('<line x1="{0:.1f}" y1="0" x2="{0:.1f}" y2="{1:.0f}" stroke="#1d2740" stroke-width="1"/>'.format(g, H))
        g += step
    g = step
    while g < H:
        parts.append('<line x1="0" y1="{0:.1f}" x2="{1:.0f}" y2="{0:.1f}" stroke="#1d2740" stroke-width="1"/>'.format(g, W))
        g += step
    parts.append('<rect x="0" y="0" width="{:.0f}" height="{:.0f}" fill="none" stroke="#334155" stroke-width="1.5"/>'.format(W, H))
    return parts


def _boss_marker(parts, bm, sx, sy, scale, W, H):
    if not bm:
        return
    bx, by = sx(bm[0]), sy(bm[1])
    bx = min(max(bx, 0), W)
    by = min(max(by, 0), H)
    parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="{:.1f}" fill="none" stroke="#94a3b8" '
                 'stroke-width="1.4" stroke-dasharray="5 4" opacity="0.55"/>'.format(bx, by, _RING_YD * SCALE * scale))
    parts.append('<polygon points="{0:.1f},{1:.1f} {2:.1f},{3:.1f} {0:.1f},{4:.1f} {5:.1f},{3:.1f}" '
                 'fill="{6}" stroke="#0f1420" stroke-width="1.6"/>'.format(
                     bx, by - 9, bx + 9, by, by + 9, bx - 9, BOSS_COLOR))


def _formation_panel(pos, roles, frame, W=300):
    """A faithful top-down panel: each actor at its whole-fight median position (role-coloured), the boss as
    a neutral diamond + dashed ~8yd ring. Outliers clamp to the border (hollow) so the core stays readable."""
    scale, H, sx, sy = _projector(frame, W)
    parts = _grid_and_border(W, H, scale)
    _boss_marker(parts, boss_median(pos), sx, sy, scale, W, H)
    items = []
    for aid, a in pos["actors"].items():
        c = _actor_median(a)
        if c:
            items.append((roles.get(aid, "ranged"), c))
    for role, c in sorted(items, key=lambda z: z[0]):
        col = COLORS.get(role, "#9ca3af")
        px, py = sx(c[0]), sy(c[1])
        inframe = (frame[0] <= c[0] <= frame[2] and frame[1] <= c[1] <= frame[3])
        px = min(max(px, 5), W - 5)
        py = min(max(py, 5), H - 5)
        if inframe:
            parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="5" fill="{}" stroke="#0f1420" stroke-width="1.2"/>'.format(px, py, col))
        else:
            parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="none" stroke="{}" stroke-width="1.8"/>'.format(px, py, col))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts))


def _scatter_panel(points, bm, frame, color, W=300):
    """A boss-relative scatter of one side's avoidable-ability hit positions (semi-transparent dots, so
    overlap reads as density). Same frame+scale as its sibling so the two clouds are directly comparable."""
    scale, H, sx, sy = _projector(frame, W)
    parts = _grid_and_border(W, H, scale)
    _boss_marker(parts, bm, sx, sy, scale, W, H)
    for x, y in points:
        px, py = sx(x), sy(y)
        if -6 <= px <= W + 6 and -6 <= py <= H + 6:
            parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="3.4" fill="{}" opacity="0.5"/>'.format(
                min(max(px, 0), W), min(max(py, 0), H), color))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts))


def _heatmap_panel(points, bm, frame, W=300, cells=18):
    """A density heatmap of one side's avoidable-hit cloud: the frame binned into square cells, each shaded
    by how many hits fell in it (the honest spread visual — a median would collapse it). One shared frame +
    one colour scale across both panels so 'our hot corner vs their cold one' reads straight across."""
    scale, H, sx, sy = _projector(frame, W)
    cw = W / cells
    rows = max(1, int(round(H / cw)))
    grid = [[0] * cells for _ in range(rows)]
    mx = 0
    for x, y in points:
        px, py = sx(x), sy(y)
        ci = int(px // cw)
        ri = int(py // cw)
        if 0 <= ci < cells and 0 <= ri < rows:
            grid[ri][ci] += 1
            mx = max(mx, grid[ri][ci])
    parts = ['<rect x="0" y="0" width="{:.0f}" height="{:.0f}" fill="#0f1420"/>'.format(W, H)]
    if mx > 0:
        for ri in range(rows):
            for ci in range(cells):
                v = grid[ri][ci]
                if not v:
                    continue
                # perceptual-ish ramp toward warm; alpha by relative density
                a = 0.18 + 0.72 * (v / mx)
                parts.append('<rect x="{:.1f}" y="{:.1f}" width="{:.1f}" height="{:.1f}" fill="#f97316" opacity="{:.2f}"/>'.format(
                    ci * cw, ri * cw, cw + 0.6, cw + 0.6, a))
    parts.append('<rect x="0" y="0" width="{:.0f}" height="{:.0f}" fill="none" stroke="#334155" stroke-width="1.5"/>'.format(W, H))
    _boss_marker(parts, bm, sx, sy, scale, W, H)
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts), W)


def _strip_svg(o_series, t_series, W=620, H=120):
    """The spread-over-time strip: footprint (yd) over fight fraction, ours vs benchmark overlaid, phase
    markers implicit in the fraction axis. Two polylines on one y-scale; gaps (low-actor buckets) skipped."""
    n = max(len(o_series or []), len(t_series or []))
    allv = [v for v in (o_series or []) + (t_series or []) if v is not None]
    if n < 2 or not allv:
        return ""
    pad = 26
    top = 10
    ymax = max(allv) * 1.15 or 1
    iw = W - pad - 8
    ih = H - top - 18

    def pts(series, color, who):
        if not series:
            return ""
        xy = []
        for i, v in enumerate(series):
            if v is None:
                continue
            x = pad + iw * (i / (len(series) - 1))
            y = top + ih * (1 - v / ymax)
            xy.append((x, y))
        if not xy:
            return ""
        line = '<polyline points="{}" fill="none" stroke="{}" stroke-width="2.2" opacity="0.95"/>'.format(
            " ".join("{:.1f},{:.1f}".format(x, y) for x, y in xy), color)
        dots = "".join('<circle cx="{:.1f}" cy="{:.1f}" r="2.6" fill="{}"/>'.format(x, y, color) for x, y in xy)
        return line + dots

    parts = ['<rect x="0" y="0" width="{:.0f}" height="{:.0f}" fill="#0f1420"/>'.format(W, H)]
    # y gridlines at 0 / mid / max
    for frac in (0.0, 0.5, 1.0):
        y = top + ih * (1 - frac)
        parts.append('<line x1="{0:.0f}" y1="{1:.1f}" x2="{2:.0f}" y2="{1:.1f}" stroke="#1d2740" stroke-width="1"/>'.format(pad, y, W - 8))
        parts.append('<text x="2" y="{:.1f}" fill="#64748b" font-size="9" font-family="sans-serif">{:.0f}</text>'.format(y + 3, ymax * frac))
    parts.append(pts(t_series, "#38bdf8", "theirs"))
    parts.append(pts(o_series, "#f59e0b", "ours"))
    parts.append('<text x="{:.0f}" y="{:.0f}" fill="#64748b" font-size="9" font-family="sans-serif">pull</text>'.format(pad, H - 5))
    parts.append('<text x="{:.0f}" y="{:.0f}" fill="#64748b" font-size="9" font-family="sans-serif" text-anchor="end">kill</text>'.format(W - 8, H - 5))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(W, H, "".join(parts))


def _legend():
    items = [("tank", "Tank"), ("melee", "Melee"), ("ranged", "Ranged"), ("healer", "Healer")]
    sp = "".join('<span style="color:{}">&#9679; {}</span>'.format(COLORS[k], lbl) for k, lbl in items)
    return ('<div style="color:#94a3b8;font-size:11px;margin:4px 0 2px;display:flex;gap:14px;flex-wrap:wrap">'
            + sp + '<span style="color:#94a3b8">&#9670; boss (dashed ~8yd ring)</span></div>')


def _dual(o_svg, t_svg, o_name, t_name, sub=""):
    cap = '<div style="color:#64748b;font-size:11px">{}</div>'.format(sub) if sub else ""
    return ('<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">'
            '<div style="text-align:center"><div class="poshd" style="color:var(--ours)">{0}</div>{1}{4}</div>'
            '<div style="text-align:center"><div class="poshd" style="color:var(--theirs)">{2}</div>{3}{4}</div>'
            '</div>').format(esc(o_name), o_svg, esc(t_name), t_svg, cap)


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------- the per-boss Positioning sub-tab

def boss_positioning(o_pos, t_pos, o_roles, t_roles, o_tank_ids, t_tank_ids,
                     boss_name, avoidable_rows, o_name, t_name):
    """Compose one boss's Positioning sub-tab (features 1, 2, 4, 5) as an HTML fragment, and return the
    scalars the Overview headline (spread gap) and the Execution melee-uptime view consume. Any sub-view
    whose data is missing is silently omitted — the section only shows what it can honestly support."""
    if not o_pos or not t_pos:
        return None
    travel_o = boss_travel_yd(o_pos)
    bclass = boss_class(travel_o)
    # On a MOBILE boss (e.g. Al'ar flying between platforms) the room frame and the boss anchor are
    # meaningless — actor "median positions" smear across the arena and a clustered/scattered verdict would
    # just track the boss's path. The brainstorm's auto-class GATES which features make sense, so a mobile
    # boss gets no Positioning section at all (melee-uptime is independently gated to non-mobile too).
    if bclass == "mobile":
        return None
    frame = _robust_frame([o_pos, t_pos])
    if not frame:
        return None
    demand = DEMAND.get(boss_name)

    # ---- feature 2: spread-vs-demand index (+ direction verdict for vetted bosses) ----
    o_sr = spread_radius_yd(o_pos, o_roles)
    t_sr = spread_radius_yd(t_pos, t_roles)
    spread_gap = None
    spread_html = ""
    if o_sr is not None and t_sr is not None:
        margin = 1.0  # yd: how much tighter/looser counts as a real gap, not sampling noise
        if demand:
            if demand["demand"] == "spread":
                worse = o_sr < t_sr - margin   # tighter than the benchmark on a SPREAD boss = bad
                arrow = "spread wider"
            else:  # stack
                worse = o_sr > t_sr + margin   # looser than the benchmark on a STACK boss = bad
                arrow = "stack tighter"
            if worse:
                verdict = ('<b>{demand} boss ({mech}).</b> Our ranged+healers hold a ~{o}yd spread radius vs '
                           'the benchmark\'s ~{t}yd — <b>{arrow}</b> next pull.').format(
                    demand=demand["demand"].title(), mech=esc(demand["mechanic"]), o=o_sr, t=t_sr, arrow=arrow)
            else:
                verdict = ('{demand} boss ({mech}). Our squishy spread radius (~{o}yd) {cmp} the benchmark\'s '
                           '(~{t}yd) — spacing here is fine.').format(
                    demand=demand["demand"].title(), mech=esc(demand["mechanic"]),
                    o=o_sr, t=t_sr, cmp="matches" if abs(o_sr - t_sr) < margin else ("beats" if o_sr > t_sr else "is close to"))
            spread_gap = {"boss": boss_name, "demand": demand["demand"], "mechanic": demand["mechanic"],
                          "oursSpread": o_sr, "theirsSpread": t_sr, "worse": worse,
                          "delta": round(abs(o_sr - t_sr), 1)}
        else:
            verdict = ('Ranged + healer spread radius: ~{o}yd vs the benchmark\'s ~{t}yd '
                       '(descriptive — no curated spread/stack call on this boss).').format(o=o_sr, t=t_sr)
        o_map = _formation_panel(o_pos, o_roles, frame)
        t_map = _formation_panel(t_pos, t_roles, frame)
        spread_html = (
            '<h4 style="margin:14px 0 4px">Raid formation &amp; spread'
            '<span class="xp">Experimental</span></h4>'
            + _legend()
            + _dual(o_map, t_map, o_name, t_name, "median position per player &middot; one shared frame &amp; zoom")
            + '<p class="posnote">{}</p>'.format(verdict))

    # ---- feature 5: spread-over-time strip ----
    strip_html = ""
    o_series = spread_series(o_pos, o_roles)
    t_series = spread_series(t_pos, t_roles)
    if o_series and t_series:
        strip = _strip_svg(o_series, t_series)
        if strip:
            ov = [v for v in o_series if v is not None]
            tv = [v for v in t_series if v is not None]
            note = ""
            if ov and tv:
                # find the bucket with the biggest gap, expressed in fight-fraction terms
                gaps = [(abs((o_series[i] or 0) - (t_series[i] or 0)), i)
                        for i in range(min(len(o_series), len(t_series)))
                        if o_series[i] is not None and t_series[i] is not None]
                if gaps:
                    g, gi = max(gaps)
                    frac = int(round(100 * (gi + 0.5) / len(o_series)))
                    if g >= 2:
                        note = ('Biggest spacing gap opens around <b>{}% into the fight</b> (~{}yd vs '
                                '~{}yd spread radius) — drill that window, not the whole fight.').format(
                            frac, o_series[gi], t_series[gi])
            strip_html = (
                '<h4 style="margin:18px 0 4px">Spread over time<span class="xp">Experimental</span></h4>'
                '<div style="color:#94a3b8;font-size:11px;margin-bottom:3px">'
                '<span style="color:#f59e0b">&#9679; {}</span> &nbsp; <span style="color:#38bdf8">&#9679; {}</span>'
                ' &nbsp; raid spread radius (~yd) across the fight</div>{}'
                '{}'.format(esc(o_name), esc(t_name), strip,
                            '<p class="posnote">{}</p>'.format(note) if note else ""))

    # ---- feature 1 + 4: the top avoidable ability — clustered/scattered scatter + heatmap ----
    ability_html = ""
    ability = _top_avoidable_with_hits(avoidable_rows, o_pos, t_pos)
    if ability:
        clus = ability_cluster(o_pos, t_pos, ability, o_tank_ids, t_tank_ids)
        if clus:
            bm_o, bm_t = boss_median(o_pos), boss_median(t_pos)
            sc_o = _scatter_panel(clus["oursPoints"], bm_o, frame, "#ef4444")
            sc_t = _scatter_panel(clus["theirsPoints"], bm_t, frame, "#38bdf8")
            hm_o = _heatmap_panel(clus["oursPoints"], bm_o, frame)
            hm_t = _heatmap_panel(clus["theirsPoints"], bm_t, frame)
            if clus["clustered"]:
                verdict = ('Our <b>{ab}</b> hits cluster in one zone (~{og}yd spread{cmp}) — this is a '
                           '<b>spacing fix</b>: half the raid is clipping the same hazard. Mark a spread/clear-out spot.'
                           ).format(ab=esc(ability), og=clus["oursGyr"],
                                    cmp=" vs benchmark ~{}yd".format(clus["theirsGyr"]) if clus["theirsGyr"] else "")
            else:
                verdict = ('Our <b>{ab}</b> hits are scattered/at-range (~{og}yd spread) — <b>not a positioning '
                           'problem</b>. Route it to a cooldown/healing assignment, not a movement drill.'
                           ).format(ab=esc(ability), og=clus["oursGyr"])
            ability_html = (
                '<h4 style="margin:18px 0 4px">Why we eat more {ab}<span class="xp">Experimental</span></h4>'
                '<div style="color:#94a3b8;font-size:11px;margin-bottom:3px">where each <b>{ab}</b> hit landed '
                '(non-tank), ours vs benchmark &middot; same frame &amp; boss anchor</div>'
                '{scatter}'
                '<div style="color:#94a3b8;font-size:11px;margin:10px 0 3px">Void-zone density — the same hits '
                'binned, hotter = more hits there</div>{heat}'
                '<p class="posnote">{verdict}</p>').format(
                    ab=esc(ability),
                    scatter=_dual(sc_o, sc_t, o_name, t_name, "{} hits ours / {} theirs".format(clus["oursN"], clus["theirsN"])),
                    heat=_dual(hm_o, hm_t, o_name, t_name),
                    verdict=verdict)

    body = spread_html + strip_html + ability_html
    if not body:
        return None
    cls_note = ""
    if bclass:
        names = {"stationary": "Stationary boss", "plant-and-move": "Plant-and-move boss", "mobile": "Mobile boss"}
        cls_note = ('<div style="color:#64748b;font-size:11px;margin-bottom:8px">{} '
                    '(travel ~{:.0f}yd over the kill) — positioning is read as relative geometry; '
                    'yard figures are approximate, the ours-vs-benchmark ratio is the signal.</div>').format(
            names.get(bclass, ""), travel_o or 0)
    html = cls_note + body

    # melee-uptime scalar for the Execution tier view (gated to non-mobile bosses by the caller's filter,
    # but we tag the class here so the caller can decide).
    mu = melee_uptime(o_pos, o_roles)
    mu_t = melee_uptime(t_pos, t_roles)
    melee = None
    if mu and mu_t:
        melee = {"boss": boss_name, "class": bclass, "ours": mu["pct"], "theirs": mu_t["pct"],
                 "oursIn": mu["inPct"], "theirsIn": mu_t["inPct"], "meleeCount": mu["meleeCount"]}

    return {"html": html, "spreadGap": spread_gap, "meleeUptime": melee, "bossClass": bclass}


# Damage-taken rows that are never a raid POSITIONING mechanic you reposition for: the boss's auto-attack and
# its single-target tank-cleave. Player SELF-DAMAGE (Seal/Judgement of Blood, Shadow Word: Death, Dark Rune,
# Life Tap, engineer bombs) is NOT name-listed — it self-filters via the distinct-target gate (it hits one
# player), so a real raid mechanic that happens to share a name ("Bomb") on some other boss isn't wrongly hidden.
_NOT_A_MECHANIC = {"Melee", "Knock Away"}


def _top_avoidable_with_hits(avoidable_rows, o_pos, t_pos):
    """Pick the ability for the scatter/heatmap: the highest-deficit row (we eat the most MORE of) that is a
    real raid-wide mechanic with spatial signal — excludes melee/self-damage by name AND requires the hit
    cloud to span >=5 distinct non-tank targets (so a one-victim self-hit can't masquerade as an AoE). On a
    cleanly-executed boss nothing qualifies (we don't eat meaningfully more of any positional mechanic) — the
    section then stays silent, which is the honest 'not a positioning problem' answer. avoidable_rows is the
    per-boss [{name, ours, theirs, deficit}] list (ex-tanks, per-second)."""
    o_hits = o_pos.get("hitsByAbility") or {}
    for r in avoidable_rows or []:
        nm = r.get("name")
        if r.get("deficit", 0) <= 0 or nm in _NOT_A_MECHANIC:
            continue  # only mechanics we take MORE of than the benchmark, and never melee/self-damage
        rec = o_hits.get(nm)
        if not rec or rec.get("total", 0) < 12:
            continue
        distinct = len({tid for _x, _y, tid in rec["points"] if tid is not None})
        if distinct >= 5:
            return nm
    return None


# --------------------------------------------------------------------- Execution: melee uptime gap (F3)

def melee_uptime_view(rows, o_name, t_name):
    """The tier-wide melee in-range view for Execution, under Activity by Spec (feature 3). Pools the
    per-boss melee in-ring % across STATIONARY / PLANT bosses only (a mobile boss measures the boss's path,
    not melee discipline), ours vs benchmark. Returns '' when no eligible boss has data."""
    elig = [r for r in (rows or []) if r and r.get("class") in ("stationary", "plant-and-move")]
    if not elig:
        return ""
    body = ""
    o_all, t_all = [], []
    for r in sorted(elig, key=lambda z: (z["theirs"] - z["ours"]), reverse=True):
        o_all.append(r["ours"])
        t_all.append(r["theirs"])
        dl_cls = "neg" if r["ours"] < r["theirs"] - 2 else ("pos" if r["ours"] > r["theirs"] + 2 else "flat")
        dl = r["ours"] - r["theirs"]
        body += ('<div class="dval lo">{o}%</div>'
                 '<div class="dbarL"><div class="f ours" style="width:{ow}%"></div></div>'
                 '<div class="dmid">{boss} <span class="poscl">{cls}</span>'
                 '<span class="delta {dc}">{ds}{dl}</span></div>'
                 '<div class="dbarR"><div class="f theirs" style="width:{tw}%"></div></div>'
                 '<div class="dval ro">{t}%</div>').format(
            o=r["ours"], t=r["theirs"], ow=max(2, r["ours"]), tw=max(2, r["theirs"]),
            boss=esc(r["boss"]), cls=esc((r.get("class") or "").replace("-", " ")),
            dc=dl_cls, ds="+" if dl > 0 else "", dl=dl)
    return ('<h2 class="section">Melee Uptime on the Boss<span class="xp">Experimental</span>'
            '<span class="hint">The geometric cause beneath the Activity-by-Spec gap: the share of melee '
            'samples within ~8&nbsp;yd of the boss (a soft in/edge/out band), time-weighted across the fight, '
            'ours vs the benchmark. Restricted to <b>non-mobile</b> bosses, where a low in-range % is melee '
            '<i>discipline</i> (chasing, over-reacting to mechanics) rather than the boss kiting itself away — '
            'on a mobile boss the number would measure the boss\'s path, so it\'s suppressed. Higher is better; '
            'a red boss means our melee left the ring more than the benchmark\'s. Ring distance is relative '
            '(~8&nbsp;yd floor), not an absolute yard claim. <b>Experimental.</b></span></h2>'
            '<div class="dmgcmp"><div class="dmgcmphdr2"><span class="cours">{o}</span>'
            '<span>Melee in-range %, by boss</span><span class="cthe">{t}</span></div>'
            '<div class="ugrid">{body}</div></div>').format(o=esc(o_name), t=esc(t_name), body=body)


# ------------------------------------------------------------------------ Overview: the one spread call

def spread_headline(gaps):
    """The single biggest spread-vs-demand gap across shared bosses, for the Overview (feature 2's headline).
    Only vetted bosses where we're past the benchmark by a real margin qualify; '' when none do."""
    cand = [g for g in (gaps or []) if g and g.get("worse")]
    if not cand:
        return ""
    g = max(cand, key=lambda z: z["delta"])
    verb = "spread wider" if g["demand"] == "spread" else "stack tighter"
    return ('<div class="poshl"><div class="poshl-k">Biggest positioning gap</div>'
            '<div class="poshl-v"><b>{boss}</b> — {verb} for {mech}. '
            'Our ranged+healers hold a ~{o}yd spread radius vs the benchmark\'s ~{t}yd.</div></div>').format(
        boss=esc(g["boss"]), verb=verb, mech=esc(g["mechanic"]), o=g["oursSpread"], t=g["theirsSpread"])
