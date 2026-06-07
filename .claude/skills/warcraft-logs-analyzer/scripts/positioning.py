"""positioning.py - the Positioning views for the deep-dive report.

Turns the per-boss `positions-<enc>.json` artifacts (per-actor x/y over the fight, the boss anchor track,
and per-ability hit spots; written by fetch_report._fetch_positions) into the positioning features, all
rendered as self-contained stdlib SVG/HTML fragments that build_deepdive injects into the template. No new
top-level tab — each view embeds next to the boss/mechanic it explains:

  2. Spread-vs-demand index           -> per-boss Positioning sub-tab + an Overview headline
  3. Melee uptime gap                 -> Execution, under Lowest-hanging DPS (tier aggregate)
  5. Spread-over-time curve            -> per-boss Timeline sub-tab (spread_series; aligned to the DPS axis)

(Features 1 "Why we eat more <ability>" + 4 "Void-zone density heatmap" were cut in the /audit pass:
experimental, buried in a sub-tab, and redundant with Execution → Avoidable Damage by Mechanic — see
TODO.md. Feature 5 "Spread over time" was removed from the Positioning sub-tab and RE-HOMED into the per-boss
Timeline tab, where it sits on the same seconds axis as the DPS curves. The formation map + spread-vs-demand
verdict and the melee-uptime gap remain in their own homes.)

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
import re

from report_common import read_json

SCALE = 52.8  # WCL units per yard — a FLOOR (UiMap 334 bounds fit); yard figures are approximate, ratios exact.
# Snapshot panels pin WIDTH to 260px. A WIDE zoom stand would render short & crunched at 260, so we render it
# a touch wider (uniform scale — proportions unchanged) for a bit more room; two still sit side by side in the
# ~1080px content column. Tall zoom stands and the fixed frame keep the 260 width untouched.
_WIDE_ZOOM_W = 320

# Role palette (matches references/rendering.md): red is reserved for melee, so the boss is neutral silver.
COLORS = {"tank": "#f59e0b", "melee": "#ef4444", "healer": "#a3e635", "ranged": "#a855f7"}
BOSS_COLOR = "#e5e7eb"
ADD_COLOR = "#ffffff"  # enemy NPC (add) — a WHITE square; the boss is a (slightly off-white) diamond, so the
#                        two read distinctly by SHAPE (square vs diamond) and the boss's dashed melee ring
OURS_TRAIL = "#4ea1ff"    # boss-path trail colour for ours (matches the report's --ours blue)
THEIRS_TRAIL = "#e268a8"  # boss-path trail colour for the benchmark (matches --theirs pink)
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

# Plant / re-plant snapshot detection (a boss is "planted" while it stays within this radius; a NEW plant after
# it moves away is its own snapshot moment, even mid-phase). Tuned for TBC fights: a stand must last a few
# seconds to hold a meaningful formation, and snapshots within a few seconds of each other are merged.
_PLANT_RADIUS_YD = 12.0   # boss stays within this of the stand's anchor = same plant
_MIN_PLANT_SEC = 6.0      # a stand shorter than this isn't a settled formation
_PLANT_STAB_SEC = 3.0     # skip the arrival scramble at the start of a stand
_PLANT_WINDOW_SEC = 10.0  # max length of a snapshot window
_PLANT_MERGE_SEC = 6.0    # moments closer than this are the same moment (keep the earlier/phase-labelled one)
_MAX_MOMENTS = 6          # cap snapshots per side so a long fight isn't a wall of maps


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


def _circ_mean_n(headings):
    """(circular-mean heading, sample count) over per-bin headings (radians), ignoring None. atan2 of the
    summed unit vectors handles the +/-pi seam. (None, 0) when nothing is present."""
    sx = sy = 0.0
    n = 0
    for h in headings:
        if h is None:
            continue
        sx += math.cos(h)
        sy += math.sin(h)
        n += 1
    return (math.atan2(sy, sx), n) if n else (None, 0)


def _circ_mean(headings):
    """Circular mean of per-bin headings (radians), ignoring None; None when nothing is present."""
    return _circ_mean_n(headings)[0]


def _heading_all(actor):
    """Whole-fight mean heading (radians) for an actor/boss/add track, or None when no facing was captured."""
    return _circ_mean(actor.get("facing") or [])


def _heading_at(actor, lo, hi, fill=False, min_n=1):
    """Mean heading (radians) over the window [lo,hi) of a track's per-bin facings. Needs at least `min_n`
    real samples in the window (a guard against a single noisy facing reading drawing a misleading arrow). When
    `fill` is set and the window has too few samples, fall back to the NEAREST captured facing outside it — used
    for persistent actors (boss, players) whose facing is sampled sparsely, so a short snapshot window that
    happens to miss a sample still gets the right heading; never used for transient adds (we don't infer a dead
    add's facing). None when the track has no facing at all."""
    fac = actor.get("facing")
    if not fac:
        return None
    h, n = _circ_mean_n(fac[lo:hi])
    if n >= min_n and h is not None:
        return h
    if not fill:
        return None
    mid = (lo + hi) // 2
    best = None
    best_d = None
    for i, v in enumerate(fac):
        if v is None:
            continue
        d = abs(i - mid)
        if best_d is None or d < best_d:
            best_d, best = d, v
    return best


def _arrow_svg(px, py, heading, col, ln=12.0, r0=0.0):
    """A facing arrow (line + barbed head) along `heading` (radians, WCL x/y frame), starting `r0` px out from
    (px,py) so it clears the actor's marker (a boss diamond / add square) and the whole arrow reads cleanly
    outside the dot. The screen y-axis is flipped vs the WCL frame, so the y component is negated. '' when no
    heading (we never INFER a facing — an actor with no captured facing simply gets no arrow)."""
    if heading is None:
        return ""
    dx, dy = math.cos(heading), -math.sin(heading)  # negate y: screen y grows downward
    bx, by = px + dx * r0, py + dy * r0
    tx, ty = px + dx * (r0 + ln), py + dy * (r0 + ln)
    sa = math.atan2(dy, dx)  # screen-space angle for the barbs
    bl = 4.0
    lx, ly = tx - bl * math.cos(sa - 0.5), ty - bl * math.sin(sa - 0.5)
    rx, ry = tx - bl * math.cos(sa + 0.5), ty - bl * math.sin(sa + 0.5)
    return ('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" stroke="{}" stroke-width="1.6" '
            'opacity="0.95"/><polygon points="{:.1f},{:.1f} {:.1f},{:.1f} {:.1f},{:.1f}" fill="{}"/>').format(
        bx, by, tx, ty, col, tx, ty, lx, ly, rx, ry, col)


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


def spread_series(pos, roles, cohort="squishies", buckets=20):
    """Raid spread radius (yd) over fight-fraction buckets — the spread-over-time curve. Bins are grouped
    into `buckets` equal fractions of the fight; each bucket is the median per-bin spread radius in that
    window. Same robust metric as the headline number (`spread_radius_yd`), so the curve and the scalar
    agree. The radius is a within-bin pairwise spread (distance from the cohort's median centroid), so it is
    FRAME-INDEPENDENT — valid even on a mobile boss, where it measures the squishies' internal spacing, not
    anything relative to the moving boss. Returns a list of `buckets` values (None where a bucket lacks
    enough actors), comparable across fights via the fraction. None when the cohort is too small."""
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
    position + the boss's, and score the distance with a SOFT band in COMPUTED yards: <=_RING_YD (12yd) counts
    1.0, 12-_EDGE_YD (17yd) 0.5, else 0.0 (so a melee hovering at the ring edge isn't a hard miss). The 12yd
    ring is the SCALE-floor-corrected stand-in for true ~8yd melee range — computed yd run ~1.3x true (see the
    _RING_YD note), which is why the user-facing legend says "~8 yd". The mean over all (melee,bin) samples is
    the in-ring %. Returns {pct, inPct, edgePct, outPct, samples, meleeCount} or None when there's no boss
    anchor or no melee. The CALLER gates this to non-mobile bosses (on a mobile boss it measures the boss's path)."""
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


# --------------------------------------------------------------------------------------- SVG rendering

def _robust_frame(sides, pad_frac=0.06):
    """One shared frame (minx,miny,maxx,maxy) for side-by-side panels: the FULL min/max box of every actor's
    median position + boss medians across BOTH fights, padded. No percentile clipping — every plotted dot
    falls inside the frame, so nobody is clamped to the border and the formation is shown honestly (a genuine
    far-out actor widens the frame; that's the true read, not an artefact). Used for the whole-fight single
    panel; snapshot panels use `_window_frame` (positions in the window, not whole-fight medians)."""
    xs, ys = [], []
    for pos in sides:
        for a in pos["actors"].values():
            c = _actor_median(a)
            if c:
                xs.append(c[0])
                ys.append(c[1])
        for a in (pos.get("adds") or {}).values():
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
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    if maxx - minx < 1 or maxy - miny < 1:
        return None
    pad = pad_frac * max(maxx - minx, maxy - miny)
    return (minx - pad, miny - pad, maxx + pad, maxy + pad)


def _window_frame(specs, pad_frac=0.06):
    """Shared frame (minx,miny,maxx,maxy) for SNAPSHOT panels, built from the actual positions being plotted —
    each actor's median over its window [lo,hi) plus the boss's — across every (pos, lo, hi) in `specs` (both
    raids share one frame, so a position is the same screen point in both panels and a gap reads as an offset).
    Full min/max (no clipping), so every drawn dot lands inside the frame."""
    xs, ys = [], []
    for pos, lo, hi in specs:
        for a in pos["actors"].values():
            pts = [p for p in _fill(a["bins"])[lo:hi] if p]
            if pts:
                xs.append(_median([p[0] for p in pts]))
                ys.append(_median([p[1] for p in pts]))
        for a in (pos.get("adds") or {}).values():
            pts = [p for p in a["bins"][lo:hi] if p]  # raw — a despawned add must not inflate the frame
            if pts:
                xs.append(_median([p[0] for p in pts]))
                ys.append(_median([p[1] for p in pts]))
        bb = (pos.get("boss") or {}).get("bins") if pos.get("boss") else None
        if bb:
            bpts = [p for p in _fill(bb)[lo:hi] if p]
            if bpts:
                xs.append(_median([p[0] for p in bpts]))
                ys.append(_median([p[1] for p in bpts]))
    if len(xs) < 2:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    if maxx - minx < 1 or maxy - miny < 1:
        return None
    pad = pad_frac * max(maxx - minx, maxy - miny)
    return (minx - pad, miny - pad, maxx + pad, maxy + pad)


def _moment_tab_label(label, replant_n):
    """Tab label for a snapshot moment: the opening is 'Opener'; a phase start shows the PHASE'S NAME when the
    encounter has named phases (e.g. 'P2: The Weapons') and 'Phase N' otherwise; a boss re-plant is a running
    number ('1','2',…), prefixed with its phase NAME when it falls inside one ('P5: Gravity Lapse · re-plant 2').
    Returns (tab_label, new_replant_n). (`label` is already the phase name / 'Re-plant' from `_plant_windows`.)"""
    label = label or ""
    low = label.lower()
    if low == "opening":
        return "Opener", replant_n
    if "re-plant" in low or "replant" in low:
        replant_n += 1
        # A re-plant with no named phase (label exactly "Re-plant") shows the bare running number; one inside a
        # named phase keeps that phase name so the tab still names its phase.
        if re.match(r'\s*re-?plant\s*$', label, flags=re.I):
            return str(replant_n), replant_n
        return "{} {}".format(label, replant_n), replant_n
    # phase start — `label` is already the phase name ("P2: The Weapons") or a "Phase N" fallback.
    return label, replant_n


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


def _boss_marker(parts, bm, sx, sy, scale, W, H, heading=None):
    if not bm:
        return
    bx, by = sx(bm[0]), sy(bm[1])
    bx = min(max(bx, 0), W)
    by = min(max(by, 0), H)
    parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="{:.1f}" fill="none" stroke="#94a3b8" '
                 'stroke-width="1.4" stroke-dasharray="5 4" opacity="0.55"/>'.format(bx, by, _RING_YD * SCALE * scale))
    # Facing arrow (cleave/cone-threat direction): start at the diamond's edge (r0=9) so the whole arrow reads
    # OUTSIDE the boss glyph, and draw it longer than a player's so the boss's heading is unmistakable.
    parts.append('<polygon points="{0:.1f},{1:.1f} {2:.1f},{3:.1f} {0:.1f},{4:.1f} {5:.1f},{3:.1f}" '
                 'fill="{6}" stroke="#0f1420" stroke-width="1.6"/>'.format(
                     bx, by - 9, bx + 9, by, by + 9, bx - 9, BOSS_COLOR))
    parts.append(_arrow_svg(bx, by, heading, BOSS_COLOR, ln=20.0, r0=9.0))


def _add_marker(parts, c, heading, sx, sy, W, H):
    """An enemy NPC (add): a WHITE square (still a square, distinct from the boss diamond) + its facing arrow
    (cleave/cone), clamped into frame. The arrow starts at the square's edge (r0=8) so it reads outside the glyph."""
    if not c:
        return
    ax, ay = sx(c[0]), sy(c[1])
    ax = min(max(ax, 6), W - 6)
    ay = min(max(ay, 6), H - 6)
    parts.append('<rect x="{:.1f}" y="{:.1f}" width="12" height="12" fill="{}" stroke="#0f1420" '
                 'stroke-width="1.3"/>'.format(ax - 6, ay - 6, ADD_COLOR))
    parts.append(_arrow_svg(ax, ay, heading, ADD_COLOR, ln=14.0, r0=8.0))


def _player_dot(parts, role, c, hd, sx, sy, frame, W, H):
    """One role-coloured player marker (facing arrow + dot; hollow + smaller when it clamps to the border)."""
    col = COLORS.get(role, "#9ca3af")
    px, py = sx(c[0]), sy(c[1])
    inframe = (frame[0] <= c[0] <= frame[2] and frame[1] <= c[1] <= frame[3])
    px = min(max(px, 5), W - 5)
    py = min(max(py, 5), H - 5)
    parts.append(_arrow_svg(px, py, hd, col, ln=10.0, r0=5.0))
    if inframe:
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="5" fill="{}" stroke="#0f1420" stroke-width="1.2"/>'.format(px, py, col))
    else:
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="4" fill="none" stroke="{}" stroke-width="1.8"/>'.format(px, py, col))


def _formation_panel(pos, roles, frame, W=300):
    """A faithful top-down panel: each actor at its whole-fight median position (role-coloured), the boss as
    a neutral diamond + dashed ~8yd ring. Outliers clamp to the border (hollow) so the core stays readable.
    Z-order: non-tank players → adds → boss → TANKS on top."""
    scale, H, sx, sy = _projector(frame, W)
    parts = _grid_and_border(W, H, scale)
    items = []
    for aid, a in pos["actors"].items():
        c = _actor_median(a)
        if c:
            items.append((roles.get(aid, "ranged"), c, _heading_all(a)))
    for role, c, hd in sorted([it for it in items if it[0] != "tank"], key=lambda z: z[0]):
        _player_dot(parts, role, c, hd, sx, sy, frame, W, H)
    for a in (pos.get("adds") or {}).values():
        _add_marker(parts, _actor_median(a), _heading_all(a), sx, sy, W, H)
    bd = pos.get("boss") or {}
    _boss_marker(parts, boss_median(pos), sx, sy, scale, W, H, heading=_heading_all(bd) if bd else None)
    for role, c, hd in [it for it in items if it[0] == "tank"]:
        _player_dot(parts, role, c, hd, sx, sy, frame, W, H)
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts))


