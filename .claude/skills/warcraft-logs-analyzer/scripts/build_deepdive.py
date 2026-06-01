"""build_deepdive.py - tabbed (Overview + Dive Deeper) raid comparison report.
Consumes the folders produced by fetch_report.py plus the two parse files.

    python build_deepdive.py --ours-dir ./data/ours --theirs-dir ./data/demo \\
        --ours-parses ./data/ours-parses.json --theirs-parses ./data/demo-parses.json \\
        --ours-name "Our Raid" --theirs-name "Benchmark" --zone-name "SSC / TK" \\
        --out-file ./reports/deepdive.html

This is a 1:1 port of build-deepdive.ps1 - it emits the identical DATA payload the
self-contained template (templates/report.html) renders.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
from report_common import avg, index_by_encounter, get_fights, read_json, render_report, ssum

_ROLE_LABEL = {"tanks": "tank", "healers": "healer", "dps": "dps"}


# ---------- small JSON-navigation helpers (graceful on missing aliases) ----------
def _auras(report, alias):
    t = report.get(alias)
    if not t:
        return []
    return (t.get("data") or {}).get("auras") or []


def _entries(report, alias):
    t = report.get(alias)
    if not t:
        return []
    return (t.get("data") or {}).get("entries") or []


def _inner_entries(report, alias):
    """Interrupts/Dispels nest as data.entries[0].entries[]."""
    entries = _entries(report, alias)
    if not entries:
        return []
    return entries[0].get("entries") or []


# ---------- COMPOSITION (distinct roster from parses) ----------
def primary_spec_map(idx, enc_ids):
    """Per player across the shared bosses: their most-frequent (primary) spec. Using
    the primary spec — not whatever the first-iterated fight happened to show — makes
    composition counts and buff-provider detection order-independent and robust to
    role/spec switchers (e.g. a Feral druid who bear-tanks one fight as "Guardian" but
    is Feral on the other four reads as Feral)."""
    counts = {}
    for enc in enc_ids:
        if enc not in idx:
            continue
        for p in idx[enc]["players"]:
            if p["spec"]:
                counts.setdefault(p["name"], {})
                counts[p["name"]][p["spec"]] = counts[p["name"]].get(p["spec"], 0) + 1
    # max by count; ties fall to the first spec seen (dict is insertion-ordered)
    return {name: max(c, key=c.get) for name, c in counts.items()}


def get_roster(idx, enc_ids):
    """Roster restricted to the given encounters (the shared bosses), unique by name.
    Spec is the player's PRIMARY (most-frequent) spec; first-seen role wins."""
    primary = primary_spec_map(idx, enc_ids)
    by_name = {}
    for enc in enc_ids:
        if enc not in idx:
            continue
        for p in idx[enc]["players"]:
            if p["name"] not in by_name:
                by_name[p["name"]] = {"name": p["name"], "class": p["class"],
                                      "spec": primary.get(p["name"], p["spec"]), "role": p["role"]}
    return list(by_name.values())


def names_by_role(roster, role):
    return [p["name"] for p in roster if p["role"] == role]


def class_counts(roster):
    by_class = {}
    for p in roster:
        cls = p["class"]
        if cls not in by_class:
            by_class[cls] = {"count": 0, "specs": {}}
        by_class[cls]["count"] += 1
        spec = p["spec"] if p["spec"] else "Unknown"
        by_class[cls]["specs"][spec] = by_class[cls]["specs"].get(spec, 0) + 1
    out = []
    for cls in sorted(by_class):
        specs = [
            {"spec": s, "count": by_class[cls]["specs"][s]}
            for s in sorted(by_class[cls]["specs"], key=lambda s: -by_class[cls]["specs"][s])
        ]
        out.append({"class": cls, "count": by_class[cls]["count"], "specs": specs})
    return out


def has_provider(pairs, cls, spec):
    """Does any (class, primary-spec) pair satisfy this provider check? `pairs` is one
    (class, primary-spec) entry per player, taken from the roster."""
    for c, s in pairs:
        if c == cls:
            if not spec:
                return True
            if s and spec.lower() in s.lower():
                return True
    return False


