"""fetch_report.py - pull everything the deep-dive needs for ONE report into a
per-report folder. Run once per report, then feed both folders to build_deepdive.

    python fetch_report.py --code 1GHrpaNc2YM4hKTJ --out-dir ./data/demo

Writes:
    <out_dir>/fights.json          (boss kills: id, name, encounterID, start/end, size, ilvl)
    <out_dir>/attempts.json        (every boss pull kill+wipe, for per-boss wipe/attempt counts)
    <out_dir>/playerdetails.json   (combatantInfo: gear/enchants/gems, potionUse)
    <out_dir>/boss-<encounterID>.json  (per-kill: buffs + boss debuffs, in one call)
    <out_dir>/consumes-<encounterID>.json  (shared bosses only: per-player buff auras for the
                                            Consumables table — flask/elixir/food/potion presence)
    <out_dir>/timeline-<encounterID>.json  (shared bosses only: exact DPS/HPS-over-time curves,
                                            event-binned into N equal buckets across the fight)
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


def _fetch_per_player_buffs(code, fid, player_ids):
    """Per-player buff coverage for one fight, for the per-player Consumables table.

    Consumables (flask/elixir/food) are applied PRE-PULL and persist, so they generate no
    applybuff events inside the fight window — the events stream misses them. The Buffs *table*
    scoped by `sourceID`, however, sees auras present at pull. We alias one tiny table per player
    into a single request (cheap: ~2 points, sub-second) and keep just name + totalUses per aura."""
    ids = sorted({int(i) for i in player_ids})
    if not ids:
        return {}
    fields = " ".join(
        "p{0}: table(dataType:Buffs, fightIDs:[{1}], sourceID:{0})".format(pid, fid) for pid in ids
    )
    q = "query Q($code:String!){reportData{report(code:$code){" + fields + "}}}"
    rep = lib.invoke_query(q, {"code": code})["reportData"]["report"]
    out = {}
    for pid in ids:
        auras = ((rep.get("p{0}".format(pid)) or {}).get("data") or {}).get("auras") or []
        # Keep guid — elixirs are classified by spell id downstream (WCL renames buffs by effect).
        out[str(pid)] = [{"name": a.get("name"), "guid": a.get("guid"), "uses": int(a.get("totalUses", 0))}
                         for a in auras]
    return out


def _binned_curves(code, fid, start, end, n=40):
    """Exact DPS/HPS-over-time curves for one fight.

    Bins friendly DamageDone / Healing event `amount`s into `n` equal time buckets across the
    fight and divides each by the bucket width -> DPS/HPS per slice. This is computed from events
    on purpose: the cheaper `graph()` endpoint returns an opaque rolling rate (~2x true DPS, and
    the ratio drifts), which would contradict the exact time-weighted Raid DPS shown elsewhere in
    the report. Event-binning matches the table totals, so the timeline stays honest. Both reports
    use the same fixed `n`, so the two curves overlay index-for-index on a 0-100%-of-fight axis."""
    dur = max(1, int(end) - int(start))
    width = dur / n  # ms per bucket

    def curve(dtype):
        buckets = [0.0] * n
        cur = int(start)
        while cur is not None and cur < int(end):
            q = ("query Q($c:String!,$f:[Int]!,$st:Float!,$et:Float!){reportData{report(code:$c){"
                 "events(dataType:" + dtype + ",fightIDs:$f,startTime:$st,endTime:$et,limit:10000)"
                 "{data nextPageTimestamp}}}}")
            ev = lib.invoke_query(q, {"c": code, "f": [fid], "st": cur, "et": int(end)})["reportData"]["report"]["events"]
            for e in ev["data"]:
                amt = e.get("amount") or 0
                bi = int((e["timestamp"] - int(start)) // width)
                buckets[min(max(bi, 0), n - 1)] += amt
            nxt = ev.get("nextPageTimestamp")
            if not nxt or nxt <= cur:
                break
            cur = int(nxt)
        secs = width / 1000.0
        return [round(b / secs) for b in buckets]

    return {"durMs": dur, "n": n, "dps": curve("DamageDone"), "hps": curve("Healing")}


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

    # 1b) Attempt/wipe counts per encounter (one cheap call). killType:Encounters returns every
    #     boss pull (kills AND wipes); `kill` flags which succeeded → wipes = pulls before the kill.
    attempts_q = (
        "query A($code:String!){reportData{report(code:$code){"
        "fights(killType:Encounters){encounterID kill}}}}"
    )
    attempts = lib.invoke_query(attempts_q, {"code": code})
    _save(attempts, os.path.join(out_dir, "attempts.json"))

    # 2) Player details (gear/enchants/gems/potions) across all kills - gear is static,
    #    one call covers the roster.
    pd_q = (
        "query D($code:String!,$f:[Int]!){reportData{report(code:$code){"
        "playerDetails(fightIDs:$f, includeCombatantInfo:true)}}}"
    )
    pd = lib.invoke_query(pd_q, {"code": code, "f": fight_ids})
    _save(pd, os.path.join(out_dir, "playerdetails.json"))
    print("[{}] player details saved".format(code))

    # Actor IDs (for the per-player Consumables table on shared bosses).
    pdd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    player_ids = []
    for rn in ("tanks", "healers", "dps"):
        for p in (pdd.get(rn) or []):
            player_ids.append(p["id"])

    # 3) Per-boss tables (one call per boss via aliases). Shared bosses also pull the
    #    heavy output tables for the Dive Deeper modules.
    for fight in fights:
        fid = int(fight["id"])
        enc = int(fight["encounterID"])
        heavy = enc in full_encounters
        res = lib.invoke_query(FULL_Q if heavy else LITE_Q, {"code": code, "f": [fid]})
        _save(res, os.path.join(out_dir, "boss-{}.json".format(enc)))
        print("[{}]   {}: {} (enc {})".format(code, "FULL" if heavy else "lite", fight["name"], enc))
        # Per-player consumable coverage + DPS/HPS timeline (shared bosses only — coaching detail).
        if heavy:
            ppb = _fetch_per_player_buffs(code, fid, player_ids)
            _save({"perPlayer": ppb}, os.path.join(out_dir, "consumes-{}.json".format(enc)))
            timeline = _binned_curves(code, fid, fight["startTime"], fight["endTime"])
            _save(timeline, os.path.join(out_dir, "timeline-{}.json".format(enc)))

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
