"""build_comparison.py - turn two `rankings(compare: Parses)` JSON dumps into a
self-contained HTML comparison report.

Each input file is the saved output of:
    python query.py --query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' --variables '{"code":"..."}' --out-file ...

Usage:
    python build_comparison.py --ours-file ./data/ours-parses.json --theirs-file ./data/demo-parses.json \\
        --ours-name "Our Raid" --theirs-name "Tuesday Split" --zone-name "SSC / TK" \\
        --out-file ./reports/ssc-comparison.html
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
from report_common import avg, get_fights, index_by_encounter, render_report, ssum


def build(ours_file, theirs_file, out_file, ours_name="Our Raid", theirs_name="Benchmark", zone_name=""):
    ours = index_by_encounter(get_fights(ours_file))
    theirs = index_by_encounter(get_fights(theirs_file))

    # Common encounters, ordered by our kill order in the file.
    common_ids = [k for k in ours if k in theirs]

    bosses = [
        {"encounterID": int(i), "name": ours[i]["name"], "ours": ours[i], "theirs": theirs[i]}
        for i in common_ids
    ]

    summary = {
        "bossCount": len(bosses),
        "oursAvgParse": avg([b["ours"]["avgParse"] for b in bosses]),
        "theirsAvgParse": avg([b["theirs"]["avgParse"] for b in bosses]),
        "oursDeaths": ssum([b["ours"]["deaths"] for b in bosses]),
        "theirsDeaths": ssum([b["theirs"]["deaths"] for b in bosses]),
        "oursDurationMs": ssum([b["ours"]["durationMs"] for b in bosses]),
        "theirsDurationMs": ssum([b["theirs"]["durationMs"] for b in bosses]),
    }

    payload = {
        "zone": zone_name,
        "ours": {"title": ours_name},
        "theirs": {"title": theirs_name},
        "summary": summary,
        "bosses": bosses,
    }

    out_full = render_report(payload, out_file)
    print("Report written to {} ({} common bosses)".format(out_full, len(bosses)))
    return out_full


def main(argv=None):
    p = argparse.ArgumentParser(description="Build a two-raid parse comparison report.")
    p.add_argument("--ours-file", required=True)
    p.add_argument("--theirs-file", required=True)
    p.add_argument("--ours-name", default="Our Raid")
    p.add_argument("--theirs-name", default="Benchmark")
    p.add_argument("--zone-name", default="")
    p.add_argument("--out-file", required=True)
    args = p.parse_args(argv)
    build(args.ours_file, args.theirs_file, args.out_file, args.ours_name, args.theirs_name, args.zone_name)


if __name__ == "__main__":
    main()