# High-impact TBC raid contributions: class/spec -> buff/debuff + why it matters.
PROVIDER_CHECKS = [
    {"buff": "Misery", "class": "Priest", "spec": "Shadow", "impact": "+3% spell damage taken by boss, plus a mana battery for casters"},
    {"buff": "Improved Faerie Fire", "class": "Druid", "spec": "Balance", "impact": "+3% spell hit for the whole raid (huge for casters)"},
    {"buff": "Ferocious Inspiration", "class": "Hunter", "spec": "Beast", "impact": "+3% damage to the raid"},
    {"buff": "Trueshot Aura", "class": "Hunter", "spec": "Marksmanship", "impact": "Raid-wide attack power"},
    {"buff": "Expose Weakness", "class": "Hunter", "spec": "Survival", "impact": "Raid-wide attack power from crits"},
    {"buff": "Bloodlust / Heroism", "class": "Shaman", "spec": "", "impact": "+30% raid haste burst window"},
    {"buff": "Windfury Totem", "class": "Shaman", "spec": "Enhancement", "impact": "Big melee damage boost"},
    {"buff": "Improved Scorch (fire)", "class": "Mage", "spec": "Fire", "impact": "+15% fire damage taken by boss"},
    {"buff": "Curse of the Elements", "class": "Warlock", "spec": "", "impact": "+10% spell damage taken by boss"},
    {"buff": "Leader of the Pack", "class": "Druid", "spec": "Feral", "impact": "+5% melee/ranged crit for the raid"},
    {"buff": "Judgement of Wisdom", "class": "Paladin", "spec": "", "impact": "Mana return for the raid"},
    {"buff": "Battle Shout", "class": "Warrior", "spec": "", "impact": "Raid-wide attack power"},
]


# ---------- ENCHANT / GEM / CONSUMABLE AUDIT (from playerDetails) ----------
# Core enchantable slots in TBC (exclude rings = enchanter-only, offhand/ranged = conditional).
ENCH_SLOTS = {0: "Head", 2: "Shoulder", 4: "Chest", 6: "Legs", 7: "Feet", 8: "Wrist", 9: "Hands", 14: "Back", 15: "Weapon"}


def audit_report(directory, allow_names):
    pd = read_json(os.path.join(directory, "playerdetails.json"))
    pd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    # Restrict to the shared-boss roster so the audit matches the Composition view.
    allow = set(allow_names)
    # A player who tanked some fights and DPS'd others appears in BOTH role buckets;
    # dedupe by name (same character = same gear).
    seen = set()
    players = []
    for rn in ("tanks", "healers", "dps"):
        for pl in (pd.get(rn) or []):
            if allow and pl["name"] not in allow:
                continue
            if pl["name"] in seen:
                continue
            seen.add(pl["name"])
            ci = pl.get("combatantInfo")
            gear = (ci.get("gear") if isinstance(ci, dict) else None) or []
            missing = []
            gems = 0
            weapon_oil = False
            for slot in sorted(ENCH_SLOTS):
                item = next((g for g in gear if g.get("slot") == slot), None)
                if item and item.get("id", 0) != 0:
                    if not item.get("permanentEnchant") or int(item.get("permanentEnchant", 0)) == 0:
                        missing.append(ENCH_SLOTS[slot])
                    if slot == 15 and item.get("temporaryEnchant") and int(item.get("temporaryEnchant", 0)) != 0:
                        weapon_oil = True
            for item in gear:
                if item.get("gems"):
                    gems += len(item["gems"])
            players.append({
                "name": pl["name"], "class": pl.get("type"), "role": _ROLE_LABEL[rn],
                "missingEnchants": missing, "missingCount": len(missing), "gems": gems,
                "weaponOil": weapon_oil,
            })
    return {
        "players": players,
        "totalMissingEnchants": ssum([p["missingCount"] for p in players]),
        "playersNoWeaponOil": len([p for p in players if not p["weaponOil"]]),
        "fullyEnchanted": len([p for p in players if p["missingCount"] == 0]),
        "playerCount": len(players),
        "avgGems": avg([p["gems"] for p in players]),
    }