def _legend(has_adds=False):
    items = [("tank", "Tank"), ("melee", "Melee"), ("ranged", "Ranged"), ("healer", "Healer")]
    sp = "".join('<span style="color:{}">&#9679; {}</span>'.format(COLORS[k], lbl) for k, lbl in items)
    add_leg = ('<span style="color:{}">&#9632; add</span>'.format(ADD_COLOR)) if has_adds else ""
    return ('<div style="color:#94a3b8;font-size:11px;margin:4px 0 2px;display:flex;gap:14px;flex-wrap:wrap">'
            + sp + '<span style="color:#94a3b8">&#9670; boss (dashed ~8yd ring)</span>' + add_leg
            + '<span style="color:#94a3b8">&#8594; facing</span></div>')


def _dual(o_svg, t_svg, o_name, t_name, sub=""):
    cap = '<div style="color:#64748b;font-size:11px">{}</div>'.format(sub) if sub else ""
    return ('<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">'
            '<div style="text-align:center"><div class="poshd" style="color:var(--ours)">{0}</div>{1}{4}</div>'
            '<div style="text-align:center"><div class="poshd" style="color:var(--theirs)">{2}</div>{3}{4}</div>'
            '</div>').format(esc(o_name), o_svg, esc(t_name), t_svg, cap)


