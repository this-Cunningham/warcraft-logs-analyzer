"""compare_raids.py - ONE deterministic command: two report URLs in, a tabbed
deep-dive comparison report out. No manual params, no LLM in the generation path.

    python compare_raids.py --ours-url https://fresh.warcraftlogs.com/reports/AAAA \\
                            --theirs-url https://fresh.warcraftlogs.com/reports/BBBB

Auto-resolves report codes, auto-computes the shared bosses (encounter-ID
intersection), fetches parses + heavy tables for those bosses, builds the report,
and opens it. Titles/zone default to the reports' own metadata.

Optional: --ours-name / --theirs-name to override labels, --out-file to set the path,
          --no-open to skip launching the browser.
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib
import build_deepdive
import fetch_report
import fetch_worldbest

META_Q = "query M($code:String!){reportData{report(code:$code){title zone{name} fights(killType:Kills){encounterID}}}}"
PARSE_Q = "query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}"
# rankings(compare:Parses) defaults to the DPS metric for EVERY role — so a healer's rankPercent/amount
# come back as a meaningless DPS parse (their incidental damage), NOT their HPS parse. We fetch HPS
# parses separately and merge them over the healers so each healer carries their real (HPS) parse.
HPS_PARSE_Q = "query P($code:String!){reportData{report(code:$code){rankings(compare:Parses, playerMetric:hps)}}}"


def get_code(u):
    m = re.search(r"reports/([^/?#\s]+)", u)
    return m.group(1) if m else u.strip()


def _rank_fights(obj):
    return ((((obj or {}).get("reportData") or {}).get("report") or {}).get("rankings") or {}).get("data") or []


def merge_healer_hps(default_obj, hps_obj):
    """Overwrite each healer's `rankPercent` + `amount` in the DPS-metric parses with the HPS-metric
    values (matched by encounter id + name within the healers bucket). Without this, healer parses are a
    DPS percentile of their ~0 incidental damage — wrong number, and it pollutes the Avg Raid Parse.
    Mutates and returns default_obj. dps/tanks are left on the DPS metric (their correct parse)."""
    hmap = {}  # (encId, name) -> (rankPercent, amount)
    for f in _rank_fights(hps_obj):
        enc = (f.get("encounter") or {}).get("id")
        for c in (((f.get("roles") or {}).get("healers") or {}).get("characters") or []):
            hmap[(enc, c.get("name"))] = (c.get("rankPercent"), c.get("amount"))
    for f in _rank_fights(default_obj):
        enc = (f.get("encounter") or {}).get("id")
        for c in (((f.get("roles") or {}).get("healers") or {}).get("characters") or []):
            hit = hmap.get((enc, c.get("name")))
            if hit is not None:
                c["rankPercent"], c["amount"] = hit
    return default_obj


def guild_name(parses_obj):
    """Most-common guild name across a report's parse entries. The report's guild is the report's own
    identity — far clearer in the report than an opaque report title. Returns the most-common name so a
    PUG night (mixed guilds) falls to whichever guild is dominant; None when no entry carries a guild."""
    rankings = ((((parses_obj or {}).get("reportData") or {}).get("report") or {}).get("rankings") or {})
    counts = {}
    for e in (rankings.get("data") or []):
        g = (e.get("guild") or {}).get("name")
        if g:
            counts[g] = counts.get(g, 0) + 1
    return max(counts, key=counts.get) if counts else None


def slug(s):
    """Filesystem-safe lowercase slug for the output filename (guild names → 'imminent-vs-foo')."""
    out = re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return out or "raid"


def trunc_name(s, limit=13):
    """Truncate a guild/report name past `limit` chars with an ellipsis. Long names blow out column
    widths and delta labels and make the report wrap unpredictably; capping the GUILD name (not the
    "Benchmark (…)" wrapper around it) keeps the layout stable for any guild pairing while staying
    recognizable. Our side caps at 13; the benchmark caps tighter at 8 (it carries the extra
    "Benchmark (…)" wrapper AND appears as a column label in many side-by-side tables, so it crowds
    headers fastest). Applied once here, at the naming source, so every reference to the name in the
    report (header, table columns, inline) inherits the truncated form for free. The filename slug still
    uses the full guild names, so on-disk reports stay distinguishable."""
    if not s:
        return s
    s = s.strip()
    return s if len(s) <= limit else s[:limit].rstrip() + "…"


def cached_for(code, data_root, shared):
    """True if this report's data on disk can be reused as-is: its parses + deep-data dir exist AND were
    fetched for the SAME shared-boss set. The deep fetch is scoped to `shared`, which depends on BOTH
    report codes — so cached data is only valid for the identical pairing, not just a matching code. We
    record the shared set in a `.shared.json` marker at fetch time and compare against it here. Pinned
    reports are immutable, so a match means the bytes are guaranteed current — no API call needed."""
    parses = os.path.join(data_root, "{}-parses.json".format(code))
    directory = os.path.join(data_root, code)
    marker = os.path.join(directory, ".shared.json")
    if not (os.path.isfile(parses) and os.path.isdir(directory) and os.path.isfile(marker)):
        return False
    try:
        with open(marker, encoding="utf-8") as fh:
            return sorted(json.load(fh)) == sorted(shared)
    except (OSError, ValueError):
        return False


def get_meta(code):
    r = lib.invoke_query(META_Q, {"code": code})["reportData"]["report"]
    if not r:
        raise RuntimeError("Report '{}' not found or not public.".format(code))
    encounters = sorted({int(f["encounterID"]) for f in r["fights"] if int(f["encounterID"]) != 0})
    return {"title": r["title"], "zone": (r.get("zone") or {}).get("name"), "encounters": encounters}


def open_file(path):
    """Cross-platform 'open this file in the default app' (replaces PS Invoke-Item)."""
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", path], check=False)


def main(argv=None):
    p = argparse.ArgumentParser(description="Two report URLs -> tabbed deep-dive comparison report.")
    p.add_argument("--ours-url", required=True)
    p.add_argument("--theirs-url", required=True)
    p.add_argument("--ours-name")
    p.add_argument("--theirs-name")
    p.add_argument("--out-file")
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--refresh", action="store_true",
                   help="re-fetch from the API even if cached data for these report codes exists")
    args = p.parse_args(argv)

    # Guild/report/ranking names carry accents; on a cp1252 Windows console or a non-UTF-8 pipe a plain
    # print() of one raises UnicodeEncodeError. Make stdout lossy-but-safe so logging can't sink the run.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ours_code = get_code(args.ours_url)
    theirs_code = get_code(args.theirs_url)

    print("Resolving reports ({}, {})...".format(ours_code, theirs_code))
    ours_meta = get_meta(ours_code)
    theirs_meta = get_meta(theirs_code)

    # Shared bosses = encounter-ID intersection (fully deterministic).
    theirs_set = set(theirs_meta["encounters"])
    shared = [e for e in ours_meta["encounters"] if e in theirs_set]
    if not shared:
        raise RuntimeError("No shared boss encounters between the two reports.")
    print("Shared bosses ({}): {}".format(len(shared), ", ".join(str(s) for s in shared)))

    zone = ours_meta["zone"]

    # Paths under <repo>/data and <repo>/reports.
    root = lib.find_repo_root()
    data_root = os.path.join(root, "data")
    os.makedirs(data_root, exist_ok=True)
    ours_dir = os.path.join(data_root, ours_code)
    theirs_dir = os.path.join(data_root, theirs_code)
    ours_parses = os.path.join(data_root, "{}-parses.json".format(ours_code))
    theirs_parses = os.path.join(data_root, "{}-parses.json".format(theirs_code))

    # Cache reuse: when both report codes + their shared-boss set match a prior run, the data on disk is
    # identical (pinned reports never change), so we skip the API entirely and read parses from disk.
    cached = {code: (cached_for(code, data_root, shared) and not args.refresh)
              for code in (ours_code, theirs_code)}

    # Parses (per-player percentile rankings) — fetched first so we can name each side by its GUILD.
    parse_obj = {}
    for code, path in ((ours_code, ours_parses), (theirs_code, theirs_parses)):
        if cached[code]:
            print("Using cached parses for {}.".format(code))
            with open(path, encoding="utf-8") as fh:
                parse_obj[code] = json.load(fh)
            continue
        print("Fetching parses for {}...".format(code))
        parse_obj[code] = lib.invoke_query(PARSE_Q, {"code": code})
        # Healers' parses default to DPS; overwrite them with the real HPS-metric parse.
        merge_healer_hps(parse_obj[code], lib.invoke_query(HPS_PARSE_Q, {"code": code}))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(parse_obj[code], fh, indent=2, ensure_ascii=False)

    # Name each side by its guild (the report's identity). Ours shows the guild name; theirs is framed
    # "Benchmark (Guild)" so a reader who didn't generate the report still knows which side to aspire to.
    # Manual --ours-name/--theirs-name override wins; guild name falls back to the report title.
    ours_guild = guild_name(parse_obj[ours_code])
    theirs_guild = guild_name(parse_obj[theirs_code])
    # Guild names are truncated before any wrapper is added (the "Benchmark (…)" wrapper is applied AFTER
    # truncating the guild, so only the guild name itself is shortened). Ours caps at 13; the benchmark
    # caps tighter at 8 — it carries the wrapper and appears as a column label across many tables, so it
    # crowds headers fastest. A manual --ours-name/--theirs-name override is the user's call and is left
    # exactly as given.
    ours_name = args.ours_name or trunc_name(ours_guild or ours_meta["title"])
    theirs_name = args.theirs_name or (
        "Benchmark ({})".format(trunc_name(theirs_guild, 8)) if theirs_guild else trunc_name(theirs_meta["title"], 8))
    # File named after the guilds (slugified), not the opaque report codes.
    out_file = args.out_file or os.path.join(
        root, "reports", "{}-vs-{}.html".format(slug(ours_guild or ours_code), slug(theirs_guild or theirs_code)))

    # Deep data (heavy output tables only for the shared bosses) — the bulk of the API cost. Reuse the
    # cached dir when valid; otherwise fetch and stamp the shared set so the next run can reuse it.
    for code, directory in ((ours_code, ours_dir), (theirs_code, theirs_dir)):
        if cached[code]:
            print("Using cached deep data for {}.".format(code))
            continue
        print("Fetching deep data for {}...".format(code))
        fetch_report.fetch(code, directory, shared)
        with open(os.path.join(directory, ".shared.json"), "w", encoding="utf-8") as fh:
            json.dump(sorted(shared), fh)

    # Same-faction world-best rotations for our raid's specs (powers the Optimize tab). Keyed by OUR
    # roster + faction + shared bosses, so it lives in ours_dir alongside the deep data. Re-fetched when
    # our data isn't cached, when --refresh is passed, or when an older cached dir predates this file
    # (so re-running over a cached report backfills the new tab). A failure here is non-fatal — the rest
    # of the report still builds; the Optimize tab just renders empty.
    worldbest_path = os.path.join(ours_dir, "worldbest.json")
    if cached[ours_code] and os.path.isfile(worldbest_path) and not args.refresh:
        print("Using cached world-best rotations.")
    else:
        print("Fetching same-faction world-best rotations...")
        enc_names = {int(k): v["name"] for k, v in
                     build_deepdive.index_by_encounter(build_deepdive.get_fights(ours_parses)).items()
                     if int(k) in shared}
        try:
            fetch_worldbest.fetch_for_report(ours_code, ours_parses, shared, enc_names, worldbest_path)
        except Exception as exc:
            print("  world-best fetch failed ({}); Optimize tab will render empty.".format(exc))

    # Build the report (pure Python + static template - deterministic).
    print("Building report...")
    out_full = build_deepdive.build(
        ours_dir, theirs_dir, ours_parses, theirs_parses, out_file,
        ours_name=ours_name, theirs_name=theirs_name, zone_name=zone or "",
    )

    print("\n{}  vs  {}  --  {} shared bosses".format(ours_name, theirs_name, len(shared)))
    print("Report: {}".format(out_full))
    if not args.no_open:
        open_file(out_full)


if __name__ == "__main__":
    main()