def avg_ilvl(directory, enc_ids):
    fights = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]
    enc_set = set(enc_ids)
    vals = [float(f["averageItemLevel"]) for f in fights
            if str(f["encounterID"]) in enc_set and float(f["averageItemLevel"]) > 0]
    if not vals:
        return 0
    return round(sum(vals) / len(vals), 1)


# ---------- PER-BOSS BUFF/DEBUFF UPTIME + LUST TIMING ----------
def fight_map(directory):
    m = {}
    for f in read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]:
        m[str(f["encounterID"])] = {
            "start": int(f["startTime"]), "end": int(f["endTime"]),
            "phases": f.get("phaseTransitions") or [], "ilvl": float(f["averageItemLevel"]),
        }
    return m


KEY_BUFFS = ["Bloodlust", "Heroism", "Battle Shout", "Blessing of Kings", "Gift of the Wild",
             "Ferocious Inspiration", "Leader of the Pack", "Drums of Battle", "Arcane Brilliance", "Windfury"]
KEY_DEBUFFS = ["Sunder Armor", "Expose Armor", "Curse of the Elements", "Faerie Fire", "Misery",
               "Judgement of Wisdom", "Judgement of the Crusader", "Demoralizing Shout"]


def uptime_pct(auras, name, dur_ms):
    if dur_ms <= 0:
        return None
    a = next((x for x in auras if x.get("name") == name), None)
    if not a:
        return 0
    return min(100, round(float(a["totalUptime"]) / dur_ms * 100))


def lust_sec(auras, fight_start):
    a = next((x for x in auras if x.get("name") in ("Bloodlust", "Heroism")), None)
    if not a or not a.get("bands"):
        return None
    first = min(a["bands"], key=lambda b: b["startTime"])["startTime"]
    return round((int(first) - int(fight_start)) / 1000)


def load_boss(directory, enc):
    p = os.path.join(directory, "boss-{}.json".format(enc))
    if not os.path.isfile(p):
        return None
    return read_json(p)["reportData"]["report"]


# --- Dive Deeper output-quality extractors (heavy tables) ---
def activity_pct(report, dur, dps_names):
    if not report.get("dd") or dur <= 0:
        return None
    es = [e for e in _entries(report, "dd") if e.get("name") in dps_names]
    if not es:
        return None
    return avg([min(100, float(e["activeTime"]) / dur * 100) for e in es])


def overheal_pct(report, healer_names):
    if not report.get("heal"):
        return None
    vals = []
    for e in [x for x in _entries(report, "heal") if x.get("name") in healer_names]:
        den = float(e.get("total", 0)) + float(e.get("overheal", 0))
        if den > 0:
            vals.append(float(e.get("overheal", 0)) / den * 100)
    if not vals:
        return None
    return avg(vals)


def dmg_taken_ex_tanks(report, tank_names):
    if not report.get("dt"):
        return None
    return ssum([int(e["total"]) for e in _entries(report, "dt") if e.get("name") not in tank_names])


def dtps(dmg, dur_ms):
    """Damage-taken per second - normalizes for kill time so slower fights aren't penalized."""
    if dmg is None or dur_ms <= 0:
        return None
    return round(float(dmg) * 1000 / dur_ms)


def ability_agg(report, tank_names):
    agg = {}
    if not report.get("dt"):
        return agg
    for e in [x for x in _entries(report, "dt") if x.get("name") not in tank_names]:
        for a in (e.get("abilities") or []):
            agg[a["name"]] = agg.get(a["name"], 0) + int(a["total"])
    return agg


def dmg_compare(o_report, o_tank, t_report, t_tank, n):
    """Unified per-ability damage-taken comparison: union of both raids' sources, top N."""
    oa = ability_agg(o_report, o_tank)
    ta = ability_agg(t_report, t_tank)
    names = sorted(set(oa) | set(ta))
    rows = [{"name": nm, "ours": int(oa.get(nm, 0)), "theirs": int(ta.get(nm, 0))} for nm in names]
    rows.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    return rows[:n]