def _single(svg, name, side, sub=""):
    """One side's panel alone — for a snapshot moment only ONE raid has (e.g. a re-plant the other didn't do,
    or a phase one raid never reached). `side` is 'ours'/'theirs' for the heading colour."""
    var = "--ours" if side == "ours" else "--theirs"
    cap = '<div style="color:#64748b;font-size:11px">{}</div>'.format(sub) if sub else ""
    return ('<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">'
            '<div style="text-align:center"><div class="poshd" style="color:var({0})">{1}</div>{2}{3}</div>'
            '</div>').format(var, esc(name), svg, cap)


def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _mmss(sec):
    sec = int(round(sec or 0))
    return "{}:{:02d}".format(sec // 60, sec % 60)


def _formation_at(pos, roles, frame, lo, hi, W=260, wide_room=False):
    """A formation panel like `_formation_panel`, but each actor's (and the boss's) position is the median
    over a TIME WINDOW of bins [lo, hi) — so we can snapshot the raid's shape at a specific moment (a phase
    start) instead of smearing the whole fight into one median. Tracks are carry-forward filled first, so an
    idle actor in the window isn't dropped. Same shared frame/scale as every other snapshot → comparable.
    `wide_room`: the projector pins panel WIDTH to W, so a tall stand renders roomy (W×big-H) while a WIDE
    stand renders short & crunched (its long edge capped at W). For zoom snapshots we render a wide stand a
    touch wider (W=`_WIDE_ZOOM_W`) — a UNIFORM scale-up, so the aspect ratio / proportions are unchanged, it
    just isn't cramped; two panels still sit side by side. Tall stands and the fixed frame keep W=260."""
    if wide_room and frame[2] - frame[0] > frame[3] - frame[1]:
        W = _WIDE_ZOOM_W            # a wide stand renders a bit wider than the 260 tall-panel width
    scale, H, sx, sy = _projector(frame, W)
    parts = _grid_and_border(W, H, scale)
    bd = pos.get("boss") or {}
    bb = bd.get("bins") if bd else None
    bm = None
    if bb:
        bpts = [p for p in _fill(bb)[lo:hi] if p]
        if bpts:
            bm = (_median([p[0] for p in bpts]), _median([p[1] for p in bpts]))
    # Z-order: NON-TANK players (bottom) → adds → boss → TANKS (very top). Tanks sit on the boss they hold, so
    # they're painted last; the boss diamond + add squares sit above the dps/healer dots so the anchors a
    # leader reads against are never hidden behind a dot.
    items = []
    for aid, a in pos["actors"].items():
        pts = [p for p in _fill(a["bins"])[lo:hi] if p]
        if pts:
            items.append((roles.get(aid, "ranged"),
                          (_median([p[0] for p in pts]), _median([p[1] for p in pts])),
                          _heading_at(a, lo, hi, fill=True)))
    for role, c, hd in sorted([it for it in items if it[0] != "tank"], key=lambda z: z[0]):
        _player_dot(parts, role, c, hd, sx, sy, frame, W, H)
    # Enemy NPCs (adds) present in this window. Use RAW (un-filled) bins: an add that despawned earlier must
    # NOT carry-forward its last position into later snapshots (that ghosted dead adds into every panel). It's
    # shown only where it actually has samples in [lo,hi); its facing needs ≥2 real samples (no inference).
    for a in (pos.get("adds") or {}).values():
        pts = [p for p in a["bins"][lo:hi] if p]
        if pts:
            ac = (_median([p[0] for p in pts]), _median([p[1] for p in pts]))
            _add_marker(parts, ac, _heading_at(a, lo, hi, min_n=2), sx, sy, W, H)
    # Boss heading: fill from the nearest captured sample (the boss persists all fight, so a short window that
    # misses a sparse facing reading still gets the right arrow).
    _boss_marker(parts, bm, sx, sy, scale, W, H,
                 heading=_heading_at(bd, lo, hi, fill=True) if bd else None)
    for role, c, hd in [it for it in items if it[0] == "tank"]:   # tanks ON TOP of the boss/adds
        _player_dot(parts, role, c, hd, sx, sy, frame, W, H)
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts))


