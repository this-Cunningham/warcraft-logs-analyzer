"""spike_compare.py - PROOF-OF-CONCEPT: side-by-side positional comparison.

Renders two faithful top-down position plots at the SAME zoom so a raid's Void
Reaver spread can be eyeballed against a benchmark guild's. For Void Reaver the
meaningful signal is spread: Arcane Orbs bounce between clustered players, so a
tighter stack takes more chained orb damage.

Both panels use one coordinate system (TBC map 334) and one px/yd scale, so dot
positions and distances are directly comparable across panels.

Scratch artifact -> reports/voidreaver-compare.html (gitignored).
"""
import sys, os, math, statistics

def _repo_root(d):  # examples/ lives deep in the tree; resolve repo root by walking up to .git
    while os.path.dirname(d) != d:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return d
HERE = _repo_root(os.path.dirname(os.path.abspath(__file__)))  # = repo root (keeps reports/ + lib paths valid)
sys.path.insert(0, os.path.join(HERE, ".claude", "skills", "warcraft-logs-analyzer", "scripts"))
import lib

SCALE = 52.8  # working WCL-units-per-yard floor (from UiMap 334 bounds fit)
COLORS = {"tank": "#b45309", "melee": "#ef4444", "healer": "#a3e635",
          "ranged": "#a855f7", "dps": "#9ca3af"}
MELEE_CLASSES = {"Warrior", "Rogue", "DeathKnight"}
RANGED_CLASSES = {"Mage", "Warlock", "Hunter", "Priest"}

# (label, report code, fightID, boss NPC actor id)
SIDES = [
    ("Imminent (ours) — 193s kill", "pkHqfrBbhQK9GP1a", 17, 164),
    ("Benchmark (T5 #5) — 156s kill", "BxZPrhXYDfL1VKm8", 42, 210),
]


def classify_dps(p):
    cls = p.get("type")
    specs = p.get("specs") or []
    spec = (specs[0].get("spec") if specs and isinstance(specs[0], dict) else None) or ""
    if cls in MELEE_CLASSES:
        return "melee"
    if cls in RANGED_CLASSES:
        return "ranged"
    if cls == "Druid":
        return "melee" if "Feral" in spec else "ranged"
    if cls == "Shaman":
        return "melee" if "Enha" in spec else "ranged"
    if cls == "Paladin":
        return "melee"
    return "dps"