def count_actions(report, alias):
    """Interrupts/Dispels nest as data.entries[0].entries[] (by ability)."""
    inner = _inner_entries(report, alias)
    if not inner:
        return 0
    c = 0
    for ab in inner:
        if not ab:
            continue
        if ab.get("details"):
            for d in ab["details"]:
                c += int(d.get("total", 0))
        elif ab.get("total") is not None:
            c += int(ab["total"])
    return c


def int_break(report, spec_map):
    """Interrupts breakdown: which enemy casts got interrupted, and by which class."""
    abil = {}
    grp = {}
    for ab in _inner_entries(report, "intr"):
        if not ab or not ab.get("name"):
            continue
        an = str(ab["name"])
        for d in (ab.get("details") or []):
            if not d:
                continue
            c = int(d.get("total", 0))
            abil[an] = abil.get(an, 0) + c
            cls = str(d["type"]) if d.get("type") else "Unknown"
            spec = str(spec_map.get(str(d.get("name")), "")) if d.get("name") else ""
            key = "{}|{}".format(spec, cls)
            if key not in grp:
                grp[key] = {"spec": spec, "class": cls, "count": 0}
            grp[key]["count"] += c
    return {"abilities": abil, "groups": grp}


def int_compare(o_report, t_report, o_spec, t_spec):
    o = int_break(o_report, o_spec)
    t = int_break(t_report, t_spec)
    ab_names = sorted(set(o["abilities"]) | set(t["abilities"]))
    abilities = [{"name": n, "ours": int(o["abilities"].get(n, 0)), "theirs": int(t["abilities"].get(n, 0))}
                 for n in ab_names]
    abilities.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    keys = sorted(set(o["groups"]) | set(t["groups"]))
    interrupters = []
    for k in keys:
        og = o["groups"].get(k)
        tg = t["groups"].get(k)
        ref = og if og else tg
        interrupters.append({
            "spec": ref["spec"], "class": ref["class"],
            "ours": int(og["count"]) if og else 0, "theirs": int(tg["count"]) if tg else 0,
        })
    interrupters.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    return {"abilities": abilities, "interrupters": interrupters}


def death_list(report, fight_start):
    """Deaths: name + spec (from icon) + killing blow + when (sec into fight)."""
    out = []
    if not report.get("deaths"):
        return out
    for d in _entries(report, "deaths"):
        if not d or not d.get("name"):
            continue
        kb = str(d["killingBlow"]["name"]) if d.get("killingBlow") and d["killingBlow"].get("name") else "Unknown"
        t = round((int(d["timestamp"]) - int(fight_start)) / 1000)
        out.append({"name": str(d["name"]), "class": str(d.get("type")),
                    "icon": str(d.get("icon")), "killedBy": kb, "tSec": int(t)})
    out.sort(key=lambda x: x["tSec"])
    return out


def disp_list(report):
    """Dispels: which enemy auras the raid dispelled, with counts."""
    m = {}
    for a in _inner_entries(report, "disp"):
        if not a or not a.get("name"):
            continue
        cnt = sum(int(d.get("total", 0)) for d in (a.get("details") or []))
        if not cnt:
            cnt = int(a.get("spellsInterrupted", 0))
        m[str(a["name"])] = int(cnt)
    return m


def disp_compare(o_report, t_report):
    o = disp_list(o_report)
    t = disp_list(t_report)
    names = sorted(set(o) | set(t))
    rows = [{"name": n, "ours": int(o.get(n, 0)), "theirs": int(t.get(n, 0))} for n in names]
    rows.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    return rows