def _trail_one_svg(xys, col, frame, W=260):
    """ONE raid's boss MOVEMENT TRAIL: its settled boss spot at each snapshot up to this tab, in time order,
    connected into a path. NO players. The latest point (this tab's stand) is drawn larger. Rendered in the
    shared constant frame, so ours and the benchmark (drawn in separate side-by-side panels) stay positionally
    comparable. `xys` are the boss (x,y) per moment up to the current tab."""
    scale, H, sx, sy = _projector(frame, W)
    parts = _grid_and_border(W, H, scale)
    pts = [(min(max(sx(x), 4), W - 4), min(max(sy(y), 4), H - 4)) for (x, y) in (xys or []) if x is not None]
    if len(pts) >= 2:
        parts.append('<polyline points="{}" fill="none" stroke="{}" stroke-width="2.4" '
                     'stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'.format(
                         " ".join("{:.1f},{:.1f}".format(px, py) for px, py in pts), col))
    for i, (px, py) in enumerate(pts):
        r = 6.0 if i == len(pts) - 1 else 3.2   # the most recent stand (this tab) is the big dot
        parts.append('<circle cx="{:.1f}" cy="{:.1f}" r="{:.1f}" fill="{}" stroke="#0f1420" '
                     'stroke-width="1.4"/>'.format(px, py, r, col))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{0:.0f}" height="{1:.0f}" viewBox="0 0 {0:.0f} {1:.0f}">{2}</svg>'.format(
        W, H, "".join(parts))


