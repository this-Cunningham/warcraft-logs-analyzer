"""fetch_report.py - pull everything the deep-dive needs for ONE report into a
per-report folder. Run once per report, then feed both folders to build_deepdive.

    python fetch_report.py --code 1GHrpaNc2YM4hKTJ --out-dir ./data/demo

Writes:
    <out_dir>/fights.json          (boss kills: id, name, encounterID, start/end, size, ilvl)
    <out_dir>/attempts.json        (every boss pull kill+wipe, for per-boss wipe/attempt counts)
    <out_dir>/wipe-deaths.json     (shared bosses only: friendly Deaths table on the WIPE pulls — powers
                                    the Wipes tab's "what ends your attempts": first death + killing blows)
    <out_dir>/playerdetails.json   (combatantInfo: gear/enchants/gems, potionUse)
    <out_dir>/boss-<encounterID>.json  (per-kill: buffs + boss debuffs, in one call)
    <out_dir>/consumes-<encounterID>.json  (shared bosses only: per-player buff auras for the
                                            Consumables table — flask/elixir/food/potion presence)
    <out_dir>/timeline-<encounterID>.json  (shared bosses only: exact DPS/HPS-over-time curves,
                                            event-binned into N equal buckets across the fight)
    <out_dir>/incombat-<encounterID>.json  (shared bosses only: per-source mana-potion/healthstone cast
                                            counts from cast EVENTS — the Casts table caps at 5 abilities)
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
    "threat: table(dataType:Threat, fightIDs:$f) "
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
    """Exact DPS/HPS-over-time curves for one fight, plus FOCUS-FIRE concentration (free — same pull).

    Bins friendly DamageDone / Healing event `amount`s into `n` equal time buckets across the
    fight and divides each by the bucket width -> DPS/HPS per slice. This is computed from events
    on purpose: the cheaper `graph()` endpoint returns an opaque rolling rate (~2x true DPS, and
    the ratio drifts), which would contradict the exact time-weighted Raid DPS shown elsewhere in
    the report. Event-binning matches the table totals, so the timeline stays honest. Both reports
    use the same fixed `n`, so the two curves overlay index-for-index on a 0-100%-of-fight axis.

    The DamageDone events already carry `targetID`, so for **no extra API cost** we also bin damage
    per target → focus concentration: in each slice, the share of raid damage on the single
    most-damaged enemy (high = focused fire, low = damage split across targets). Used only on
    multi-target fights (single-target fights are ~100% by definition and carry no signal)."""
    dur = max(1, int(end) - int(start))
    width = dur / n  # ms per bucket

    def curve(dtype, with_focus=False):
        buckets = [0.0] * n
        by_source = {}  # sourceID -> [raw amount per bin]; powers the PER-SPEC timeline curves (build
                        # folds pets into owners, maps owner -> spec, and pools). No extra API cost —
                        # the same event sweep already carries sourceID on every damage/heal event.
        tgt_bucket = [dict() for _ in range(n)] if with_focus else None  # bucket -> {targetID: dmg}
        tgt_total = {} if with_focus else None                          # targetID -> total dmg (whole fight)
        tgt_inst = {} if with_focus else None  # (targetID,targetInstance) -> [firstTs, lastTs] for add lifespans
        cur = int(start)
        while cur is not None and cur < int(end):
            q = ("query Q($c:String!,$f:[Int]!,$st:Float!,$et:Float!){reportData{report(code:$c){"
                 "events(dataType:" + dtype + ",fightIDs:$f,startTime:$st,endTime:$et,limit:10000)"
                 "{data nextPageTimestamp}}}}")
            ev = lib.invoke_query(q, {"c": code, "f": [fid], "st": cur, "et": int(end)})["reportData"]["report"]["events"]
            for e in ev["data"]:
                amt = e.get("amount") or 0
                bi = min(max(int((e["timestamp"] - int(start)) // width), 0), n - 1)
                buckets[bi] += amt
                if amt:
                    sid = e.get("sourceID")
                    if sid is not None:
                        arr = by_source.get(sid)
                        if arr is None:
                            arr = by_source[sid] = [0.0] * n
                        arr[bi] += amt
                if with_focus and amt:
                    tid = e.get("targetID")
                    if tid is not None:
                        tgt_bucket[bi][tid] = tgt_bucket[bi].get(tid, 0) + amt
                        tgt_total[tid] = tgt_total.get(tid, 0) + amt
                        ts = e["timestamp"]
                        sp = tgt_inst.get((tid, e.get("targetInstance")))
                        if sp is None:
                            tgt_inst[(tid, e.get("targetInstance"))] = [ts, ts]
                        elif ts < sp[0]:
                            sp[0] = ts
                        elif ts > sp[1]:
                            sp[1] = ts
            nxt = ev.get("nextPageTimestamp")
            if not nxt or nxt <= cur:
                break
            cur = int(nxt)
        secs = width / 1000.0
        rates = [round(b / secs) for b in buckets]
        # Per-source RAW sums (build divides by `secs` after folding pets into owners).
        src_raw = {str(sid): [round(x) for x in arr] for sid, arr in by_source.items()}
        if not with_focus:
            return rates, None, src_raw
        # Per-slice focus concentration = top target's share of that slice's damage.
        conc = []
        for tb in tgt_bucket:
            tot = sum(tb.values())
            conc.append(round(100 * max(tb.values()) / tot) if tot > 0 else None)
        grand = sum(tgt_total.values()) or 1
        top_overall = (max(tgt_total.values()) / grand) if tgt_total else 1.0
        n_sig = sum(1 for v in tgt_total.values() if v / grand >= 0.05)  # enemies taking >=5% of damage
        focus = {"conc": conc, "topShareOverall": round(100 * top_overall), "distinctTargets": n_sig,
                 "multiTarget": top_overall < 0.80 and n_sig >= 2}
        # Per-target damage spans → add lifespans (first-hit to last-hit per instance) + the add's
        # first-appearance time (earliest first-hit, relative to pull) for "when did it spawn/engage".
        # The build side names each target via masterData, drops the boss by name, and keeps the rest.
        spans = {}
        for (tid, _inst), (f, l) in tgt_inst.items():
            s = spans.setdefault(str(tid), {"dmg": int(tgt_total.get(tid, 0)), "lifespans": [], "firstSec": None})
            s["lifespans"].append(round((l - f) / 1000.0, 1))
            fsec = round((f - int(start)) / 1000.0, 1)
            if s["firstSec"] is None or fsec < s["firstSec"]:
                s["firstSec"] = fsec
        focus["targetSpans"] = spans
        return rates, focus, src_raw

    dps, focus, dps_src = curve("DamageDone", with_focus=True)
    hps, _, hps_src = curve("Healing")
    return {"durMs": dur, "n": n, "dps": dps, "hps": hps, "focus": focus,
            "dpsBySource": dps_src, "hpsBySource": hps_src}


# IN-COMBAT instant consumables (super mana potion, healthstone) log as CASTS, not buffs. The Casts
# TABLE caps each player at their top-5 abilities — which truncates these low-count casts off the bottom
# for almost everyone — so we read them from cast EVENTS (untruncated) instead. Classified by ability
# NAME (rank-proof): a mana potion casts "Restore Mana" (multiple item ranks share that one name), a
# healthstone "… Healthstone". "Replenish Mana" (the Mage Mana Gem) is a class ability and stays excluded
# by name. Events carry only an abilityGameID, so we resolve it to a name via masterData.abilities.
INCOMBAT_MANA_NAMES = {"Restore Mana"}
ABILITIES_Q = "query AB($code:String!){reportData{report(code:$code){masterData{abilities{gameID name}}}}}"


def _ability_names(code):
    """{abilityGameID(int) -> name} for the report, from masterData. Lets us classify cast EVENTS (which
    carry only the numeric abilityGameID) by ability name. One cheap call per report."""
    ab = (((lib.invoke_query(ABILITIES_Q, {"code": code}).get("reportData") or {}).get("report") or {})
          .get("masterData") or {}).get("abilities") or []
    return {int(a["gameID"]): a.get("name") for a in ab if a.get("gameID") is not None}


def _incombat_casts(code, fid, start, end, ability_names, cap_pages=20):
    """Per-source IN-COMBAT consumable cast counts {sourceID(str): {"MP","HS"}} for one shared boss, from
    cast EVENTS (sweeping the whole fight, paginated). Buckets each cast's abilityGameID->name: a mana
    potion's "Restore Mana" -> MP, any "Healthstone" -> HS, by sourceID. Untruncated, unlike the 5-ability
    Casts TABLE that hid these. Health potions are deliberately NOT tracked (unused in TBC raids)."""
    out = {}
    cur = int(start)
    q = ("query IC($c:String!,$f:[Int]!,$s:Float!,$e:Float!){reportData{report(code:$c){"
         "events(dataType:Casts,fightIDs:$f,startTime:$s,endTime:$e,limit:10000){data nextPageTimestamp}}}}")
    for _ in range(cap_pages):
        ev = lib.invoke_query(q, {"c": code, "f": [fid], "s": cur, "e": int(end)})["reportData"]["report"]["events"]
        for e in (ev.get("data") or []):
            g = e.get("abilityGameID")
            if g is None:
                continue
            nm = ability_names.get(int(g))
            if not nm:
                continue
            if nm in INCOMBAT_MANA_NAMES:
                key = "MP"
            elif "Healthstone" in nm:
                key = "HS"
            else:
                continue
            sid = e.get("sourceID")
            if sid is None:
                continue
            rec = out.setdefault(str(sid), {"MP": 0, "HS": 0})
            rec[key] += 1
        nxt = ev.get("nextPageTimestamp")
        if not nxt or nxt <= cur:
            break
        cur = int(nxt)
    return out


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


def _fetch_attempts(code, out_dir, full_set):
    """Attempt/wipe counts per encounter + the wipe-DEATHS table for shared-boss wipes. Independent of
    the boss/trash/player fetches, so it runs as its own parallel task. Returns a log line."""
    # killType:Encounters returns every boss pull (kills AND wipes); `kill` flags which succeeded →
    # wipes = pulls before the kill. `fightPercentage` (boss HP% remaining at wipe) + `lastPhase` ride
    # along for WIPE DEPTH — how far the best attempt got ("best Kael'thas: 21.6%, P5").
    attempts_q = (
        "query A($code:String!){reportData{report(code:$code){"
        "fights(killType:Encounters){id encounterID kill startTime endTime fightPercentage lastPhase}}}}"
    )
    attempts = lib.invoke_query(attempts_q, {"code": code})
    _save(attempts, os.path.join(out_dir, "attempts.json"))

    # Wipe DEATHS (shared bosses only): the friendly Deaths table for the WIPE pulls — the data behind
    # "what ends your attempts" on the Wipes tab (first death + killing blows per wipe). ONE cheap call
    # across every shared-boss wipe fight (entries carry `fight` + `timestamp` + killingBlow, so we
    # bucket to pulls client-side). Graceful: no wipes on the shared bosses → an empty file.
    if not full_set:
        return None
    att_fights = attempts["reportData"]["report"]["fights"]
    wipe_fights = [f for f in att_fights
                   if not f.get("kill") and int(f.get("encounterID") or 0) in full_set]
    wipe_fids = [int(f["id"]) for f in wipe_fights]
    wd_entries = []
    if wipe_fids:
        wd_q = ("query WD($code:String!,$f:[Int]!){reportData{report(code:$code){"
                "table(dataType:Deaths, fightIDs:$f, hostilityType:Friendlies)}}}")
        wd = lib.invoke_query(wd_q, {"code": code, "f": wipe_fids})["reportData"]["report"]["table"]
        wd_entries = ((wd or {}).get("data") or {}).get("entries") or []
    _save({"wipeFights": wipe_fights, "deaths": wd_entries},
          os.path.join(out_dir, "wipe-deaths.json"))
    return "[{}] wipe deaths: {} shared-boss wipe fights, {} deaths".format(
        code, len(wipe_fids), len(wd_entries))


def _fetch_one_boss(code, out_dir, fight, full_encounters, player_ids, ability_names):
    """Fetch + save everything for ONE boss kill: its buff/debuff (and, for shared bosses, heavy output)
    table, plus the per-player consumables, DPS/HPS timeline, and in-combat-cast files. Each boss writes
    only its own boss-<enc>/consumes-<enc>/timeline-<enc>/incombat-<enc> files, so bosses are fully
    independent and run in parallel. Returns a log line."""
    fid = int(fight["id"])
    enc = int(fight["encounterID"])
    heavy = enc in full_encounters
    res = lib.invoke_query(FULL_Q if heavy else LITE_Q, {"code": code, "f": [fid]})
    _save(res, os.path.join(out_dir, "boss-{}.json".format(enc)))
    if heavy:
        ppb = _fetch_per_player_buffs(code, fid, player_ids)
        _save({"perPlayer": ppb}, os.path.join(out_dir, "consumes-{}.json".format(enc)))
        timeline = _binned_curves(code, fid, fight["startTime"], fight["endTime"])
        _save(timeline, os.path.join(out_dir, "timeline-{}.json".format(enc)))
        # In-combat mana-potion / healthstone usage, per source actor id, from cast EVENTS (untruncated;
        # the Casts table caps each player at 5 abilities, hiding these). Read by per_player_incombat.
        incombat = _incombat_casts(code, fid, fight["startTime"], fight["endTime"], ability_names)
        _save({"perSource": incombat}, os.path.join(out_dir, "incombat-{}.json".format(enc)))
    return "[{}]   {}: {} (enc {})".format(code, "FULL" if heavy else "lite", fight["name"], enc)


def fetch(code, out_dir, full_encounters=None):
    """Fetch fights, player details, and per-boss tables for one report code.

    The independent network calls run concurrently (lib.parallel_map): boss kills come first because
    everything else needs the fight list, then player-details + the ability map are fetched together,
    and finally every per-boss table, the attempts/wipe data, and the trash sweep all fan out at once.
    The files written and their contents are identical to the old serial path — only the wall-clock
    wait shrinks. The global request semaphore in lib caps total in-flight requests."""
    full_encounters = set(int(e) for e in (full_encounters or []))
    os.makedirs(out_dir, exist_ok=True)

    # 1) Boss kills (phaseTransitions ride along here - cheap, used by the Phases view).
    #    `report.phases` rides along too: it carries the human PHASE NAMES (PhaseMetadata) that
    #    phaseTransitions lacks — populated in TBC for scripted multi-phase bosses (e.g. Kael'thas
    #    "P5: Gravity Lapse"). Maps phase id -> name for the Phases view, death timing, and wipe depth.
    #    Must be first: the fight list drives every fetch below.
    kills_q = (
        "query K($code:String!){reportData{report(code:$code){title "
        "fights(killType:Kills){id name encounterID difficulty startTime endTime "
        "size averageItemLevel gameZone{id name} phaseTransitions{id startTime}} "  # gameZone: which zone each kill was in (Trash zone filter)
        "phases{encounterID separatesWipes phases{id name isIntermission}} "
        "masterData{npcs: actors(type:\"NPC\"){id gameID name} "
        "pets: actors(type:\"Pet\"){id petOwner}}}}}"  # pet->owner: fold pet damage into the owner's spec
    )
    kills = lib.invoke_query(kills_q, {"code": code})
    _save(kills, os.path.join(out_dir, "fights.json"))
    fights = kills["reportData"]["report"]["fights"]
    fight_ids = [int(f["id"]) for f in fights]
    print("[{}] {} boss kills".format(code, len(fights)))

    # 2) Player details + ability map — both feed the heavy per-boss subtasks (player_ids for the
    #    per-player consumables table; ability_names for classifying in-combat cast events), so fetch
    #    them before the boss loop. They're independent of each other → run as a 2-way parallel batch.
    pd_q = (
        "query D($code:String!,$f:[Int]!){reportData{report(code:$code){"
        "playerDetails(fightIDs:$f, includeCombatantInfo:true)}}}"
    )

    def get_pd():
        pd = lib.invoke_query(pd_q, {"code": code, "f": fight_ids})
        _save(pd, os.path.join(out_dir, "playerdetails.json"))
        return pd

    # Ability id -> name map only matters when there are heavy bosses to sweep.
    pd, ability_names = lib.parallel_map(
        lambda f: f(), (get_pd, (lambda: _ability_names(code) if full_encounters else {})))
    print("[{}] player details saved".format(code))

    # Actor IDs (for the per-player Consumables table on shared bosses).
    pdd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    player_ids = []
    for rn in ("tanks", "healers", "dps"):
        for p in (pdd.get(rn) or []):
            player_ids.append(p["id"])

    # 3) Everything left is independent — fan it all out at once: the attempts/wipe data, every per-boss
    #    table (+ heavy subtasks), and the trash sweep. Tasks return a log line (or None); we print them
    #    after the join so the per-report output stays grouped and readable.
    tasks = [lambda: _fetch_attempts(code, out_dir, full_encounters)]
    tasks += [(lambda fight=fight: _fetch_one_boss(
        code, out_dir, fight, full_encounters, player_ids, ability_names)) for fight in fights]
    tasks.append(lambda: fetch_trash(code, out_dir) or None)

    for line in lib.parallel_map(lambda t: t(), tasks):
        if line:
            print(line)

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