def unkicked_list(report):
    """Interruptible casts that went off un-kicked (raid failed to interrupt).
    Keep only abilities whose un-interrupted casts (missedCasts) have a hostile caster."""
    rows = []
    for a in _inner_entries(report, "intr"):
        if not a:
            continue
        missed = a.get("missedCasts") or []
        hostile = [m for m in missed if m.get("type") in ("NPC", "Boss")]
        if len(missed) > 0 and len(hostile) == 0:
            continue  # friendly-ability noise
        kicked = int(a.get("spellsInterrupted", 0))
        went_off = len(hostile) if len(missed) > 0 else int(a.get("spellsCompleted", 0))
        if (kicked + went_off) <= 0:
            continue
        rows.append({"name": str(a.get("name")), "kicked": kicked, "wentOff": went_off})
    return rows


def unkicked_compare(o_report, t_report):
    o = {r["name"]: r for r in unkicked_list(o_report)}
    t = {r["name"]: r for r in unkicked_list(t_report)}
    names = sorted(set(o) | set(t))
    rows = []
    for n in names:
        oo = o.get(n)
        tt = t.get(n)
        rows.append({
            "name": n,
            "oursKicked": int(oo["kicked"]) if oo else 0, "oursWentOff": int(oo["wentOff"]) if oo else 0,
            "theirsKicked": int(tt["kicked"]) if tt else 0, "theirsWentOff": int(tt["wentOff"]) if tt else 0,
        })
    rows.sort(key=lambda r: max(r["oursWentOff"], r["theirsWentOff"]), reverse=True)
    return rows


def phase_list(fight_info):
    """Duration of each phase (from phaseTransitions on the fight)."""
    pts = fight_info.get("phases") or []
    if not pts:
        return []
    sorted_pts = sorted(pts, key=lambda p: p["startTime"])
    phases = []
    for i in range(len(sorted_pts)):
        ps = int(sorted_pts[i]["startTime"])
        pe = int(sorted_pts[i + 1]["startTime"]) if i + 1 < len(sorted_pts) else int(fight_info["end"])
        phases.append({"id": int(sorted_pts[i]["id"]), "durMs": pe - ps})
    return phases


def phase_compare(o_info, t_info):
    op = phase_list(o_info)
    tp = phase_list(t_info)
    if not op and not tp:
        return []
    o_by_id = {str(p["id"]): p["durMs"] for p in op}
    t_by_id = {str(p["id"]): p["durMs"] for p in tp}
    ids = sorted(set(o_by_id) | set(t_by_id), key=lambda x: int(x))
    return [{"id": int(i), "oursMs": int(o_by_id.get(i, 0)), "theirsMs": int(t_by_id.get(i, 0))} for i in ids]


# ---------- CLEAR EFFICIENCY (wall-clock vs in-combat) ----------
def efficiency(directory):
    fights = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]
    first = min(int(f["startTime"]) for f in fights)
    last = max(int(f["endTime"]) for f in fights)
    combat = ssum([int(f["endTime"]) - int(f["startTime"]) for f in fights])
    span = last - first
    return {"spanMs": span, "combatMs": combat, "downtimeMs": span - combat, "kills": len(fights)}