def _boss_stands(bb, bin_ms):
    """Maximal STATIONARY segments [start_bin, end_bin) of the boss anchor track `bb` — runs where the boss
    stays within `_PLANT_RADIUS_YD` of the segment's anchor. A None bin (boss not being hit — typically in
    flight / untargetable) breaks a segment, so the next run is a fresh stand. The first stand is the pull
    position; every later stand is a RE-PLANT (the boss moved away and settled somewhere new)."""
    nb = len(bb)
    plant_r = _PLANT_RADIUS_YD * SCALE
    segs = []
    i = 0
    while i < nb:
        if not bb[i]:
            i += 1
            continue
        anchor = bb[i]
        j = i + 1
        while j < nb and bb[j] and math.hypot(bb[j][0] - anchor[0], bb[j][1] - anchor[1]) <= plant_r:
            j += 1
        segs.append((i, j))
        i = j
    return segs


def _plant_windows(pos, phases, phase_names):
    """Labelled snapshot windows for one side — the moments worth freezing the formation at:
      * the OPENING (settled a few seconds after the pull),
      * the start of each named PHASE (`phases` = [{id, tSec}]), and
      * every boss RE-PLANT — anytime the boss moves and settles into a NEW stand, even mid-phase (so a boss
        that hops between platforms or repositions within a phase gets a snapshot per stand, not just one).
    Candidate moments from those three sources are merged (moments within `_PLANT_MERGE_SEC` collapse to one,
    keeping the phase-labelled one), each window runs from a short stabilization offset for up to
    `_PLANT_WINDOW_SEC` (not past the next moment), and the list is capped at `_MAX_MOMENTS`. Returns dicts
    {label, lo, hi, sec}; times are labelled (approximate), never claimed exact."""
    nb = pos.get("nBins") or 0
    bin_ms = pos.get("binMs") or 1
    dur_sec = (pos.get("durMs") or 0) / 1000.0
    if nb < 4 or dur_sec <= 0:
        return []

    def to_bin(s):
        return max(0, min(nb, int(round(s * 1000.0 / bin_ms))))

    ph = sorted([(p.get("tSec", 0), (phase_names or {}).get(int(p["id"])) or "Phase {}".format(p.get("id")))
                 for p in (phases or [])], key=lambda x: x[0])

    def phase_at(sec):
        lab = "Opening"
        for ts, nm in ph:
            if ts <= sec + 0.5:
                lab = nm
            else:
                break
        return lab

    # candidate moments: (sec, label)
    cands = [(0.0, "Opening")]
    for ts, nm in ph:
        if 0 < ts < dur_sec - 3:
            cands.append((ts, nm))
    bb = (pos.get("boss") or {}).get("bins") if pos.get("boss") else None
    if bb:
        for k, (a, b) in enumerate(_boss_stands(bb, bin_ms)):
            if k == 0:
                continue  # first stand == the pull (already the Opening candidate)
            if (b - a) * bin_ms / 1000.0 < _MIN_PLANT_SEC:
                continue
            ssec = a * bin_ms / 1000.0
            ph_lab = phase_at(ssec)
            # Plain middot here (the label is run through esc() at render); a no-named-phase boss (Al'ar)
            # just reads "Re-plant" rather than "Opening · re-plant".
            cands.append((ssec, "Re-plant" if ph_lab == "Opening" else ph_lab + " · re-plant"))

    cands.sort(key=lambda c: c[0])
    merged = []
    for sec, lab in cands:
        if merged and sec - merged[-1][0] < _PLANT_MERGE_SEC:
            continue
        merged.append((sec, lab))

    starts = [m[0] for m in merged]
    wins = []
    for idx, (sec, lab) in enumerate(merged):
        nxt = starts[idx + 1] if idx + 1 < len(starts) else dur_sec
        stab = min(_PLANT_STAB_SEC, max(0.0, (nxt - sec) * 0.25))
        win_start = sec + stab
        win_end = min(nxt, win_start + _PLANT_WINDOW_SEC, dur_sec)
        lo, hi = to_bin(win_start), to_bin(win_end)
        if hi - lo >= 2:
            # The boss's median position over this window — lets _match_moments tell whether ours and theirs
            # re-planted at the SAME stand (a fair side-by-side) or at different platforms (must not be paired).
            bxy = None
            if bb:
                bpts = [p for p in _fill(bb)[lo:hi] if p]
                if bpts:
                    bxy = (_median([p[0] for p in bpts]), _median([p[1] for p in bpts]))
            wins.append({"label": lab, "lo": lo, "hi": hi, "sec": round(sec), "bossXY": bxy})
        if len(wins) >= _MAX_MOMENTS:
            break
    return wins


