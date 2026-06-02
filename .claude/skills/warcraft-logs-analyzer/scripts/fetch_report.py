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
    <out_dir>/trash.json           (trash pull segments + NPC name master data, for the Trash tab)
    <out_dir>/trash-deaths.json    (enemy kill-order events + player death entries on trash)
    <out_dir>/trash-cc.json        (hard-CC aura table + per-mob CC apply events on trash)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib
import report_common

# Cheap call: buffs + boss debuffs only.
LITE_Q = (
    "query F($code:String!,$f:[Int]!){reportData{report(code:$code){"
    "buffs: table(dataType:Buffs, fightIDs:$f) "
    "debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies)}}}"
)
# Heavy call (shared bosses): adds the output tables for the Dive Deeper modules.
# `casts` powers the Cooldown Usage + Rotation (ability-mix) views — it carries every ability a player
# cast (incl. non-damaging cooldowns/trinkets the DamageDone table can't show), with a per-ability count.
FULL_Q = (
    "query F($code:String!,$f:[Int]!){reportData{report(code:$code){"
    "buffs: table(dataType:Buffs, fightIDs:$f) "
    "debuffs: table(dataType:Debuffs, fightIDs:$f, hostilityType:Enemies) "
    "dd: table(dataType:DamageDone, fightIDs:$f) "
    "heal: table(dataType:Healing, fightIDs:$f) "
    "dt: table(dataType:DamageTaken, fightIDs:$f) "
    "intr: table(dataType:Interrupts, fightIDs:$f) "
    "disp: table(dataType:Dispels, fightIDs:$f) "
    "casts: table(dataType:Casts, fightIDs:$f) "
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


# Trash structure: every trash pull segment (with the NPCs in it) + the NPC name master data,
# in one cheap call. WCL already splits trash into discrete pulls; enemyNPCs carries the report
# actor id + game id + how many of each mob, and masterData resolves those ids to names.
TRASH_STRUCT_Q = (
    "query TR($code:String!){reportData{report(code:$code){"
    "fights(killType:Trash){id name startTime endTime gameZone{id name} enemyNPCs{id gameID instanceCount}} "
    "masterData{actors(type:\"Player\"){id name} npcs: actors(type:\"NPC\"){id gameID name}}}}}"
)


def _events_all(code, fids, tmin, tmax, data_type, hostility, ability_id=None, keep_type=None, cap_pages=12):
    """Pull every matching event across all the given fights in one (paginated) sweep. Each event
    carries its `fight` id, so a single call covers all trash and we bucket by fight client-side."""
    out = []
    start = tmin
    extra = ",abilityID:{}".format(ability_id) if ability_id is not None else ""
    q = ("query E($code:String!,$f:[Int]!,$s:Float!,$e:Float!){reportData{report(code:$code){"
         "events(dataType:" + data_type + ",hostilityType:" + hostility +
         ",fightIDs:$f,startTime:$s,endTime:$e,limit:5000" + extra + "){data nextPageTimestamp}}}}")
    for _ in range(cap_pages):
        ev = lib.invoke_query(q, {"code": code, "f": fids, "s": start, "e": tmax})["reportData"]["report"]["events"]
        for e in (ev.get("data") or []):
            if keep_type is None or e.get("type") == keep_type:
                out.append({"t": e.get("timestamp"), "targetID": e.get("targetID"),
                            "targetInstance": e.get("targetInstance"),
                            "sourceID": e.get("sourceID"), "fight": e.get("fight")})
        nxt = ev.get("nextPageTimestamp")
        if not nxt:
            break
        start = nxt
    return out


def fetch_trash(code, out_dir):
    """Pull everything the Trash tab needs (on by default). Trash is cheap because deaths/CC come
    back in single paginated events calls keyed by `fight`, not one call per pull. Writes trash.json,
    trash-deaths.json, trash-cc.json. Safe on reports with no trash (writes empty structures)."""
    os.makedirs(out_dir, exist_ok=True)
    struct = lib.invoke_query(TRASH_STRUCT_Q, {"code": code})["reportData"]["report"]
    fights = struct.get("fights") or []
    md = struct.get("masterData") or {}
    _save({"fights": fights, "npcActors": md.get("npcs") or [], "playerActors": md.get("actors") or []},
          os.path.join(out_dir, "trash.json"))
    if not fights:
        _save({"friendly": [], "enemy": []}, os.path.join(out_dir, "trash-deaths.json"))
        _save({"auras": [], "events": {}}, os.path.join(out_dir, "trash-cc.json"))
        print("[{}] no trash segments".format(code))
        return

    fids = [int(f["id"]) for f in fights]
    tmin = min(float(f["startTime"]) for f in fights)
    tmax = max(float(f["endTime"]) for f in fights)

    # Player deaths on trash: the Deaths TABLE gives per-death rows with the killing-blow NAME already
    # resolved (events only carry the ability's game id), plus a timestamp we use to assign each death
    # to its pull. Enemy deaths: EVENTS, for the intra-pack kill order (timestamp + which mob).
    fd_q = ("query FD($code:String!,$f:[Int]!){reportData{report(code:$code){"
            "table(dataType:Deaths,fightIDs:$f,hostilityType:Friendlies)}}}")
    fd = lib.invoke_query(fd_q, {"code": code, "f": fids})["reportData"]["report"]["table"]
    friendly = ((fd or {}).get("data") or {}).get("entries") or []
    enemy = _events_all(code, fids, tmin, tmax, "Deaths", "Enemies", keep_type="death")
    _save({"friendly": friendly, "enemy": enemy}, os.path.join(out_dir, "trash-deaths.json"))

    # Crowd control: the enemy-Debuffs aura table lists every debuff placed on trash mobs; we keep only
    # the hard-CC auras (curated names) and then pull each one's apply events to learn WHICH mob got
    # CC'd, by whom, in which pull. Only a handful of CC spell ids are ever present, so it's cheap.
    cc_q = ("query CC($code:String!,$f:[Int]!){reportData{report(code:$code){"
            "table(dataType:Debuffs,fightIDs:$f,hostilityType:Enemies)}}}")
    cc_tbl = lib.invoke_query(cc_q, {"code": code, "f": fids})["reportData"]["report"]["table"]
    auras = ((cc_tbl or {}).get("data") or {}).get("auras") or []
    cc_auras = [{"name": a.get("name"), "guid": a.get("guid"), "uses": int(a.get("totalUses", 0))}
                for a in auras if report_common.cc_label(a.get("name"))]
    cc_events = {}
    for a in cc_auras:
        gid = a["guid"]
        if gid is None:
            continue
        cc_events[str(int(gid))] = _events_all(
            code, fids, tmin, tmax, "Debuffs", "Enemies",
            ability_id=float(gid), keep_type="applydebuff", cap_pages=6)
    _save({"auras": cc_auras, "events": cc_events}, os.path.join(out_dir, "trash-cc.json"))
    print("[{}] trash: {} pulls, {} enemy kills, {} player deaths, {} CC type(s)".format(
        code, len(fights), len(enemy), len(friendly), len(cc_auras)))


def fetch(code, out_dir, full_encounters=None):
    """Fetch fights, player details, and per-boss tables for one report code."""
    full_encounters = set(int(e) for e in (full_encounters or []))
    os.makedirs(out_dir, exist_ok=True)

    # 1) Boss kills (phaseTransitions ride along here - cheap, used by the Phases view).
    #    `report.phases` rides along too: it carries the human PHASE NAMES (PhaseMetadata) that
    #    phaseTransitions lacks — populated in TBC for scripted multi-phase bosses (e.g. Kael'thas
    #    "P5: Gravity Lapse"). Maps phase id -> name for the Phases view, death timing, and wipe depth.
    kills_q = (
        "query K($code:String!){reportData{report(code:$code){title "
        "fights(killType:Kills){id name encounterID difficulty startTime endTime "
        "size averageItemLevel phaseTransitions{id startTime}} "
        "phases{encounterID separatesWipes phases{id name isIntermission}}}}}"
    )
    kills = lib.invoke_query(kills_q, {"code": code})
    _save(kills, os.path.join(out_dir, "fights.json"))
    fights = kills["reportData"]["report"]["fights"]
    fight_ids = [int(f["id"]) for f in fights]
    print("[{}] {} boss kills".format(code, len(fights)))

    # 1b) Attempt/wipe counts per encounter (one cheap call). killType:Encounters returns every
    #     boss pull (kills AND wipes); `kill` flags which succeeded → wipes = pulls before the kill.
    #     `fightPercentage` (boss HP% remaining at wipe) + `lastPhase` ride along for WIPE DEPTH —
    #     how far the best attempt got, so progression walls surface ("best Kael'thas: 21.6%, P5").
    attempts_q = (
        "query A($code:String!){reportData{report(code:$code){"
        "fights(killType:Encounters){encounterID kill fightPercentage lastPhase}}}}"
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

    # 4) Trash analysis (on by default — cheap, ~7-9 calls). Self-contained so it can also run alone.
    fetch_trash(code, out_dir)

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
    p.add_argument(
        "--trash-only",
        action="store_true",
        help="only (re)fetch the trash files into an existing data folder; skip the boss fetch",
    )
    args = p.parse_args(argv)
    if args.trash_only:
        fetch_trash(args.code, args.out_dir)
    else:
        fetch(args.code, args.out_dir, args.full_encounters)


if __name__ == "__main__":
    main()
