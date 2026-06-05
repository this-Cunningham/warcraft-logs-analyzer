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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib
import build_deepdive
import fetch_report
import fetch_worldbest

META_Q = "query M($code:String!){reportData{report(code:$code){title zone{name} fights(killType:Kills){encounterID}}}}"
# rankings(compare:Parses) defaults to the DPS metric for EVERY role — so a healer's rankPercent/amount
# come back as a meaningless DPS parse (their incidental damage), NOT their HPS parse. We pull the HPS
# metric alongside it and merge it over the healers so each healer carries their real (HPS) parse.
# Both metrics ride in ONE request via aliases: WCL charges the report-load once per request, so two
# aliased rankings cost fewer points than two separate calls — and the `dps`/`hps` aliases unpack back
# into the exact same per-metric objects the merge expects, so the written JSON is byte-for-byte unchanged.
MERGED_PARSE_Q = ("query P($code:String!){reportData{report(code:$code){"
                  "dps: rankings(compare:Parses) "
                  "hps: rankings(compare:Parses, playerMetric:hps)}}}")

# The two reports are pinned/immutable, so their fetched data is cached hard (re-fetch only on --refresh).
# The world-best rotations are the one LIVE input — but the global leaderboards barely move over a tier,
# so an on-disk worldbest.json younger than this window is reused rather than re-fetched. World-best is the
# bulk of the fetch's REQUESTS (~half the calls), so reusing it makes a tight dev loop (repeated --refresh)
# cheap and, more importantly, stops us re-hammering the live leaderboard: --refresh re-pulls the report
# data but leaves a recent worldbest alone. --refresh-worldbest forces it; --worldbest-ttl-hours overrides
# the window. Default: 2 weeks — well within a raid tier, so the benchmark is effectively never re-fetched.
WORLDBEST_TTL_HOURS = 24.0 * 14  # 2 weeks


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
                   help="re-fetch the REPORT data from the API even if cached data for these codes exists")
    p.add_argument("--refresh-worldbest", action="store_true",
                   help="also re-fetch the live world-best rotations (otherwise reused while within the TTL)")
    p.add_argument("--worldbest-ttl-hours", type=float, default=WORLDBEST_TTL_HOURS,
                   help="reuse an on-disk worldbest.json younger than this many hours (default %(default)s)")
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
    # Both metadata lookups are independent one-shot queries → fetch them together.
    ours_meta, theirs_meta = lib.parallel_map(get_meta, [ours_code, theirs_code])

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
    # Each side's DPS-metric parses + HPS-metric overlay come back in ONE aliased request (fewer points
    # than two calls). Across both uncached reports the two requests are independent, so we still fan
    # them out. The reconstructed per-metric objects + merge yield JSON identical to the old two-call path.
    parse_obj = {}

    def fetch_parses(code):
        rep = lib.invoke_query(MERGED_PARSE_Q, {"code": code})["reportData"]["report"]
        # Rebuild the exact single-metric response shape each side expects, then overlay HPS on healers
        # (whose default-metric parse is a meaningless DPS percentile of their incidental damage).
        default_obj = {"reportData": {"report": {"rankings": rep["dps"]}}}
        hps_obj = {"reportData": {"report": {"rankings": rep["hps"]}}}
        return merge_healer_hps(default_obj, hps_obj)

    to_fetch = []
    for code, path in ((ours_code, ours_parses), (theirs_code, theirs_parses)):
        if cached[code]:
            print("Using cached parses for {}.".format(code))
            with open(path, encoding="utf-8") as fh:
                parse_obj[code] = json.load(fh)
        else:
            print("Fetching parses for {}...".format(code))
            to_fetch.append((code, path))

    for (code, path), obj in zip(to_fetch, lib.parallel_map(lambda cp: fetch_parses(cp[0]), to_fetch)):
        parse_obj[code] = obj
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)

    # Name each side by its guild (the report's identity). Ours shows the guild name; theirs is framed
    # "Benchmark (Guild)" so a reader who didn't generate the report still knows which side is B (the
    # comparison target — a better guild, or your own past raid; B is not assumed to be "better").
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

    # Deep data (heavy output tables only for the shared bosses) — the bulk of the API cost — plus the
    # same-faction world-best rotations for the Optimize tab. These three jobs (our deep data, their deep
    # data, world-best) are fully independent: each writes a disjoint set of files and world-best reads
    # only ours_parses, already on disk. So we collect the uncached ones and run them concurrently; each
    # job also parallelizes internally, all throttled by lib's global request semaphore. Reuse cached
    # data/dirs when valid; otherwise fetch and stamp the shared set so the next run can reuse it.
    def deep_task(code, directory):
        fetch_report.fetch(code, directory, shared)
        with open(os.path.join(directory, ".shared.json"), "w", encoding="utf-8") as fh:
            json.dump(sorted(shared), fh)

    # World-best is keyed by OUR roster + faction + shared bosses, so it lives in ours_dir alongside the
    # deep data. Re-fetched when our data isn't cached, when --refresh is passed, or when an older cached
    # dir predates this file (so re-running over a cached report backfills the tab). A failure here is
    # non-fatal — the rest of the report still builds; the Optimize tab just renders empty.
    worldbest_path = os.path.join(ours_dir, "worldbest.json")

    def worldbest_task():
        enc_names = {int(k): v["name"] for k, v in
                     build_deepdive.index_by_encounter(build_deepdive.get_fights(ours_parses)).items()
                     if int(k) in shared}
        try:
            fetch_worldbest.fetch_for_report(ours_code, ours_parses, shared, enc_names, worldbest_path)
        except Exception as exc:
            print("  world-best fetch failed ({}); Optimize tab will render empty.".format(exc))

    heavy_jobs = []
    for code, directory in ((ours_code, ours_dir), (theirs_code, theirs_dir)):
        if cached[code]:
            print("Using cached deep data for {}.".format(code))
        else:
            print("Fetching deep data for {}...".format(code))
            heavy_jobs.append(lambda code=code, directory=directory: deep_task(code, directory))

    # World-best is the live input, cached on its OWN TTL (not the report-data cache): reuse an on-disk
    # worldbest.json that's younger than the TTL even across a --refresh, since leaderboards move slowly.
    # Re-fetch only when it's missing, stale, or --refresh-worldbest forces it. This keeps the priciest
    # part of the fetch (≈half the API points) off the repeated dev-loop path.
    wb_age_h = ((time.time() - os.path.getmtime(worldbest_path)) / 3600.0
                if os.path.isfile(worldbest_path) else None)
    if wb_age_h is not None and wb_age_h < args.worldbest_ttl_hours and not args.refresh_worldbest:
        print("Using cached world-best rotations ({:.1f}h old < {:g}h TTL).".format(
            wb_age_h, args.worldbest_ttl_hours))
    else:
        why = "forced" if args.refresh_worldbest else ("missing" if wb_age_h is None
                                                       else "{:.1f}h old".format(wb_age_h))
        print("Fetching same-faction world-best rotations ({})...".format(why))
        heavy_jobs.append(worldbest_task)

    lib.parallel_map(lambda job: job(), heavy_jobs)

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
