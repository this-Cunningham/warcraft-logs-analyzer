"""cloud_startup.py — pre-generate a benchmark comparison report from two PINNED report codes.

Meant to run when a Claude Code cloud container starts cold: it produces a fresh self-contained HTML
report (and populates the local data cache) from two known reports — our raid + a top-world benchmark —
so a developer has real data and a real artifact to inspect, tweak, and verify changes against without a
manual fetch step every session.

    python scripts/cloud_startup.py            # build from cache if present, else fetch then build
    python scripts/cloud_startup.py --force    # always re-fetch from the WCL API
    python scripts/cloud_startup.py --no-open   # don't launch a browser (headless containers)

The two report codes below are pinned. Swap them to point at a different raid / benchmark pair.
Nothing in the *report* changes here — this is the pipeline/convenience layer only.
"""

import argparse
import os
import sys

# The skill's scripts live under .claude/skills/...; add that dir so we can import the pipeline modules.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_SCRIPTS = os.path.join(ROOT, ".claude", "skills", "warcraft-logs-analyzer", "scripts")
sys.path.insert(0, SKILL_SCRIPTS)

import lib              # noqa: E402
import build_deepdive   # noqa: E402
import compare_raids    # noqa: E402

# --- PINNED REPORTS (swap these to retarget) ---------------------------------------------------------
OURS_URL = "https://fresh.warcraftlogs.com/reports/pkHqfrBbhQK9GP1a"      # our raid
THEIRS_URL = "https://fresh.warcraftlogs.com/reports/BxZPrhXYDfL1VKm8"    # top-world benchmark


def _cache_ready(data_root, code):
    """True when this report's fetched data + parses already exist on disk (so we can skip the API)."""
    return (os.path.isdir(os.path.join(data_root, code))
            and os.path.isfile(os.path.join(data_root, "{}-parses.json".format(code))))


def main(argv=None):
    p = argparse.ArgumentParser(description="Pre-generate a report from two pinned report codes.")
    p.add_argument("--force", action="store_true", help="always re-fetch from the API, ignore the cache")
    p.add_argument("--no-open", action="store_true", help="don't launch a browser (headless containers)")
    args = p.parse_args(argv)

    ours_code = compare_raids.get_code(OURS_URL)
    theirs_code = compare_raids.get_code(THEIRS_URL)
    data_root = os.path.join(lib.find_repo_root(), "data")
    ours_parses = os.path.join(data_root, "{}-parses.json".format(ours_code))
    theirs_parses = os.path.join(data_root, "{}-parses.json".format(theirs_code))

    cached = (not args.force
              and _cache_ready(data_root, ours_code) and _cache_ready(data_root, theirs_code))

    if cached:
        # Reuse the on-disk cache — no API points spent. Re-derive guild names from the saved parses so
        # the report is named/labelled exactly as a fresh fetch would (build_deepdive is pure + offline).
        print("Cache hit — building from existing data (no API fetch). Pass --force to re-fetch.")
        from report_common import read_json  # noqa: E402
        ours_obj, theirs_obj = read_json(ours_parses), read_json(theirs_parses)
        ours_guild = compare_raids.guild_name(ours_obj)
        theirs_guild = compare_raids.guild_name(theirs_obj)
        ours_name = ours_guild or ours_code
        theirs_name = "Benchmark ({})".format(theirs_guild) if theirs_guild else theirs_code
        out_file = os.path.join(ROOT, "reports", "{}-vs-{}.html".format(
            compare_raids.slug(ours_guild or ours_code), compare_raids.slug(theirs_guild or theirs_code)))
        out_full = build_deepdive.build(
            os.path.join(data_root, ours_code), os.path.join(data_root, theirs_code),
            ours_parses, theirs_parses, out_file,
            ours_name=ours_name, theirs_name=theirs_name, zone_name="")
        print("Report: {}".format(out_full))
        if not args.no_open:
            compare_raids.open_file(out_full)
        return

    # Cold start (or --force): fall through to the full deterministic fetch+build pipeline.
    print("No cache (or --force) — running the full fetch + build pipeline.")
    cr_args = ["--ours-url", OURS_URL, "--theirs-url", THEIRS_URL]
    if args.no_open:
        cr_args.append("--no-open")
    compare_raids.main(cr_args)


if __name__ == "__main__":
    main()