def get_roster(code, fight):
    d = lib.invoke_query(
        "query($c:String!){reportData{report(code:$c){playerDetails(fightIDs:[%d])}}}" % fight,
        {"c": code})
    pd = d["reportData"]["report"]["playerDetails"]
    pd = pd.get("data", pd).get("playerDetails", {})
    by_id = {}
    for p in pd.get("tanks", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": "tank"}
    for p in pd.get("healers", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": "healer"}
    for p in pd.get("dps", []):
        by_id[p["id"]] = {"name": p.get("name"), "role": classify_dps(p)}
    return by_id


def page_events(code, fight, dataType, extra=""):
    query = ("query($c:String!,$s:Float){reportData{report(code:$c){"
             "events(fightIDs:[%d],dataType:%s,includeResources:true,startTime:$s,limit:10000%s)"
             "{data nextPageTimestamp}}}}" % (fight, dataType, extra))
    start = None
    while True:
        d = lib.invoke_query(query, {"c": code, "s": start})
        ev = d["reportData"]["report"]["events"]
        for e in ev["data"]:
            if "x" not in e or "y" not in e:
                continue
            ra = e.get("resourceActor")
            aid = e.get("sourceID") if ra == 1 else e.get("targetID") if ra == 2 else None
            if aid is not None:
                yield aid, e["x"], e["y"]
        nxt = ev.get("nextPageTimestamp")
        if not nxt:
            break
        start = nxt


def get_bbox(code, fight):
    d = lib.invoke_query(
        "query($c:String!){reportData{report(code:$c){fights(fightIDs:[%d]){boundingBox{minX maxX minY maxY}}}}}" % fight,
        {"c": code})
    return d["reportData"]["report"]["fights"][0]["boundingBox"]


def fetch_positions(code, fight, boss_id):
    roster = get_roster(code, fight)
    samples = {}
    for dt, extra in [("DamageTaken", ""), ("Casts", ""), ("DamageDone", ",targetID:%d" % boss_id)]:
        for aid, x, y in page_events(code, fight, dt, extra):
            samples.setdefault(aid, []).append((x, y))

    def center(aid):
        pts = samples.get(aid, [])
        return (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)) if pts else None

    boss = center(boss_id)
    players = []
    for aid, info in roster.items():
        c = center(aid)
        if c:
            players.append({**info, "x": c[0], "y": c[1]})
    return boss, players


def spread_stats(players):
    """Raid spread metrics (in yards via SCALE)."""
    pts = [(p["x"], p["y"]) for p in players]
    n = len(pts)
    # nearest-neighbor distance per player
    nn = []
    for i, a in enumerate(pts):
        dmin = min((math.hypot(a[0] - b[0], a[1] - b[1]) for j, b in enumerate(pts) if j != i), default=0)
        nn.append(dmin)
    cx = statistics.mean(p[0] for p in pts); cy = statistics.mean(p[1] for p in pts)
    gyr = math.sqrt(statistics.mean((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in pts))
    return {
        "n": n,
        "median_nn_yd": statistics.median(nn) / SCALE,
        "footprint_yd": gyr / SCALE,
    }


def render_panel(boss, players, frame, W):
    minx, miny, maxx, maxy = frame
    dx, dy = maxx - minx, maxy - miny
    scale = W / dx               # equal aspect: same px/unit on both axes
    H = dy * scale

    def sx(x):
        return (x - minx) * scale

    def sy(y):
        return H - (y - miny) * scale

    parts = ['<rect x="0" y="0" width="%.0f" height="%.0f" fill="#0f1420"/>' % (W, H)]
    step = 10 * SCALE * scale
    g = 0
    while g < W:
        parts.append('<line x1="%.1f" y1="0" x2="%.1f" y2="%.0f" stroke="#1d2740" stroke-width="1"/>' % (g, g, H)); g += step
    g = 0
    while g < H:
        parts.append('<line x1="0" y1="%.1f" x2="%.0f" y2="%.1f" stroke="#1d2740" stroke-width="1"/>' % (g, W, g)); g += step
    parts.append('<rect x="0" y="0" width="%.0f" height="%.0f" fill="none" stroke="#334155" stroke-width="1.5"/>' % (W, H))
    bx, by = sx(boss[0]), sy(boss[1])
    parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5 4" opacity="0.5"/>' % (bx, by, 8 * SCALE * scale))
    parts.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="#e5e7eb" stroke="#0f1420" stroke-width="2"/>' % (bx, by - 10, bx + 10, by, bx, by + 10, bx - 10, by))
    for p in sorted(players, key=lambda z: z["role"]):
        c = COLORS.get(p["role"], "#9ca3af")
        px, py = sx(p["x"]), sy(p["y"])  # true position, no clamping
        parts.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s" stroke="#0f1420" stroke-width="1.3"/>' % (px, py, c))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">%s</svg>' % (W, H, W, H, "".join(parts))


def main():
    panels = []
    stats = []
    datasets = []
    for label, code, fight, boss_id in SIDES:
        boss, players = fetch_positions(code, fight, boss_id)
        bbox = get_bbox(code, fight)
        datasets.append((label, boss, players, bbox))
        stats.append((label, spread_stats(players)))
        print(label, "-> bbox", bbox, spread_stats(players))

    # common frame = UNION of both fights' WCL boundingBoxes (the "full map" rect), padded
    minx = min(d[3]["minX"] for d in datasets)
    maxx = max(d[3]["maxX"] for d in datasets)
    miny = min(d[3]["minY"] for d in datasets)
    maxy = max(d[3]["maxY"] for d in datasets)
    pad = 0.04 * max(maxx - minx, maxy - miny)
    frame = (minx - pad, miny - pad, maxx + pad, maxy + pad)

    W = 470
    for label, boss, players, bbox in datasets:
        svg = render_panel(boss, players, frame, W)
        panels.append((label, svg))

    legend = " &nbsp; ".join('<span style="color:%s">&#9679; %s</span>' % (c, r) for r, c in COLORS.items())
    panel_html = ""
    for label, svg in panels:
        panel_html += '<div style="text-align:center"><h2 style="font-size:15px;margin:4px 0">%s</h2>%s<div style="color:#64748b;font-size:11px">same zoom &middot; 10yd grid &middot; all players at true position</div></div>' % (label, svg)

    # comparison stats table
    rows = ""
    metrics = [("players plotted", "n", "%d"), ("median nearest-neighbor spread", "median_nn_yd", "%.1f yd"),
               ("raid footprint (radius of gyration)", "footprint_yd", "%.1f yd")]
    for name, key, fmt in metrics:
        cells = "".join('<td style="padding:4px 14px;text-align:right">%s</td>' % (fmt % s[key]) for _, s in stats)
        rows += '<tr><td style="padding:4px 14px;color:#94a3b8">%s</td>%s</tr>' % (name, cells)
    headers = "".join('<th style="padding:4px 14px;text-align:right;font-size:12px">%s</th>' % l.split(" —")[0] for l, _ in stats)

    html = """<!doctype html><html><head><meta charset="utf-8"><title>Void Reaver positioning: ours vs benchmark</title>
<style>body{{background:#0b0f17;color:#e2e8f0;font-family:sans-serif;margin:24px;max-width:1040px}}
h1{{font-size:20px}} .cap{{color:#94a3b8;font-size:13px;line-height:1.5}} table{{border-collapse:collapse;margin-top:8px}}</style></head><body>
<h1>Void Reaver &mdash; raid positioning: ours vs benchmark</h1>
<p class="cap">Each dot = a player's median position over the kill; silver diamond = boss; dashed ring &asymp; 8&nbsp;yd melee range.
Both panels show the FULL map (WCL's per-fight boundingBox, unioned across both kills) at one shared zoom, so positions are directly comparable; every player at their true position.
For Void Reaver, more spread = less Arcane-Orb chaining between players. Orientation provisional (no texture).</p>
<p>{legend}</p>
<div style="display:flex;gap:22px;justify-content:center;align-items:flex-start">{panels}</div>
<table><tr><td></td>{headers}</tr>{rows}</table>
<p class="cap">Coordinates via <code>events(includeResources:true)</code>; scale &asymp;52.8 WCL units/yd (UiMap 334 bounds, working estimate).</p>
</body></html>""".format(legend=legend, panels=panel_html, headers=headers, rows=rows)

    out = os.path.join(HERE, "reports", "voidreaver-compare.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    # also serve as index for preview
    with open(os.path.join(HERE, "reports", "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print("\nwrote", out)


if __name__ == "__main__":
    main()
