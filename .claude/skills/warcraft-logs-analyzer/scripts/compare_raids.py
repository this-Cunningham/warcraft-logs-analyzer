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

META_Q = "query M($code:String!){reportData{report(code:$code){title zone{name} fights(killType:Kills){encounterID}}}}"
PARSE_Q = "query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}"


def get_code(u):
    m = re.search(r"reports/([^/?#\s]+)", u)
    return m.group(1) if m else u.strip()


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
    args = p.parse_args(argv)

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

    # Parses (per-player percentile rankings) — fetched first so we can name each side by its GUILD.
    print("Fetching parses...")
    parse_obj = {}
    for code, path in ((ours_code, ours_parses), (theirs_code, theirs_parses)):
        parse_obj[code] = lib.invoke_query(PARSE_Q, {"code": code})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(parse_obj[code], fh, indent=2, ensure_ascii=False)

    # Name each side by its guild (the report's identity). Ours shows the guild name; theirs is framed
    # "Benchmark (Guild)" so a reader who didn't generate the report still knows which side to aspire to.
    # Manual --ours-name/--theirs-name override wins; guild name falls back to the report title.
    ours_guild = guild_name(parse_obj[ours_code])
    theirs_guild = guild_name(parse_obj[theirs_code])
    ours_name = args.ours_name or ours_guild or ours_meta["title"]
    theirs_name = args.theirs_name or ("Benchmark ({})".format(theirs_guild) if theirs_guild else theirs_meta["title"])
    # File named after the guilds (slugified), not the opaque report codes.
    out_file = args.out_file or os.path.join(
        root, "reports", "{}-vs-{}.html".format(slug(ours_guild or ours_code), slug(theirs_guild or theirs_code)))

    # Deep data (heavy output tables only for the shared bosses).
    print("Fetching deep data (ours)...")
    fetch_report.fetch(ours_code, ours_dir, shared)
    print("Fetching deep data (theirs)...")
    fetch_report.fetch(theirs_code, theirs_dir, shared)

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