def _match_moments(o_wins, t_wins):
    """Pair ours/theirs snapshot windows into render rows. Windows are grouped by LABEL and paired in
    chronological order within each label; a window with no counterpart on the other side becomes an UNMATCHED
    row (shown as a single panel) rather than being dropped — so a re-plant only one raid did is still shown.
    The two panels share one absolute frame (real positions, not aligned or centered), so a positioning gap
    between the raids reads as a real offset.
    Returns a list of {label, sec, o, t} sorted by time (o or t may be None)."""
    o_by, t_by = {}, {}
    for w in o_wins:
        o_by.setdefault(w["label"], []).append(w)
    for w in t_wins:
        t_by.setdefault(w["label"], []).append(w)
    rows = []
    for lab in (list(o_by) + [l for l in t_by if l not in o_by]):
        ol, tl = o_by.get(lab, []), t_by.get(lab, [])
        for i in range(max(len(ol), len(tl))):
            ow = ol[i] if i < len(ol) else None
            tw = tl[i] if i < len(tl) else None
            sec = (ow or tw)["sec"]
            rows.append({"label": lab, "sec": sec, "o": ow, "t": tw})
    rows.sort(key=lambda r: r["sec"])
    return rows


# --------------------------------------------------------------------- the per-boss Positioning sub-tab

