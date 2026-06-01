"""fetch_report.py - pull everything the deep-dive needs for ONE report into a
per-report folder. Run once per report, then feed both folders to build_deepdive.

    python fetch_report.py --code 1GHrpaNc2YM4hKTJ --out-dir ./data/demo

Writes:
    <out_dir>/fights.json          (boss kills: id, name, encounterID, start/end, size, ilvl)
    <out_dir>/playerdetails.json   (combatantInfo: gear/enchants/gems, potionUse)
    <out_dir>/boss-<encounterID>.json  (per-kill: buffs + boss debuffs, in one call)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib

# Cheap call: buffs + boss debuffs only.
LITE_Q = (
    "query F($code:String!,$f:[Int]!){reportData{report(code:$code){"
    "buffs: table(dataType:Buffs, fightIDs:$f) "
    "debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies)}}}"
)
# Heavy call (shared bosses): adds the output tables for the Dive Deeper modules.
FULL_Q = (
    "query F($code:String!,$f:[Int]!){reportData{report(code:$code){"
    "buffs: table(dataType:Buffs, fightIDs:$f) "
    "debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies) "
    "dd: table(dataType:DamageDone, fightIDs:$f) "
    "heal: table(dataType:Healing, fightIDs:$f) "
    "dt: table(dataType:DamageTaken, fightIDs:$f) "
    "intr: table(dataType:Interrupts, fightIDs:$f) "
    "disp: table(dataType:Dispels, fightIDs:$f) "
    "deaths: table(dataType:Deaths, fightIDs:$f)}}}"
)


def _save(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)


def fetch(code, out_dir, full_encounters=None):
    """Fetch fights, player details, and per-boss tables for one report code."""
    full_encounters = set(int(e) for e in (full_encounters or []))
    os.makedirs(out_dir, exist_ok=True)

    # 1) Boss kills (phaseTransitions ride along here - cheap, used by the Phases view).
    kills_q = (
        "query K($code:String!){reportData{report(code:$code){title "
        "fights(killType:Kills){id name encounterID difficulty startTime endTime "
        "size averageItemLevel phaseTransitions{id startTime}}}}}"
    )
    kills = lib.invoke_query(kills_q, {"code": code})
    _save(kills, os.path.join(out_dir, "fights.json"))
    fights = kills["reportData"]["report"]["fights"]
    fight_ids = [int(f["id"]) for f in fights]
    print("[{}] {} boss kills".format(code, len(fights)))

    # 2) Player details (gear/enchants/gems/potions) across all kills - gear is static,
    #    one call covers the roster.
    pd_q = (
        "query D($code:String!,$f:[Int]!){reportData{report(code:$code){"
        "playerDetails(fightIDs:$f, includeCombatantInfo:true)}}}"
    )
    pd = lib.invoke_query(pd_q, {"code": code, "f": fight_ids})
    _save(pd, os.path.join(out_dir, "playerdetails.json"))
    print("[{}] player details saved".format(code))

    # 3) Per-boss tables (one call per boss via aliases). Shared bosses also pull the
    #    heavy output tables for the Dive Deeper modules.
    for fight in fights:
        fid = int(fight["id"])
        enc = int(fight["encounterID"])
        heavy = enc in full_encounters
        res = lib.invoke_query(FULL_Q if heavy else LITE_Q, {"code": code, "f": [fid]})
        _save(res, os.path.join(out_dir, "boss-{}.json".format(enc)))
        print("[{}]   {}: {} (enc {})".format(code, "FULL" if heavy else "lite", fight["name"], enc))

    print("[{}] done -> {}".format(code, out_dir))


def main(argv=None):
    p = argparse.ArgumentParser(description="Fetch one WCL report's deep-dive data.")
    p.add_argument("--code", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument(
        "--full-encounters",
        nargs="*",
        type=int,
        default=[],
        help="encounter IDs that should also pull the heavy output tables (usually shared bosses)",
    )
    args = p.parse_args(argv)
    fetch(args.code, args.out_dir, args.full_encounters)


if __name__ == "__main__":
    main()
