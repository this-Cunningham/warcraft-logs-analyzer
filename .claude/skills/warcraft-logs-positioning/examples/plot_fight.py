"""spike_map.py - PROOF-OF-CONCEPT: faithful positional plot from WCL event data.

Pulls real per-actor positions for the Void Reaver kill (a stationary boss, so an
ideal faithfulness test), aggregates each actor's typical position, and renders a
geometrically faithful (equal-aspect) top-down SVG colored by role.

Faithfulness validation: Void Reaver is immobile and the fight is "spread for
Arcane Orbs," so we EXPECT tank+melee tightly clustered on the boss and
ranged/healers spread out. The script prints the measured role-to-boss distances
so we can confirm the geometry matches the known mechanic.

Standalone artifact -> reports/voidreaver-positions.html (gitignored). Scratch.
"""
import sys, os, json, math, statistics

def _repo_root(d):  # examples/ lives deep in the tree; resolve repo root by walking up to .git
    while os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return d
HERE = _repo_root(os.path.dirname(os.path.abspath(__file__)))  # = repo root (keeps reports/ + lib paths valid)
sys.path.insert(0, os.path.join(HERE, ".claude", "skills", "warcraft-logs-analyzer", "scripts"))
import lib

CODE = "pkHqfrBbhQK9GP1a"
FIGHT = 17           # Void Reaver
BOSS_ID = 164        # Void Reaver NPC actor id

MELEE_CLASSES = {"Warrior", "Rogue", "DeathKnight"}
RANGED_CLASSES = {"Mage", "Warlock", "Hunter", "Priest"}
# Druid/Shaman/Paladin are spec-dependent; resolve by spec below, else "dps".


def q(query, variables=None):
    return lib.invoke_query(query, variables)