def boss_positioning(o_pos, t_pos, o_roles, t_roles, o_tank_ids, t_tank_ids,
                     boss_name, o_name, t_name, o_phases=None, t_phases=None, phase_names=None):
    """Compose one boss's Positioning sub-tab (feature 2 — the formation map + spread-vs-demand verdict) as
    an HTML fragment, and return the scalars the Overview headline (spread gap) and the Execution melee-uptime
    view consume. The single whole-fight median map is replaced by SNAPSHOTS of the settled formation at the
    opening, each phase, and every boss RE-PLANT (the boss moving then settling into a new stand, even
    mid-phase), ours vs benchmark — where the raid stood *when it mattered*. Moments are paired across raids;
    one only a single raid reached is still shown, alone. Falls back to the single whole-fight map when there
    aren't ≥2 moments. Enemy adds (rose squares) and per-actor/boss facing arrows are drawn when the fetch
    captured them (decoded from each resourced event's `facing`); a transient add is shown only where it has
    real samples (never carry-forwarded), and an actor with no captured facing simply gets no arrow. Any
    sub-view whose data is missing is silently omitted."""
    if not o_pos or not t_pos:
        return None
    # Classify the boss from BOTH sides' travel (max), so the class is a property of the ENCOUNTER, not of
    # one raid's pull — a boss mobile on either side is treated as mobile (never wrongly fed to the
    # plantable melee view when the two raids disagree on class).
    travel_o = boss_travel_yd(o_pos)
    travel_t = boss_travel_yd(t_pos)
    bclass = boss_class(max(travel_o or 0, travel_t or 0))
    # A MOBILE boss (e.g. Al'ar flying between platforms) is mobile BETWEEN plants but stationary DURING them.
    # We render only its PLANTED windows (phase/re-plant snapshots where the boss is locally stationary) and
    # skip the whole-fight single-panel map (that one really would smear across the arena). Each tab is framed
    # to its own moment (its stands are different platforms) and both raids share that frame at real positions,
    # so a teleporting boss reads as a sequence of formations with any gap visible. The spread RADIUS verdict
    # is frame-independent (valid on every class).
    is_mobile = (bclass == "mobile")
    frame = _robust_frame([o_pos, t_pos])
    if not frame and not is_mobile:
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
        # Snapshot moments: the opening, each phase start, AND every boss RE-PLANT (the boss moving and
        # settling into a new stand). Each side is detected independently and paired by _match_moments (a
        # moment only one raid reached is shown alone). The two raids share ONE absolute frame at REAL room
        # positions — NOT aligned or boss-centered — so a positioning GAP between your raid and the benchmark
        # (a different tank spot, a looser spread, standing on the wrong side of the boss) shows as a real
        # offset you can point at. A non-mobile boss uses one frame across all moments (read drift as the raid
        # moves within a stable window); a MOBILE boss uses a tight per-moment frame (its stands are different
        # platforms, so one arena-wide frame would shrink every snapshot to a corner clump). Moments render as
        # labelled TABS (Opener / numbered re-plants / phase tags) in chronological order, not a wall of maps.
        o_wins = _plant_windows(o_pos, o_phases, phase_names)
        t_wins = _plant_windows(t_pos, t_phases, phase_names)
        rows_m = _match_moments(o_wins, t_wins)
        if rows_m:
            # ONE CONSTANT frame for the whole boss (used by every tab) — the tightest box that still contains
            # every snapshot position across all moments + both raids (with a little padding), so we zoom in as
            # far as we can from the full room WITHOUT the perspective ever changing as you click through tabs.
            allspecs = ([(o_pos, r["o"]["lo"], r["o"]["hi"]) for r in rows_m if r["o"]]
                        + [(t_pos, r["t"]["lo"], r["t"]["hi"]) for r in rows_m if r["t"]])
            win_frame = _window_frame(allspecs, pad_frac=0.10) or frame

            def _panel_at(ow, tw, fr, label, wide_room=False):
                if ow and tw:
                    om = _formation_at(o_pos, o_roles, fr, ow["lo"], ow["hi"], wide_room=wide_room)
                    tm = _formation_at(t_pos, t_roles, fr, tw["lo"], tw["hi"], wide_room=wide_room)
                    sub = label or "ours @ {} &middot; benchmark @ {} into the fight".format(_mmss(ow["sec"]), _mmss(tw["sec"]))
                    return _dual(om, tm, o_name, t_name, sub)
                if ow:
                    om = _formation_at(o_pos, o_roles, fr, ow["lo"], ow["hi"], wide_room=wide_room)
                    return _single(om, o_name, "ours", label or
                                   "ours @ {} into the fight &middot; benchmark had no matching stand here".format(_mmss(ow["sec"])))
                tm = _formation_at(t_pos, t_roles, fr, tw["lo"], tw["hi"], wide_room=wide_room)
                return _single(tm, t_name, "theirs", label or
                               "benchmark @ {} into the fight &middot; we had no matching stand here".format(_mmss(tw["sec"])))

            def _hdr(text):
                return '<div class="posnote" style="margin:12px 0 2px;opacity:.75">{}</div>'.format(text)

            tabs, panels, replant_n = [], [], 0
            for idx, r in enumerate(rows_m):
                ow, tw = r["o"], r["t"]
                # The formation in the ONE FIXED frame (constant across tabs) AND the same stand ZOOMED tight
                # to just this moment's positions (NOT boss-centered) — shown via a "Fixed frame / Zoom" TOGGLE
                # (one at a time, switched by the delegated .poszoombtn handler), not stacked vertically.
                fixed_panel = _panel_at(ow, tw, win_frame, None)
                mspecs = (([(o_pos, ow["lo"], ow["hi"])] if ow else [])
                          + ([(t_pos, tw["lo"], tw["hi"])] if tw else []))
                moment_frame = _window_frame(mspecs)
                if moment_frame:
                    zoom_panel = _panel_at(ow, tw, moment_frame, "zoomed to this stand", wide_room=True)
                    panel = ('<div class="poszoomgroup"><div class="poszoomtabs">'
                             '<button class="poszoombtn active" data-zoom="0" type="button">Fixed frame</button>'
                             '<button class="poszoombtn" data-zoom="1" type="button">Zoom</button></div>'
                             '<div class="poszoompane" style="display:block">' + fixed_panel + '</div>'
                             '<div class="poszoompane" style="display:none">' + zoom_panel + '</div></div>')
                else:
                    panel = fixed_panel
                # Boss MOVEMENT TRAIL — cumulative boss spot per tab, ours and benchmark in SEPARATE windows
                #    (same fixed frame, so the two paths still line up positionally).
                o_trail = [rows_m[j]["o"]["bossXY"] for j in range(idx + 1)
                           if rows_m[j]["o"] and rows_m[j]["o"].get("bossXY")]
                t_trail = [rows_m[j]["t"]["bossXY"] for j in range(idx + 1)
                           if rows_m[j]["t"] and rows_m[j]["t"].get("bossXY")]
                if o_trail or t_trail:
                    panel += (_hdr('<b>Boss path</b> — the boss\'s settled spot at each tab so far, connected in '
                                   'time order (big dot = this tab). No players — just where each raid moved the boss.')
                              + _dual(_trail_one_svg(o_trail, OURS_TRAIL, win_frame),
                                      _trail_one_svg(t_trail, THEIRS_TRAIL, win_frame),
                                      o_name, t_name, ""))
                tlab, replant_n = _moment_tab_label(r["label"], replant_n)
                tabs.append('<button class="postab{}" data-pos="{}" type="button" title="{}">{}</button>'.format(
                    " active" if idx == 0 else "", idx, esc(r["label"]), esc(tlab)))
                panels.append('<div class="pospanel" style="display:{}">{}</div>'.format(
                    "block" if idx == 0 else "none", panel))
            note = ('Each tab is one settled formation — the <b>Opener</b>, each phase, and every boss '
                    '<b>re-plant</b> — times approximate, cross-check the Timeline. Real positions throughout '
                    '(not aligned), so a difference in where/how your raid stood vs the benchmark is a real '
                    'offset — the positioning gap. The top map uses <b>one fixed window</b> (constant across '
                    'tabs); below it the same stand is also shown <b>zoomed to this moment</b>, and the '
                    '<b>Boss path</b> trail (ours and benchmark in separate windows) grows tab by tab to show '
                    'how each raid moved the boss. A moment only one raid reached is '
                    'shown alone. Arrows are each actor\'s (and the boss\'s) facing where captured; tanks are '
                    'painted on top; white squares are enemy adds.')
            maps_html = ('<div class="posblock"><div class="postabs">' + "".join(tabs) + '</div>'
                         + '<div class="pospanels">' + "".join(panels) + '</div>'
                         + '<p class="posnote" style="opacity:.8">' + note + '</p></div>')
        elif is_mobile:
            # mobile boss with no detectable plant window → no honest map; keep the (frame-independent) verdict
            maps_html = ('<p class="posnote" style="opacity:.8">This is a <b>mobile</b> boss with no settled '
                         'plant window long enough to snapshot a formation; the spread radius below is still '
                         'valid (it measures cohort spacing, independent of the boss\'s path).</p>')
        else:
            # No plant window detected (very short / no boss track) — one whole-fight map per side in the same
            # shared frame, real positions (so a positioning gap still shows).
            o_map = _formation_panel(o_pos, o_roles, frame)
            t_map = _formation_panel(t_pos, t_roles, frame)
            maps_html = _dual(o_map, t_map, o_name, t_name,
                              "median position per player &middot; one shared frame, real positions")
        has_adds = bool((o_pos.get("adds") or {}) or (t_pos.get("adds") or {}))
        spread_html = (
            '<h4 style="margin:14px 0 4px">Raid formation &amp; spread'
            '<span class="xp">Experimental</span></h4>'
            + _legend(has_adds)
            + maps_html
            + '<p class="posnote">{}</p>'.format(verdict))

    body = spread_html
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