# ---------- ASSEMBLE ----------
def build(ours_dir, theirs_dir, ours_parses, theirs_parses, out_file,
          ours_name="Our Raid", theirs_name="Benchmark", zone_name=""):
    ours_idx = index_by_encounter(get_fights(ours_parses))
    theirs_idx = index_by_encounter(get_fights(theirs_parses))
    common_ids = [k for k in ours_idx if k in theirs_idx]

    bosses = [{"encounterID": int(i), "name": ours_idx[i]["name"], "ours": ours_idx[i], "theirs": theirs_idx[i]}
              for i in common_ids]
    summary = {
        "bossCount": len(bosses),
        "oursAvgParse": avg([b["ours"]["avgParse"] for b in bosses]),
        "theirsAvgParse": avg([b["theirs"]["avgParse"] for b in bosses]),
        "oursDeaths": ssum([b["ours"]["deaths"] for b in bosses]),
        "theirsDeaths": ssum([b["theirs"]["deaths"] for b in bosses]),
        "oursDurationMs": ssum([b["ours"]["durationMs"] for b in bosses]),
        "theirsDurationMs": ssum([b["theirs"]["durationMs"] for b in bosses]),
    }

    # Composition
    ours_roster = get_roster(ours_idx, common_ids)
    theirs_roster = get_roster(theirs_idx, common_ids)
    ours_spec = {p["name"]: p["spec"] for p in ours_roster}
    theirs_spec = {p["name"]: p["spec"] for p in theirs_roster}
    ours_dps = names_by_role(ours_roster, "dps")
    ours_heal = names_by_role(ours_roster, "healer")
    ours_tank = names_by_role(ours_roster, "tank")
    theirs_dps = names_by_role(theirs_roster, "dps")
    theirs_heal = names_by_role(theirs_roster, "healer")
    theirs_tank = names_by_role(theirs_roster, "tank")

    # (class, primary-spec) per player, straight from the roster — so the buff-provider
    # gap status always matches the composition spec counts shown above it.
    ours_pairs = [(p["class"], p["spec"]) for p in ours_roster]
    theirs_pairs = [(p["class"], p["spec"]) for p in theirs_roster]
    gaps = [{"buff": c["buff"], "ours": has_provider(ours_pairs, c["class"], c["spec"]),
             "theirs": has_provider(theirs_pairs, c["class"], c["spec"]), "impact": c["impact"]}
            for c in PROVIDER_CHECKS]
    composition = {
        "oursClasses": class_counts(ours_roster), "theirsClasses": class_counts(theirs_roster),
        "oursSize": len(ours_roster), "theirsSize": len(theirs_roster), "gaps": gaps,
    }

    # Audit
    ours_roster_names = [p["name"] for p in ours_roster]
    theirs_roster_names = [p["name"] for p in theirs_roster]
    audit_ours = audit_report(ours_dir, ours_roster_names)
    audit_theirs = audit_report(theirs_dir, theirs_roster_names)
    audit_ours["avgIlvl"] = avg_ilvl(ours_dir, common_ids)
    audit_theirs["avgIlvl"] = avg_ilvl(theirs_dir, common_ids)
    audit = {"ours": audit_ours, "theirs": audit_theirs}

    # Per-boss
    ours_fights = fight_map(ours_dir)
    theirs_fights = fight_map(theirs_dir)
    per_boss = []
    for b in bosses:
        enc = str(b["encounterID"])
        o_b = load_boss(ours_dir, enc)
        t_b = load_boss(theirs_dir, enc)
        if not o_b or not t_b:
            continue
        o_dur = ours_fights[enc]["end"] - ours_fights[enc]["start"]
        t_dur = theirs_fights[enc]["end"] - theirs_fights[enc]["start"]

        buff_rows = []
        for name in KEY_BUFFS:
            if name == "Heroism":
                continue  # folded into Bloodlust row
            o_u = uptime_pct(_auras(o_b, "buffs"), name, o_dur)
            t_u = uptime_pct(_auras(t_b, "buffs"), name, t_dur)
            if o_u == 0 and t_u == 0:
                continue
            buff_rows.append({"name": name, "ours": o_u, "theirs": t_u})
        debuff_rows = []
        for name in KEY_DEBUFFS:
            o_u = uptime_pct(_auras(o_b, "debuffs"), name, o_dur)
            t_u = uptime_pct(_auras(t_b, "debuffs"), name, t_dur)
            if o_u == 0 and t_u == 0:
                continue
            debuff_rows.append({"name": name, "ours": o_u, "theirs": t_u})

        o_dmg = dmg_taken_ex_tanks(o_b, ours_tank)
        t_dmg = dmg_taken_ex_tanks(t_b, theirs_tank)
        per_boss.append({
            "encounterID": b["encounterID"], "name": b["name"],
            "oursLustSec": lust_sec(_auras(o_b, "buffs"), ours_fights[enc]["start"]),
            "theirsLustSec": lust_sec(_auras(t_b, "buffs"), theirs_fights[enc]["start"]),
            "buffs": buff_rows, "debuffs": debuff_rows,
            "oursActivity": activity_pct(o_b, o_dur, ours_dps), "theirsActivity": activity_pct(t_b, t_dur, theirs_dps),
            "oursOverheal": overheal_pct(o_b, ours_heal), "theirsOverheal": overheal_pct(t_b, theirs_heal),
            "oursDmgTaken": o_dmg, "theirsDmgTaken": t_dmg,
            "oursDurMs": o_dur, "theirsDurMs": t_dur,
            "oursDtps": dtps(o_dmg, o_dur), "theirsDtps": dtps(t_dmg, t_dur),
            "dmgCompare": dmg_compare(o_b, ours_tank, t_b, theirs_tank, 7),
            "oursInterrupts": count_actions(o_b, "intr"), "theirsInterrupts": count_actions(t_b, "intr"),
            "oursDispels": count_actions(o_b, "disp"), "theirsDispels": count_actions(t_b, "disp"),
            "interrupts": int_compare(o_b, t_b, ours_spec, theirs_spec),
            "unkicked": unkicked_compare(o_b, t_b),
            "dispelsList": disp_compare(o_b, t_b),
            "deaths": {"ours": death_list(o_b, ours_fights[enc]["start"]),
                       "theirs": death_list(t_b, theirs_fights[enc]["start"])},
            "phases": phase_compare(ours_fights[enc], theirs_fights[enc]),
        })

    # Overall DTPS is time-weighted (total damage / total fight time).
    o_dmg_sum = ssum([p["oursDmgTaken"] for p in per_boss])
    o_dur_sum = ssum([p["oursDurMs"] for p in per_boss])
    t_dmg_sum = ssum([p["theirsDmgTaken"] for p in per_boss])
    t_dur_sum = ssum([p["theirsDurMs"] for p in per_boss])
    quality = {
        "oursActivity": avg([p["oursActivity"] for p in per_boss]),
        "theirsActivity": avg([p["theirsActivity"] for p in per_boss]),
        "oursOverheal": avg([p["oursOverheal"] for p in per_boss]),
        "theirsOverheal": avg([p["theirsOverheal"] for p in per_boss]),
        "oursDmgTaken": o_dmg_sum, "theirsDmgTaken": t_dmg_sum,
        "oursDtps": round(o_dmg_sum * 1000 / o_dur_sum) if o_dur_sum > 0 else 0,
        "theirsDtps": round(t_dmg_sum * 1000 / t_dur_sum) if t_dur_sum > 0 else 0,
        "oursInterrupts": ssum([p["oursInterrupts"] for p in per_boss]),
        "theirsInterrupts": ssum([p["theirsInterrupts"] for p in per_boss]),
        "oursDispels": ssum([p["oursDispels"] for p in per_boss]),
        "theirsDispels": ssum([p["theirsDispels"] for p in per_boss]),
    }

    eff = {"ours": efficiency(ours_dir), "theirs": efficiency(theirs_dir)}

    payload = {
        "zone": zone_name, "ours": {"title": ours_name}, "theirs": {"title": theirs_name},
        "summary": summary, "bosses": bosses,
        "deep": {"composition": composition, "audit": audit, "quality": quality, "perBoss": per_boss, "efficiency": eff},
    }
    out_full = render_report(payload, out_file)
    print("Deep-dive report written to {} ({} shared bosses, {} with buff/debuff data)".format(
        out_full, len(bosses), len(per_boss)))
    return out_full


def main(argv=None):
    p = argparse.ArgumentParser(description="Build the tabbed deep-dive comparison report.")
    p.add_argument("--ours-dir", required=True)
    p.add_argument("--theirs-dir", required=True)
    p.add_argument("--ours-parses", required=True)
    p.add_argument("--theirs-parses", required=True)
    p.add_argument("--ours-name", default="Our Raid")
    p.add_argument("--theirs-name", default="Benchmark")
    p.add_argument("--zone-name", default="")
    p.add_argument("--out-file", required=True)
    args = p.parse_args(argv)
    build(args.ours_dir, args.theirs_dir, args.ours_parses, args.theirs_parses, args.out_file,
          args.ours_name, args.theirs_name, args.zone_name)


if __name__ == "__main__":
    main()