def get_roster():
    """name/id -> role + class, from playerDetails (data.playerDetails.{tanks,healers,dps})."""
    data = q(
        "query($c:String!){reportData{report(code:$c){"
        "playerDetails(fightIDs:[%d]) "
        "masterData{actors(type:\"Player\"){id name subType}}"
        "}}}" % FIGHT,
        {"c": CODE},
    )
    rep = data["reportData"]["report"]
    pd = rep["playerDetails"]
    pd = pd.get("data", pd).get("playerDetails", {})
    by_id = {}

    def classify_dps(p):
        cls = p.get("type")
        specs = p.get("specs") or []
        spec = (specs[0].get("spec") if specs and isinstance(specs[0], dict) else None) or ""
        if cls in MELEE_CLASSES:
            return "melee"
        if cls in RANGED_CLASSES:
            return "ranged"
        # spec-dependent classes
        if cls == "Druid":
            return "melee" if "Feral" in spec else "ranged"
        if cls == "Shaman":
            return "melee" if "Enha" in spec else "ranged"
        if cls == "Paladin":
            return "melee"  # ret (holy would be a healer bucket)
        return "dps"

    for p in pd.get("tanks", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": "tank", "cls": p.get("type")}
    for p in pd.get("healers", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": "healer", "cls": p.get("type")}
    for p in pd.get("dps", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": classify_dps(p), "cls": p.get("type")}
    return by_id


def page_events(dataType, extra=""):
    """Yield (positioned_actor_id, x, y) for every resourced event of this type.

    resourceActor: 1 => the SOURCE carries the coords, 2 => the TARGET does.
    """
    query = (
        "query($c:String!,$s:Float){reportData{report(code:$c){"
        "events(fightIDs:[%d],dataType:%s,includeResources:true,startTime:$s,limit:10000%s)"
        "{data nextPageTimestamp}}}}" % (FIGHT, dataType, extra)
    )
    start = None
    while True:
        d = q(query, {"c": CODE, "s": start})
        ev = d["reportData"]["report"]["events"]
        for e in ev["data"]:
            if "x" not in e or "y" not in e:
                continue
            ra = e.get("resourceActor")
            aid = e.get("sourceID") if ra == 1 else e.get("targetID") if ra == 2 else None
            if aid is None:
                continue
            yield aid, e["x"], e["y"]
        nxt = ev.get("nextPageTimestamp")
        if not nxt:
            break
        start = nxt


def main():
    roster = get_roster()
    print("roster: %d players" % len(roster))

    samples = {}  # actor_id -> list of (x,y)
    counts = {}
    for dt, extra in [("DamageTaken", ""), ("Casts", ""), ("DamageDone", ",targetID:%d" % BOSS_ID)]:
        n = 0
        for aid, x, y in page_events(dt, extra):
            samples.setdefault(aid, []).append((x, y))
            n += 1
        counts[dt] = n
    print("event samples:", counts)

    # Per-actor robust center (median x, median y).
    def center(aid):
        pts = samples.get(aid, [])
        if not pts:
            return None
        return (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))

    boss = center(BOSS_ID)
    if not boss:
        print("!! no boss samples"); return
    players = {}
    for aid, info in roster.items():
        c = center(aid)
        if c:
            players[aid] = {**info, "x": c[0], "y": c[1], "n": len(samples.get(aid, []))}
    print("players with positions: %d / %d" % (len(players), len(roster)))

    # ---- Faithfulness validation: role distance to (stationary) boss ----
    SCALE = 52.8  # working WCL-units-per-yard estimate from the 4-boss UiMap bounds fit
    def dist(p):
        return math.hypot(p["x"] - boss[0], p["y"] - boss[1])
    by_role = {}
    for p in players.values():
        by_role.setdefault(p["role"], []).append(dist(p))
    print("\n--- median distance to boss (Void Reaver is stationary) ---")
    for role in ["tank", "melee", "healer", "ranged", "dps"]:
        ds = by_role.get(role)
        if ds:
            md = statistics.median(ds)
            print("  %-7s n=%2d  median=%7.0f WCL  (~%4.0f yd)" % (role, len(ds), md, md / SCALE))

    print("\nboss(VR) median = (%.0f, %.0f)  samples=%d" % (boss[0], boss[1], len(samples.get(BOSS_ID, []))))
    _xs = [p["x"] for p in players.values()]; _ys = [p["y"] for p in players.values()]
    print("player coord ranges: x[%.0f..%.0f] y[%.0f..%.0f]" % (min(_xs), max(_xs), min(_ys), max(_ys)))
    print("\n--- per-player (sorted by distance to boss) ---")
    for p in sorted(players.values(), key=lambda z: dist(z)):
        print("  %-12s %-7s (%8.0f,%8.0f)  d=%7.0f  n=%d" % ((p["name"] or "?")[:12], p["role"], p["x"], p["y"], dist(p), p["n"]))

    # ---- Render geometrically faithful SVG (equal aspect) ----
    # Frame on the ACTION: use a robust window around the boss so a few far-flung
    # players don't compress the main stack into an unreadable blob. Outliers are
    # clamped to the border and drawn as arrows so they're still accounted for.
    def pct(vals, q):
        s = sorted(vals); i = max(0, min(len(s) - 1, int(q * (len(s) - 1))))
        return s[i]
    pxs = [p["x"] for p in players.values()]; pys = [p["y"] for p in players.values()]
    lo_x, hi_x = pct(pxs, 0.08), pct(pxs, 0.92)
    lo_y, hi_y = pct(pys, 0.08), pct(pys, 0.92)
    # ensure the boss and its melee ring are in frame, keep a square-ish window
    half = max(hi_x - lo_x, hi_y - lo_y, 12 * SCALE) / 2.0 * 1.5
    cx, cy = boss[0], boss[1]
    minx, maxx = cx - half, cx + half
    miny, maxy = cy - half, cy + half
    dx, dy = maxx - minx, maxy - miny
    n_clamped = sum(1 for p in players.values() if not (minx <= p["x"] <= maxx and miny <= p["y"] <= maxy))

    W = 900.0
    scale = W / dx                 # EQUAL aspect: same px/unit on both axes
    H = dy * scale

    def sx(x):
        return (x - minx) * scale
    def sy(y):
        # screen y grows downward; invert so larger WCL-y is "up" (orientation provisional)
        return H - (y - miny) * scale

    COLORS = {"tank": "#b45309", "melee": "#ef4444", "healer": "#a3e635",
              "ranged": "#a855f7", "dps": "#9ca3af"}  # tank brown/orange, melee red, healer yellow-green, ranged purple
    parts = []
    parts.append('<rect x="0" y="0" width="%.0f" height="%.0f" fill="#0f1420"/>' % (W, H))
    # light grid every ~10 yd
    step = 10 * SCALE * scale
    g = 0
    while g < W:
        parts.append('<line x1="%.1f" y1="0" x2="%.1f" y2="%.0f" stroke="#1d2740" stroke-width="1"/>' % (g, g, H)); g += step
    g = 0
    while g < H:
        parts.append('<line x1="0" y1="%.1f" x2="%.0f" y2="%.1f" stroke="#1d2740" stroke-width="1"/>' % (g, W, g)); g += step
    # boss marker + a faint "melee range" ring (~8 yd)
    bx, by = sx(boss[0]), sy(boss[1])
    # boss drawn neutral silver (red is reserved for melee dps); dashed ring = ~8yd melee range
    parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5 4" opacity="0.5"/>' % (bx, by, 8 * SCALE * scale))
    parts.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#e5e7eb" stroke="#0f1420" stroke-width="2"/>' % (
        bx, by - 11, bx + 11, by, bx, by + 11, bx - 11, by))
    parts.append('<text x="%.1f" y="%.1f" fill="#e5e7eb" font-size="12" font-family="sans-serif" text-anchor="middle">Void Reaver</text>' % (bx, by - 16))
    # players
    for p in sorted(players.values(), key=lambda z: z["role"]):
        c = COLORS.get(p["role"], "#9ca3af")
        inframe = (minx <= p["x"] <= maxx and miny <= p["y"] <= maxy)
        px = min(max(sx(p["x"]), 8), W - 8)
        py = min(max(sy(p["y"]), 8), H - 8)
        if inframe:
            parts.append('<circle cx="%.1f" cy="%.1f" r="6.5" fill="%s" stroke="#0f1420" stroke-width="1.5"/>' % (px, py, c))
            parts.append('<text x="%.1f" y="%.1f" fill="#cbd5e1" font-size="10" font-family="sans-serif" text-anchor="middle">%s</text>' % (px, py - 10, (p["name"] or "?")[:10]))
        else:
            # outlier clamped to border: hollow marker + distance, so it's accounted for
            yd = dist(p) / SCALE
            parts.append('<circle cx="%.1f" cy="%.1f" r="5" fill="none" stroke="%s" stroke-width="2"/>' % (px, py, c))
            parts.append('<text x="%.1f" y="%.1f" fill="#94a3b8" font-size="9" font-family="sans-serif" text-anchor="middle">%s &rarr;%.0fyd</text>' % (px, py - 8, (p["name"] or "?")[:8], yd))
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">%s</svg>' % (W, H, W, H, "".join(parts))

    legend = " &nbsp; ".join('<span style="color:%s">&#9679; %s</span>' % (c, r) for r, c in COLORS.items())
    html = """<!doctype html><html><head><meta charset="utf-8"><title>Void Reaver positions (faithful coords)</title>
<style>body{{background:#0b0f17;color:#e2e8f0;font-family:sans-serif;margin:24px;max-width:1000px}}
h1{{font-size:20px}} .cap{{color:#94a3b8;font-size:13px;line-height:1.5}}</style></head><body>
<h1>Void Reaver &mdash; faithful positional plot (real WCL data)</h1>
<p class="cap">Each dot is a player's median position over the kill; silver diamond is the (stationary) boss; dashed ring &asymp; 8&nbsp;yd melee range.
Equal aspect ratio &rarr; shapes &amp; distances are geometrically faithful. Frame zoomed to the raid stack; {nclamp} far-flung player(s) shown hollow at the border with their distance.
Orientation (which way is North / E-W flips) is provisional until texture calibration.</p>
<p>{legend}</p>
{svg}
<p class="cap">Source: report {code}, fight {fight} (Void Reaver). Coordinates via <code>events(includeResources:true)</code>,
attributed by <code>resourceActor</code> (1=source, 2=target). Working scale &asymp;52.8 WCL units/yd from the UiMap&nbsp;334 bounds fit.</p>
</body></html>""".format(legend=legend, svg=svg, code=CODE, fight=FIGHT, nclamp=n_clamped)

    outdir = os.path.join(HERE, "reports")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "voidreaver-positions.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