# --------------------------------------------------------------------- Execution: melee uptime gap (F3)

def melee_uptime_view(rows, o_name, t_name):
    """The tier-wide melee in-range view for Execution, under Activity by Spec (feature 3). Pools the
    per-boss melee in-ring % across STATIONARY / PLANT bosses only (a mobile boss measures the boss's path,
    not melee discipline), ours vs benchmark. Returns '' when no eligible boss has data."""
    elig = [r for r in (rows or []) if r and r.get("class") in ("stationary", "plant-and-move")]
    if not elig:
        return ""
    body = ""
    for r in sorted(elig, key=lambda z: (z["theirs"] - z["ours"]), reverse=True):
        dl = r["ours"] - r["theirs"]  # higher melee uptime is better
        dl_cls = "good" if dl > 2 else ("bad" if dl < -2 else "flat")
        # New mirror layout (matches mirrorGrid): no side value columns — the signed gap (in percentage
        # points) sits under the boss name; the bars take the freed width.
        body += ('<div class="dbarL"><div class="f ours" style="width:{ow}%"></div></div>'
                 '<div class="dmid">{boss} <span class="poscl">{cls}</span>'
                 '<span class="delta {dc}">{ds}{dl}pp</span></div>'
                 '<div class="dbarR"><div class="f theirs" style="width:{tw}%"></div></div>').format(
            ow=max(2, r["ours"]), tw=max(2, r["theirs"]),
            boss=esc(r["boss"]), cls=esc((r.get("class") or "").replace("-", " ")),
            dc=dl_cls, ds="+" if dl > 0 else ("−" if dl < 0 else ""), dl=abs(dl))
    return ('<h2 class="section">Melee Uptime on the Boss<span class="xp">Experimental</span>'
            '<span class="hint">The geometric cause beneath a DPS gap: the share of melee '
            'samples within ~8&nbsp;yd of the boss, time-weighted, ours vs the benchmark. '
            '<b>Non-mobile bosses only</b> — on a mobile boss this would measure the boss\'s path, not melee '
            'discipline. Distances are relative, not absolute yards. Higher is better. <b>Experimental.</b></span></h2>'
            '<div class="dmgcmp"><div class="dmgcmphdr2"><span class="cours">{o}</span>'
            '<span>Melee in-range %, by boss</span><span class="cthe">{t}</span></div>'
            '<div class="mg">{body}</div></div>').format(o=esc(o_name), t=esc(t_name), body=body)


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
