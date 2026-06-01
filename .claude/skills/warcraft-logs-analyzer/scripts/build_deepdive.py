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
import itertools
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
from report_common import avg, cc_label, index_by_encounter, get_fights, read_json, render_report, ssum

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


def spec_comp_diff(ours_roster, theirs_roster):
    """Spec-level roster composition diff for the Composition view, used to highlight unique specs
    in the roster tiles. 'missing' = a (class, spec) the benchmark fielded that we didn't (a comp
    gap); 'edge' = a spec we fielded that they didn't. Counts are taken from the side that has the
    spec. Empty/Unknown specs are skipped so we never invent a phantom 'missing Unknown'. This is a
    roster story, not a per-boss DPS gap — that lives in each boss's DPS-by-spec view."""
    def counts(roster):
        c = {}
        for p in roster:
            sp = p.get("spec")
            if not sp or sp == "Unknown":
                continue
            key = (p["class"], sp)
            c[key] = c.get(key, 0) + 1
        return c
    o, t = counts(ours_roster), counts(theirs_roster)
    missing = [{"class": c, "spec": s, "count": t[(c, s)]} for (c, s) in t if (c, s) not in o]
    edge = [{"class": c, "spec": s, "count": o[(c, s)]} for (c, s) in o if (c, s) not in t]
    # Biggest blocks first, then alphabetical — stable, readable order for the legend counts.
    missing.sort(key=lambda r: (-r["count"], r["class"], r["spec"]))
    edge.sort(key=lambda r: (-r["count"], r["class"], r["spec"]))
    return {"missing": missing, "edge": edge}


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
            weapon_oil = False
            for slot in sorted(ENCH_SLOTS):
                item = next((g for g in gear if g.get("slot") == slot), None)
                if item and item.get("id", 0) != 0:
                    if not item.get("permanentEnchant") or int(item.get("permanentEnchant", 0)) == 0:
                        missing.append(ENCH_SLOTS[slot])
                    if slot == 15 and item.get("temporaryEnchant") and int(item.get("temporaryEnchant", 0)) != 0:
                        weapon_oil = True
            players.append({
                "name": pl["name"], "class": pl.get("type"), "role": _ROLE_LABEL[rn],
                "missingEnchants": missing, "missingCount": len(missing),
                "weaponOil": weapon_oil,
            })
    return {
        "players": players,
        "totalMissingEnchants": ssum([p["missingCount"] for p in players]),
        "playersNoWeaponOil": len([p for p in players if not p["weaponOil"]]),
        "fullyEnchanted": len([p for p in players if p["missingCount"] == 0]),
        "playerCount": len(players),
    }


def avg_ilvl(directory, enc_ids):
    fights = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]
    enc_set = set(enc_ids)
    vals = [float(f["averageItemLevel"]) for f in fights
            if str(f["encounterID"]) in enc_set and float(f["averageItemLevel"]) > 0]
    if not vals:
        return 0
    return round(sum(vals) / len(vals), 1)


# ---------- CONSUMABLE COVERAGE (from the per-boss Buffs tables we already fetch) ----------
# The Buffs table carries consumable auras (flask/food/elixir/drums/potions) with a `totalUses`
# count. For flask/food that's ~one application per player, so totalUses ≈ how many raiders showed
# up consumed. It's raid-AGGREGATE (no per-player breakdown), and it can't tell flask-vs-elixir for
# the same player apart — flask is the headline proxy; elixirs/potions are supplementary.
DRUM_NAMES = {"Drums of Battle", "Drums of War", "Drums of Restoration", "Drums of Speed"}
# WCL names most consumable BUFFS by their effect, not the item — so the name often lacks the words
# "Flask"/"Elixir"/"Potion" (e.g. Flask of Supreme Power → buff "Supreme Power"; Ironshield Potion →
# buff "Ironshield"). We therefore detect by **spell id**, mined from the report data (the benchmark
# — a top guild — carries the full set), with a name fallback for "Flask of …"/"Elixir of …" buffs.
# Combat-potion buff spell ids (verified present in data: Haste/Destruction/Ironshield potions).
POTION_IDS = {28507, 28508, 28515}
# Effect-named flask buffs whose name doesn't start with "Flask of" (vanilla flasks still used in TBC).
FLASK_IDS = {17627, 17628}  # Flask of Distilled Wisdom, Flask of Supreme Power
# "...Elixir" names that aren't stat/battle elixirs — don't count them as raid prep.
ELIXIR_EXCLUDE = {"Noggenfogger Elixir", "Elixir of Camouflage", "Elixir of Water Breathing",
                  "Elixir of Minor Fortitude", "Elixir of Water Walking"}
# TBC lets a player run ONE battle (offensive) + ONE guardian (defensive/utility) elixir at once —
# together they substitute for a flask. Classify by **spell ID**, NOT name: WCL renames buffs and
# most battle elixirs are named by their EFFECT (e.g. "Major Shadow Power", "Healing Power") with no
# "Elixir" in the name, so name-matching silently misses them. It also avoids false positives from
# same-named non-elixirs ("Strength"/"Agility" = scrolls; a +125 "Spell Power" = a proc, not elixir).
# IDs verified against Wowhead (stats imply the category). Extend these sets as new elixirs appear.
ELIXIR_BATTLE_IDS = {
    38954,  # Fel Strength Elixir (+90 AP)
    17539,  # Greater Arcane Elixir (+35 spell dmg)
    33721,  # Adept's Elixir — WCL shows it as "Spellpower Elixir" (+24 spell dmg/heal/crit)
    28491,  # Elixir of Healing Power — buff "Healing Power" (+50 healing)
    28503,  # Elixir of Major Shadow Power — buff "Major Shadow Power" (+55 shadow)
    28497,  # Elixir of Major Agility — buff "Major Agility" (+35 agi, +20 crit)
}
ELIXIR_GUARDIAN_IDS = {
    39627,  # Elixir of Draenic Wisdom (+30 int/spi)
    39625,  # Elixir of Major Fortitude (+250 hp, +10 hp/5)
    11371,  # Gift of Arthas (+10 shadow resist + disease proc) — tooltip says "Guardian Elixir"
}
ELIXIR_IDS = ELIXIR_BATTLE_IDS | ELIXIR_GUARDIAN_IDS
# Name hints, used only as a fallback to type an "Elixir of X" buff whose spell id isn't mapped yet.
_GUARDIAN_NAME_HINTS = ("Fortitude", "Mageblood", "Draenic", "Defense", "Ironskin", "Empowerment", "Earthen")


def _is_elixir(name, guid):
    """An elixir if its spell id is mapped, or (fallback) its name literally says 'Elixir'."""
    if guid is not None and int(guid) in ELIXIR_IDS:
        return True
    return bool(name) and "Elixir" in name and name not in ELIXIR_EXCLUDE


def _elixir_type(name, guid=None):
    """battle | guardian | other. Spell id is authoritative; name is a fallback for unmapped ids."""
    if guid is not None:
        g = int(guid)
        if g in ELIXIR_BATTLE_IDS:
            return "battle"
        if g in ELIXIR_GUARDIAN_IDS:
            return "guardian"
    if name and any(h in name for h in _GUARDIAN_NAME_HINTS):
        return "guardian"
    return "battle"  # unmapped offensive/"Elixir of X" — default to battle


def _consumable_cat(name, guid=None):
    """Bucket a buff aura into a consumable category (or None). Food/drums use their stable names;
    flasks/elixirs/potions are detected by spell id (mined from data) with a "Flask of …"/"Elixir of …"
    name fallback — WCL names many consumable buffs by effect, so name-only matching misses them."""
    g = int(guid) if guid is not None else None
    if (name and name.startswith("Flask of")) or g in FLASK_IDS:
        return "flask"
    if name == "Well Fed":
        return "food"
    if name in DRUM_NAMES:
        return "drums"
    if _is_elixir(name, guid):
        return "elixir"
    if g in POTION_IDS:
        return "potion"
    return None


def consumable_report(directory, enc_ids, roster_size):
    """Raid consumable coverage averaged across the shared bosses. Flask/food counts are capped at
    the roster size (a flasked player shows ~one application). Drums is reported as fight uptime %
    rather than a user count (it's a short re-applied buff)."""
    fm = fight_map(directory)
    # Elixirs are split into battle vs guardian (TBC lets one of each run at once), so the
    # coverage card can show them separately — lumping them mislabels a guardian-heavy raid.
    cat_per_boss = {"flask": [], "food": [], "elixirBattle": [], "elixirGuardian": [], "potion": []}
    drum_upt = []
    for enc in enc_ids:
        rep = load_boss(directory, str(enc))
        if not rep:
            continue
        auras = _auras(rep, "buffs")
        if not auras:
            continue
        info = fm.get(str(enc), {})
        dur = info.get("end", 0) - info.get("start", 0)
        per_cat = {"flask": 0, "food": 0, "elixirBattle": 0, "elixirGuardian": 0, "potion": 0}
        best_drum = 0
        for a in auras:
            cat = _consumable_cat(a.get("name", ""), a.get("guid"))
            if not cat:
                continue
            if cat == "drums":
                if dur > 0:
                    best_drum = max(best_drum, min(100, round(float(a.get("totalUptime", 0)) / dur * 100)))
            elif cat == "elixir":
                key = "elixirGuardian" if _elixir_type(a.get("name", ""), a.get("guid")) == "guardian" else "elixirBattle"
                per_cat[key] += int(a.get("totalUses", 0))
            else:
                per_cat[cat] += int(a.get("totalUses", 0))
        for c in per_cat:
            cat_per_boss[c].append(per_cat[c])
        drum_upt.append(best_drum)

    def iavg(lst, cap=None):
        if not lst:
            return 0
        v = int(round(sum(lst) / len(lst)))
        return min(v, cap) if cap is not None else v

    return {
        "rosterSize": roster_size,
        "flask": iavg(cat_per_boss["flask"], roster_size),
        "food": iavg(cat_per_boss["food"], roster_size),
        "elixirBattle": iavg(cat_per_boss["elixirBattle"]),
        "elixirGuardian": iavg(cat_per_boss["elixirGuardian"]),
        "potions": iavg(cat_per_boss["potion"]),
        "drumsUptime": iavg(drum_upt),
    }


def name_id_map(directory):
    """name -> actor id from playerDetails (first id wins; dual-role chars share one id)."""
    pd = read_json(os.path.join(directory, "playerdetails.json"))
    pd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    m = {}
    for rn in ("tanks", "healers", "dps"):
        for p in (pd.get(rn) or []):
            m.setdefault(p["name"], p["id"])
    return m


def _cell_for(auras):
    """Reduce one player's pull auras on one boss to a consumable cell."""
    flask, battle, guardian, other, food, potions = False, 0, 0, 0, False, 0
    for a in (auras or []):
        nm = a.get("name")
        guid = a.get("guid")
        c = _consumable_cat(nm, guid)
        if c == "flask":
            flask = True
        elif c == "elixir":
            et = _elixir_type(nm, guid)
            if et == "battle":
                battle += 1
            elif et == "guardian":
                guardian += 1
            else:
                other += 1
        elif c == "food":
            food = True
        elif c == "potion":
            potions += int(a.get("uses", 0))
    total_elixirs = battle + guardian + other
    # Consumed = a flask, OR a battle+guardian pair (two distinct elixirs == the pair in TBC).
    consumed = flask or (battle >= 1 and guardian >= 1) or total_elixirs >= 2
    return {"present": True, "flask": flask, "battle": battle >= 1, "guardian": guardian >= 1,
            "food": food, "potions": potions, "consumed": consumed}


def per_player_consumables(directory, idx, enc_ids):
    """Per-player consumable participation as a matrix: one row per player, one column-group per
    shared boss (flask / battle elixir / guardian elixir / food / combat potion). Reads the
    consumes-<enc>.json files (per-player buff auras at pull). Players are sorted worst-prepared
    first (fewest bosses consumed, then fewest fed). Boss columns follow kill order (enc_ids)."""
    name_to_id = name_id_map(directory)
    # Per-boss present rosters + per-player auras.
    boss_meta = []
    boss_auras = {}   # enc -> {name -> auras}
    boss_present = {}  # enc -> set(names)
    for enc in enc_ids:
        path = os.path.join(directory, "consumes-{}.json".format(enc))
        if not os.path.isfile(path):
            continue
        per_player = read_json(path).get("perPlayer") or {}
        present = (idx.get(enc) or {}).get("players") or []
        names = []
        amap = {}
        for pl in present:
            nm = pl["name"]
            if nm in amap:
                continue
            names.append(nm)
            pid = name_to_id.get(nm)
            amap[nm] = per_player.get(str(pid)) if pid is not None else None
        boss_meta.append({"encounterID": int(enc), "name": idx[enc]["name"], "enc": enc})
        boss_auras[enc] = amap
        boss_present[enc] = set(names)

    # Union roster (class/role from first boss that has the player).
    info = {}
    for enc in enc_ids:
        for pl in ((idx.get(enc) or {}).get("players") or []):
            info.setdefault(pl["name"], {"class": pl["class"], "role": pl["role"]})

    players = []
    for nm, meta in info.items():
        cells = {}
        present_n = consumed_n = food_n = 0
        for b in boss_meta:
            enc = b["enc"]
            if nm in boss_present.get(enc, set()):
                cell = _cell_for(boss_auras[enc].get(nm))
                present_n += 1
                consumed_n += 1 if cell["consumed"] else 0
                food_n += 1 if cell["food"] else 0
            else:
                cell = {"present": False}
            cells[str(b["encounterID"])] = cell
        players.append({
            "name": nm, "class": meta["class"], "role": meta["role"], "cells": cells,
            "presentCount": present_n, "consumedCount": consumed_n, "foodCount": food_n,
        })

    # Worst-prepared first: lowest consumed ratio, then lowest food ratio, then name.
    def ratio(a, b):
        return (a / b) if b else 1.0
    players.sort(key=lambda p: (ratio(p["consumedCount"], p["presentCount"]),
                                ratio(p["foodCount"], p["presentCount"]), p["name"]))
    return {"bosses": [{"encounterID": b["encounterID"], "name": b["name"]} for b in boss_meta],
            "players": players}


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


def load_timeline(directory, enc):
    """Event-binned DPS/HPS curves for one boss (None if this data dir predates the feature)."""
    p = os.path.join(directory, "timeline-{}.json".format(enc))
    if not os.path.isfile(p):
        return None
    return read_json(p)


def _marker_pct(ms_into, dur_ms):
    if dur_ms <= 0:
        return None
    return round(max(0.0, min(100.0, ms_into / dur_ms * 100.0)), 1)


def _side_timeline(curves, deaths, lust_sec, dur_ms, fight_info):
    """One raid's timeline: DPS/HPS curves + markers placed as % of its OWN fight, so ours and
    theirs overlay on a shared 0-100% axis even when the two kills differ in length."""
    side = {
        "dps": curves["dps"], "hps": curves["hps"],
        "deaths": [{"pct": _marker_pct(d["tSec"] * 1000, dur_ms), "name": d["name"], "tSec": d["tSec"]}
                   for d in deaths if _marker_pct(d["tSec"] * 1000, dur_ms) is not None],
        "lustPct": _marker_pct((lust_sec or 0) * 1000, dur_ms) if lust_sec is not None else None,
        "phases": [],
    }
    start = int(fight_info["start"])
    for p in sorted(fight_info.get("phases") or [], key=lambda x: x["startTime"]):
        pc = _marker_pct(int(p["startTime"]) - start, dur_ms)
        if pc is not None and pc > 0.5:  # skip the phase-1 boundary sitting at ~0%
            side["phases"].append({"id": int(p["id"]), "pct": pc})
    return side


def timeline_view(o_curves, t_curves, o_deaths, t_deaths, o_lust, t_lust, o_dur, t_dur, o_info, t_info):
    """Per-boss DPS/HPS-over-time comparison. None if either side lacks curve data (older data dir),
    so the template simply omits the Timeline sub-tab rather than rendering an empty chart."""
    if not o_curves or not t_curves:
        return None
    return {
        "n": o_curves.get("n", len(o_curves["dps"])),
        "oursDurMs": int(o_dur), "theirsDurMs": int(t_dur),
        "ours": _side_timeline(o_curves, o_deaths, o_lust, o_dur, o_info),
        "theirs": _side_timeline(t_curves, t_deaths, t_lust, t_dur, t_info),
    }


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


def raid_sum(report, alias):
    """Total of a damage/healing table's entries (raid-wide output for the fight)."""
    return ssum([int(e.get("total", 0)) for e in _entries(report, alias)])


def rate(total, dur_ms):
    """Per-second rate (DPS/HPS) from a raw total and fight duration."""
    if not total or dur_ms <= 0:
        return 0
    return round(float(total) * 1000 / dur_ms)


# ---------- PER-SPEC DPS GAP (bucket the DamageDone table by primary spec) ----------
def spec_dps_buckets(report, spec_map, role_map, class_map, dur_ms):
    """Bucket the DamageDone entries by (class, primary-spec), DPS-role players only.
    Spec/class/role come from the shared-boss roster maps so the buckets line up with the
    Composition view. Each player's DPS is total / fight duration (raid-contribution DPS),
    which keeps it comparable across both raids and lets per-spec averages be apples-to-apples."""
    buckets = {}
    if dur_ms <= 0:
        return buckets
    for e in _entries(report, "dd"):
        nm = e.get("name")
        spec = spec_map.get(nm)
        if not spec or role_map.get(nm) != "dps":
            continue  # only roster DPS players with a known primary spec
        cls = class_map.get(nm) or e.get("type") or "Unknown"
        key = "{}|{}".format(cls, spec)
        b = buckets.setdefault(key, {"class": cls, "spec": spec, "players": []})
        b["players"].append({"name": nm, "dps": rate(int(e.get("total", 0)), dur_ms)})
    return buckets


def spec_gap(o_report, t_report, o_spec, o_role, o_cls, t_spec, t_role, t_cls, o_dur, t_dur):
    """Per-spec DPS comparison for one boss, ranked by the per-player deficit to the
    benchmark's same spec (biggest gap first → lowest-hanging fruit floats to the top).
    Compares AVERAGE DPS per player so a 3-mage vs 2-mage roster is still fair. `both`
    flags specs only one raid brought (a different kind of gap — surfaced as a roster
    story on the Composition tab, not in the per-boss chart)."""
    ob = spec_dps_buckets(o_report, o_spec, o_role, o_cls, o_dur)
    tb = spec_dps_buckets(t_report, t_spec, t_role, t_cls, t_dur)
    rows = []
    for key in set(ob) | set(tb):
        o = ob.get(key)
        t = tb.get(key)
        ref = o or t
        op = o["players"] if o else []
        tp = t["players"] if t else []
        o_avg = round(sum(x["dps"] for x in op) / len(op)) if op else 0
        t_avg = round(sum(x["dps"] for x in tp) / len(tp)) if tp else 0
        rows.append({
            "class": ref["class"], "spec": ref["spec"],
            "oursCount": len(op), "theirsCount": len(tp),
            "oursAvg": o_avg, "theirsAvg": t_avg, "deficit": t_avg - o_avg,
            "both": bool(op) and bool(tp),
        })
    # Same-spec comparisons first (the user's core ask), ranked by biggest per-player deficit;
    # specs only one raid brought fall to the bottom as a secondary "they brought X, you didn't" note.
    rows.sort(key=lambda r: (not r["both"], -r["deficit"]))
    return rows


# ---------- DEATH CAUSES (aggregate killing blows across the shared bosses) ----------
def death_causes(per_boss, side):
    """Aggregate killing-blow names across every shared boss for one side. A blow that recurs
    is a mechanic the raid repeatedly fails. Returns {cause: {count, bosses:set}}."""
    agg = {}
    for pb in per_boss:
        for d in pb["deaths"][side]:
            cause = d.get("killedBy") or "Unknown"
            rec = agg.setdefault(cause, {"count": 0, "bosses": set()})
            rec["count"] += 1
            rec["bosses"].add(pb["name"])
    return agg


def death_cause_compare(per_boss):
    """Ranked ours-vs-theirs death-cause table across the whole shared clear."""
    o = death_causes(per_boss, "ours")
    t = death_causes(per_boss, "theirs")
    rows = []
    for cause in set(o) | set(t):
        oc = o.get(cause, {"count": 0, "bosses": set()})
        tc = t.get(cause, {"count": 0, "bosses": set()})
        rows.append({
            "cause": cause, "ours": oc["count"], "theirs": tc["count"],
            "bosses": sorted(oc["bosses"] or tc["bosses"]),
        })
    # Worst for us first: where we die most (and most relative to the benchmark).
    rows.sort(key=lambda r: (-(r["ours"]), -(r["ours"] - r["theirs"]), -r["theirs"]))
    return rows


# ---------- WIPE / ATTEMPT COUNTS (one cheap query per report) ----------
def attempt_map(directory):
    """encounterID(str) -> {kills, wipes, attempts} from attempts.json. killType:Encounters lists
    every boss pull; `kill` flags the successful one, so wipes = pulls that weren't the kill.
    Graceful (empty) if the file is missing, so older data folders still build."""
    path = os.path.join(directory, "attempts.json")
    if not os.path.isfile(path):
        return {}
    fights = read_json(path)["reportData"]["report"]["fights"]
    out = {}
    for f in fights:
        enc = str(f.get("encounterID"))
        if not enc or enc == "0":
            continue
        rec = out.setdefault(enc, {"kills": 0, "wipes": 0})
        if f.get("kill"):
            rec["kills"] += 1
        else:
            rec["wipes"] += 1
    for rec in out.values():
        rec["attempts"] = rec["kills"] + rec["wipes"]
    return out


# ---------- TIER-WIDE GAP ROLLUPS (stitch per-boss data into one comprehensive view) ----------
def tier_spec_gap(o_pool, t_pool):
    """Comprehensive "lowest-hanging fruit" view: pool every DPS player's per-boss DPS by spec across
    ALL shared bosses, then rank specs by the per-player deficit to the benchmark's same spec. Floats
    the spec that's most behind tier-wide to the top — that's where coaching pays off most."""
    rows = []
    for key in set(o_pool) | set(t_pool):
        o = o_pool.get(key)
        t = t_pool.get(key)
        ref = o or t
        o_d = o["dps"] if o else []
        t_d = t["dps"] if t else []
        o_avg = round(sum(o_d) / len(o_d)) if o_d else 0
        t_avg = round(sum(t_d) / len(t_d)) if t_d else 0
        rows.append({
            "class": ref["class"], "spec": ref["spec"],
            "oursAvg": o_avg, "theirsAvg": t_avg, "deficit": t_avg - o_avg,
            "oursSamples": len(o_d), "theirsSamples": len(t_d),
            "both": bool(o_d) and bool(t_d),
        })
    rows.sort(key=lambda r: (not r["both"], -r["deficit"]))
    return rows


def tier_uptime_gap(acc):
    """Comprehensive buff/debuff coverage: average each aura's uptime % across the shared bosses,
    ours vs theirs, ranked by the biggest deficit (where we most consistently trail on maintaining
    a raid buff or boss debuff). Complements the per-boss uptime bars with a tier-wide priority list."""
    rows = []
    for name, rec in acc.items():
        o, t = rec["o"], rec["t"]
        o_avg = round(sum(o) / len(o)) if o else 0
        t_avg = round(sum(t) / len(t)) if t else 0
        rows.append({"name": name, "kind": rec["kind"], "ours": o_avg, "theirs": t_avg,
                     "deficit": t_avg - o_avg})
    rows.sort(key=lambda r: -r["deficit"])
    return rows


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


# ---------- DAMAGE CONTRIBUTION BY CLASS + ITEM LEVEL BY ROLE ----------
def accumulate_class_dmg(report, agg):
    """Add a fight's DamageDone totals into a class -> damage map (in place)."""
    for e in _entries(report, "dd"):
        cls = e.get("type") or "Unknown"
        agg[cls] = agg.get(cls, 0) + int(e.get("total", 0))


def accumulate_ilvl(report, ilvl_map):
    """Record name -> item level from any output table (ilvl is static per report, so the
    first sighting wins). dd covers dps, heal covers healers, dt covers tanks."""
    for alias in ("dd", "heal", "dt"):
        for e in _entries(report, alias):
            nm = e.get("name")
            il = e.get("itemLevel")
            if nm and il and nm not in ilvl_map:
                ilvl_map[nm] = float(il)


def class_dmg_share(o_agg, t_agg):
    """Per-class share of total raid damage, ours vs theirs, sorted by our share."""
    o_tot = sum(o_agg.values()) or 1
    t_tot = sum(t_agg.values()) or 1
    rows = []
    for cls in set(o_agg) | set(t_agg):
        o_d = o_agg.get(cls, 0)
        t_d = t_agg.get(cls, 0)
        o_pct = round(o_d / o_tot * 100, 1)
        t_pct = round(t_d / t_tot * 100, 1)
        # Drop negligible non-player buckets (Environment/Unknown round to 0% on both sides).
        if o_pct == 0 and t_pct == 0:
            continue
        rows.append({"class": cls, "ours": o_d, "theirs": t_d, "oursPct": o_pct, "theirsPct": t_pct})
    rows.sort(key=lambda r: -max(r["oursPct"], r["theirsPct"]))
    return rows


def role_ilvl(ilvl_map, roster):
    """Average item level per role (dps/healer/tank) over the shared-boss roster."""
    role_of = {p["name"]: p["role"] for p in roster}
    by = {"dps": [], "healer": [], "tank": []}
    for nm, il in ilvl_map.items():
        r = role_of.get(nm)
        if r in by and il:
            by[r].append(il)
    return {r: (round(sum(v) / len(v), 1) if v else 0) for r, v in by.items()}


# ---------- "BIGGEST GAPS" SCORECARD (rank every tracked dimension by distance to benchmark) ----------
def _fmt_k(n):
    """Compact number for prose: 31.4k / 1.2M."""
    n = float(n)
    if abs(n) >= 1e6:
        return "{:.1f}M".format(n / 1e6)
    if abs(n) >= 1e3:
        return "{:.1f}k".format(n / 1e3)
    return str(int(round(n)))


def _fmt_dur(ms):
    s = int(round(ms / 1000))
    return "{}:{:02d}".format(s // 60, s % 60)


def biggest_gaps(summary, quality, consumables, audit, comp_gaps, tier_spec=None, tier_uptime=None, n=7):
    """Score every tracked dimension by how far behind the benchmark we are, then surface the
    worst few as plain-language coaching cards. Each candidate yields a severity in [0,1]
    (0 = at/ahead of benchmark, 1 = badly behind) and an actionable sentence; only dimensions
    where we actually trail make the list. Severity scales are hand-tuned per metric so a
    'clearly bad' gap lands near 1.0."""
    co, ct = consumables["ours"], consumables["theirs"]
    ao, at = audit["ours"], audit["theirs"]
    bosses = max(summary["bossCount"], 1)
    cand = []

    def add(sev, title, text):
        if sev > 0:
            cand.append({"sev": round(min(sev, 1.0), 3), "title": title, "text": text})

    # Raid parse (higher better).
    dp = summary["theirsAvgParse"] - summary["oursAvgParse"]
    add(dp / 50.0, "Raid parses trail the benchmark",
        "Raid parses average {} vs {} — a {}-point gap. Lift individual play, gear, and rotations."
        .format(summary["oursAvgParse"], summary["theirsAvgParse"], round(dp, 1)))

    # Total kill time (lower better).
    od, td = summary["oursDurationMs"], summary["theirsDurationMs"]
    if td > 0 and od > td:
        pct = round((od / td - 1) * 100)
        add((od / td - 1), "Kills take longer",
            "Total kill time {} vs {} — {}% slower. More raid DPS and cleaner execution close this."
            .format(_fmt_dur(od), _fmt_dur(td), pct))

    # Raid DPS (higher better) — the direct driver of slower kills.
    od2, td2 = quality["oursRaidDps"], quality["theirsRaidDps"]
    if td2 > 0 and od2 < td2:
        add((td2 - od2) / td2, "Raid DPS is lower",
            "Raid DPS averages {} vs {}. This is the direct cause of the slower kills."
            .format(_fmt_k(od2), _fmt_k(td2)))

    # Deaths (lower better). oursDeaths/theirsDeaths are the night-wide total when
    # rollup data is present (trash + every pull, incl. wipes), else per-boss kills.
    ddh = summary["oursDeaths"] - summary["theirsDeaths"]
    if ddh > 0:
        scope = "across the full clear (trash + all pulls)" if summary.get("nightWideDeaths") \
            else "across {} bosses".format(bosses)
        add(ddh / (bosses * 2.0), "Too many deaths",
            "{} deaths vs {} {}. Avoidable deaths cost DPS and risk wipes."
            .format(summary["oursDeaths"], summary["theirsDeaths"], scope))

    # Healer overheal (lower better).
    oh = quality["oursOverheal"] - quality["theirsOverheal"]
    if oh > 0:
        add(oh / 40.0, "Healers overheal more",
            "Healers overheal {}% vs {}%. Tighten assignments and spell choice to free up throughput."
            .format(quality["oursOverheal"], quality["theirsOverheal"]))

    # DPS activity (higher better).
    ac = quality["theirsActivity"] - quality["oursActivity"]
    if ac > 0:
        add(ac / 30.0, "DPS activity is lower",
            "DPS spend {}% of the fight active vs {}% — dead GCDs are lost damage."
            .format(quality["oursActivity"], quality["theirsActivity"]))

    # Avoidable damage taken / sec (lower better).
    dtk_o, dtk_t = quality["oursDtps"], quality["theirsDtps"]
    if dtk_t > 0 and dtk_o > dtk_t:
        add((dtk_o / dtk_t - 1), "Taking avoidable damage",
            "Raid takes {}/s of damage (ex-tanks) vs {}/s. Dodge mechanics to ease healing and downtime."
            .format(_fmt_k(dtk_o), _fmt_k(dtk_t)))

    # Flask coverage (fraction of roster).
    o_fl = co["flask"] / max(co["rosterSize"], 1)
    t_fl = ct["flask"] / max(ct["rosterSize"], 1)
    if t_fl - o_fl > 0:
        add(t_fl - o_fl, "Not everyone is flasked",
            "Only ~{}/{} raiders flasked; benchmark ~{}/{}. A flask is a full consumable every pull."
            .format(co["flask"], co["rosterSize"], ct["flask"], ct["rosterSize"]))

    # Food coverage (fraction of roster).
    o_fd = co["food"] / max(co["rosterSize"], 1)
    t_fd = ct["food"] / max(ct["rosterSize"], 1)
    if t_fd - o_fd > 0:
        add(t_fd - o_fd, "Not everyone ate food",
            "Only ~{}/{} raiders ate food; benchmark ~{}/{}. Well Fed is free stats."
            .format(co["food"], co["rosterSize"], ct["food"], ct["rosterSize"]))

    # Missing enchants per player (lower better).
    o_me = ao["totalMissingEnchants"] / max(ao["playerCount"], 1)
    t_me = at["totalMissingEnchants"] / max(at["playerCount"], 1)
    if o_me - t_me > 0:
        add((o_me - t_me) / 3.0, "Gear isn't fully enchanted",
            "{} missing enchants across the raid vs {} for the benchmark — free stats on every slot."
            .format(ao["totalMissingEnchants"], at["totalMissingEnchants"]))

    # Raid buff/debuff providers the benchmark brings and we don't.
    missing = [g["buff"] for g in comp_gaps if g["theirs"] and not g["ours"]]
    if missing:
        eg = missing[0] + (", " + missing[1] if len(missing) > 1 else "")
        add(len(missing) / 5.0, "Missing raid buff/debuff providers",
            "Benchmark brings {} raid-wide buff/debuff{} you don't (e.g. {}). Slot the class/spec to gain it."
            .format(len(missing), "s" if len(missing) > 1 else "", eg))

    # Wipes / attempts (only when attempt data is present; more pulls = a fight you don't have down).
    if summary.get("hasAttempts"):
        ow, tw = summary["oursWipes"], summary["theirsWipes"]
        if ow > tw:
            add((ow - tw) / (bosses * 3.0), "Wiping more on progression",
                "{} wipes across the shared bosses vs {} for the benchmark. Repeated pulls = a fight not yet on farm."
                .format(ow, tw))

    # Biggest per-spec DPS deficit tier-wide (the lowest-hanging coaching target).
    if tier_spec:
        worst = next((r for r in tier_spec if r["both"] and r["deficit"] > 0), None)
        if worst:
            add(worst["deficit"] / 800.0, "A spec is underperforming tier-wide",
                "{} {} average {}/s vs {}/s across the tier — your biggest per-spec DPS gap. Coach rotation/gear."
                .format(worst["spec"], worst["class"], _fmt_k(worst["oursAvg"]), _fmt_k(worst["theirsAvg"])))

    # Biggest buff/debuff uptime deficit tier-wide.
    if tier_uptime:
        worst = next((r for r in tier_uptime if r["deficit"] >= 3), None)
        if worst:
            add(worst["deficit"] / 40.0, "A raid buff/debuff is under-maintained",
                "{} {} uptime averages {}% vs {}% tier-wide. Keeping it up is free throughput."
                .format(worst["name"], worst["kind"], worst["ours"], worst["theirs"]))

    cand.sort(key=lambda c: -c["sev"])
    out = []
    for c in cand[:n]:
        c["level"] = "high" if c["sev"] >= 0.5 else ("med" if c["sev"] >= 0.25 else "low")
        out.append(c)
    return out


# ---------- TRASH ANALYSIS (the Trash tab) ----------
# WCL splits trash into discrete pull segments; we layer four views on top, all honoring the
# product's hybrid rule: benchmark-compare only what aligns across guilds (clear time, deaths,
# CC counts, mob-type kill priority — mob TYPES align even when pull boundaries don't), and keep
# the per-pull drill-down single-raid (ours). Kill order & CC are DESCRIPTIVE vs the benchmark,
# never moralized — if the benchmark CCs more or focuses a target later, that's the bar, not a fault.
def load_trash(directory):
    """Bundle the three trash files for one report. Returns None when trash wasn't fetched (older
    data folders predate the Trash tab), so the build degrades gracefully."""
    tp = os.path.join(directory, "trash.json")
    if not os.path.isfile(tp):
        return None
    trash = read_json(tp)

    def _rj(name, default):
        p = os.path.join(directory, name)
        return read_json(p) if os.path.isfile(p) else default

    deaths = _rj("trash-deaths.json", {"friendly": [], "enemy": []})
    cc = _rj("trash-cc.json", {"auras": [], "events": {}})
    return {
        "fights": trash.get("fights") or [],
        "npc": {int(a["id"]): a.get("name") for a in (trash.get("npcActors") or []) if a.get("id") is not None},
        "player": {int(a["id"]): a.get("name") for a in (trash.get("playerActors") or []) if a.get("id") is not None},
        "friendly": deaths.get("friendly") or [],
        "enemy": deaths.get("enemy") or [],
        "cc": cc,
    }


def _trash_glance(t):
    clear = ssum([int(f["endTime"]) - int(f["startTime"]) for f in t["fights"]])
    return {"packs": len(t["fights"]), "clearMs": clear, "deaths": len(t["friendly"])}


def _trash_zones(side):
    """Set of gameZone ids that this report's trash happened in (e.g. {548} for SSC)."""
    return {(f.get("gameZone") or {}).get("id") for f in side["fights"]
            if (f.get("gameZone") or {}).get("id") is not None}


def _zone_names(side, zone_ids):
    """Pretty names for the given zone ids, from this report's trash fights."""
    names = {}
    for f in side["fights"]:
        gz = f.get("gameZone") or {}
        if gz.get("id") in zone_ids and gz.get("name"):
            names.setdefault(gz["id"], gz["name"])
    return [names[z] for z in sorted(names) if z in names]


def _filter_to_zones(side, zone_ids):
    """Restrict a side's trash to fights in `zone_ids`, dropping the deaths/kills/CC events of any
    fight outside them. This is how the trash comparison is scoped to the zone(s) BOTH raids did —
    so one raid's Gruul/TK trash doesn't pollute a comparison that should be SSC-only."""
    fights = [f for f in side["fights"] if (f.get("gameZone") or {}).get("id") in zone_ids]
    keep = {int(f["id"]) for f in fights}
    cc = side["cc"]
    out = dict(side)
    out["fights"] = fights
    out["enemy"] = [e for e in side["enemy"] if e.get("fight") in keep]
    out["friendly"] = [d for d in side["friendly"] if d.get("fight") in keep]
    out["cc"] = {"auras": cc.get("auras") or [],
                 "events": {gid: [ev for ev in evs if ev.get("fight") in keep]
                            for gid, evs in (cc.get("events") or {}).items()}}
    return out


def _cc_id_labels(t):
    """spell id -> canonical hard-CC label, for the CC auras present in this report."""
    return {int(a["guid"]): cc_label(a.get("name"))
            for a in (t["cc"].get("auras") or []) if a.get("guid") is not None}


def trash_death_causes(o, t, n=15):
    """Player trash deaths aggregated by killing blow, ranked worst-for-us, ours vs benchmark.
    Mob/ability killing blows align across guilds, so this is a clean benchmark comparison."""
    def agg(side):
        m = {}
        for d in side["friendly"]:
            kb = (d.get("killingBlow") or {}).get("name") or "Unknown"
            m[kb] = m.get(kb, 0) + 1
        return m
    oa, ta = agg(o), agg(t)
    rows = [{"cause": c, "ours": oa.get(c, 0), "theirs": ta.get(c, 0)} for c in set(oa) | set(ta)]
    rows.sort(key=lambda r: (-(r["ours"]), -(r["ours"] - r["theirs"]), -r["theirs"]))
    return rows[:n]


def trash_cc_compare(o, t):
    """Hard-CC applications by type, ours vs benchmark (descriptive — more CC isn't better or
    worse, the benchmark sets the bar). Count = landed applications (applydebuff events)."""
    def agg(side):
        labels = _cc_id_labels(side)
        m = {}
        for gid, evs in (side["cc"].get("events") or {}).items():
            lab = labels.get(int(gid)) or "CC"
            m[lab] = m.get(lab, 0) + len(evs)
        return m
    oa, ta = agg(o), agg(t)
    rows = [{"label": c, "ours": oa.get(c, 0), "theirs": ta.get(c, 0)} for c in set(oa) | set(ta)]
    rows.sort(key=lambda r: -max(r["ours"], r["theirs"]))
    return rows, {"ours": sum(oa.values()), "theirs": sum(ta.values())}


def trash_cc_by_mob(o, t):
    """Which mob types get crowd-controlled, by CC type and how often — ours vs benchmark. One row per
    (mob, CC) combo. Rows are grouped by mob (most-CC'd mob first) so you can see, e.g., 'Greyheart
    Nether-Mage: Polymorph ×40'. Counts = landed `applydebuff` events on that mob. Descriptive."""
    def agg(side):
        labels = _cc_id_labels(side)
        npc = side["npc"]
        m = {}
        for gid, evs in (side["cc"].get("events") or {}).items():
            lab = labels.get(int(gid)) or "CC"
            for ev in evs:
                mob = npc.get(ev["targetID"]) or "Unknown"
                m[(mob, lab)] = m.get((mob, lab), 0) + 1
        return m
    oa, ta = agg(o), agg(t)
    rows = [{"mob": mob, "cc": lab, "ours": oa.get((mob, lab), 0), "theirs": ta.get((mob, lab), 0)}
            for (mob, lab) in set(oa) | set(ta)]
    mob_total = {}
    for r in rows:
        mob_total[r["mob"]] = mob_total.get(r["mob"], 0) + max(r["ours"], r["theirs"])
    # Group a mob's CC rows together; rank mobs by how much they're CC'd, then biggest CC count first.
    rows.sort(key=lambda r: (-mob_total[r["mob"]], r["mob"], -max(r["ours"], r["theirs"]), r["cc"]))
    return rows


def _pull_type_medians(pull):
    """For one pull, {mob: median death time}. Empty when <2 mob types (no pair to compare).
    Using the median of each type's instance deaths keeps a straggler from flipping the order."""
    by = {}
    for k in pull["killOrder"]:
        if k.get("mob"):
            by.setdefault(k["mob"], []).append(k["tSec"])
    if len(by) < 2:
        return {}
    return {m: statistics.median(v) for m, v in by.items()}


def _trash_pull_records(t):
    """Flat list of per-pull records (one per WCL trash segment): segment name, mobs, intra-pull kill
    order, player deaths, CC. Shared by the per-pack drill-down and the kill-order comparison."""
    npc, player = t["npc"], t["player"]
    labels = _cc_id_labels(t)
    kills_by_fight, deaths_by_fight, cc_by_fight = {}, {}, {}
    for e in t["enemy"]:
        kills_by_fight.setdefault(e["fight"], []).append(e)
    for d in t["friendly"]:
        deaths_by_fight.setdefault(d.get("fight"), []).append(d)
    for gid, evs in (t["cc"].get("events") or {}).items():
        lab = labels.get(int(gid)) or "CC"
        for ev in evs:
            cc_by_fight.setdefault(ev["fight"], []).append((ev, lab))

    pulls = []
    for f in t["fights"]:
        fid, start, end = int(f["id"]), int(f["startTime"]), int(f["endTime"])

        def sec(ts):
            return round((int(ts) - start) / 1000)

        mobs = [{"name": npc.get(int(x["id"]), "Unknown"), "count": int(x.get("instanceCount") or 1)}
                for x in (f.get("enemyNPCs") or [])]
        order = [{"mob": npc.get(e["targetID"]), "tSec": sec(e["t"])}
                 for e in sorted(kills_by_fight.get(fid, []), key=lambda e: e["t"])
                 if npc.get(e["targetID"]) and npc.get(e["targetID"]) != "Environment"]
        deaths = [{"name": d.get("name"), "cls": d.get("type"),
                   "killedBy": (d.get("killingBlow") or {}).get("name") or "Unknown",
                   "tSec": sec(d.get("timestamp", start))}
                  for d in sorted(deaths_by_fight.get(fid, []), key=lambda d: d.get("timestamp", 0))]
        cc = [{"mob": npc.get(ev["targetID"], "Unknown"), "label": lab, "by": player.get(ev["sourceID"])}
              for ev, lab in sorted(cc_by_fight.get(fid, []), key=lambda x: x[0]["t"])]
        pulls.append({"name": f["name"], "clearMs": end - start, "mobs": mobs,
                      "killOrder": order, "deaths": deaths, "cc": cc})
    return pulls


def trash_packs(pulls):
    """Group OUR pull records by segment name into packs (single-raid drill-down), sorted
    most-problematic first (deaths, then repeat count, then time)."""
    groups = {}
    for p in pulls:
        g = groups.setdefault(p["name"], {"name": p["name"], "pulls": [], "deaths": 0, "cc": 0, "clearMs": 0})
        g["pulls"].append(p)
        g["deaths"] += len(p["deaths"])
        g["cc"] += len(p["cc"])
        g["clearMs"] += p["clearMs"]
    out = list(groups.values())
    for g in out:
        g["count"] = len(g["pulls"])
    out.sort(key=lambda g: (-g["deaths"], -g["count"], -g["clearMs"]))
    return out


def _roster_sig(pull):
    """A pull's exact roster signature: sorted ((mob_name, count), ...) from its enemyNPCs — names
    AND counts. Two pulls with the same signature are genuinely the same pack (and a merged chain-pull
    won't match a clean single pack), which is how we know a kill-order comparison is like-for-like."""
    counts = {}
    for m in pull["mobs"]:
        nm = m.get("name")
        if nm and nm != "Unknown":
            counts[nm] = counts.get(nm, 0) + int(m.get("count") or 1)
    return tuple(sorted(counts.items()))


def _typical_order(pulls):
    """Typical kill order (list of mob types, first-killed first) across a set of pulls: average each
    type's normalized death position (median death time per type per pull) and sort earliest first."""
    pos = {}
    for p in pulls:
        med = _pull_type_medians(p)  # {} when <2 types
        if not med:
            continue
        ordered = sorted(med, key=lambda m: med[m])
        denom = len(ordered) - 1
        for rank, m in enumerate(ordered):
            pos.setdefault(m, []).append(rank / denom)
    return sorted(pos, key=lambda m: sum(pos[m]) / len(pos[m]))


def trash_identical_packs(o_pulls, t_pulls):
    """Kill-order comparison restricted to packs both raids pulled with the EXACT same roster — same
    mob types AND counts (`_roster_sig`). This is the high-confidence 'same pack' test the user asked
    for: it guarantees a like-for-like comparison and inherently drops merged/chain-pulls (their roster
    won't match a clean pack's). For each shared roster it returns the typical kill order on each side;
    sorted by how differently the two raids ordered the same mobs."""
    def by_sig(pulls):
        g = {}
        for p in pulls:
            sig = _roster_sig(p)
            if len(sig) >= 2:  # need >= 2 mob types for an order to exist
                g.setdefault(sig, []).append(p)
        return g

    og, tg = by_sig(o_pulls), by_sig(t_pulls)
    rows = []
    for sig in set(og) & set(tg):
        o_order, t_order = _typical_order(og[sig]), _typical_order(tg[sig])
        if len(o_order) < 2 or len(t_order) < 2:
            continue
        trank = {m: i for i, m in enumerate(t_order)}
        orank = {m: i for i, m in enumerate(o_order)}
        divergence = sum(abs(orank[m] - trank.get(m, orank[m])) for m in o_order)
        rows.append({
            "roster": [{"name": n, "count": c} for n, c in sig],
            "ours": o_order, "theirs": t_order,
            "oursPulls": len(og[sig]), "theirsPulls": len(tg[sig]),
            "divergence": divergence,
        })
    rows.sort(key=lambda r: (-r["divergence"], -(r["oursPulls"] + r["theirsPulls"])))
    return rows


# --- Broad "Pairwise Priority" sub-tab: kill-priority pooled across ALL pulls (no pack matching) ---
def _kill_priority_one(t):
    """Per mob TYPE, an index 0-100 (100 = consistently the FIRST type focused in its pulls). Only
    MULTI-type pulls count; a type's death time in a pull is the median of its instances'. Feeds the
    pairwise sub-tab's ladder. Returns {mob: (index, multi-type-pull samples)}."""
    npc = t["npc"]
    kills_by_fight = {}
    for e in t["enemy"]:
        kills_by_fight.setdefault(e["fight"], []).append(e)
    pos = {}
    for kills in kills_by_fight.values():
        by_type = {}
        for e in kills:
            mob = npc.get(e["targetID"])
            if not mob or mob == "Environment":
                continue
            by_type.setdefault(mob, []).append(int(e["t"]))
        if len(by_type) < 2:
            continue
        order = sorted(by_type, key=lambda m: sorted(by_type[m])[len(by_type[m]) // 2])
        denom = len(order) - 1
        for rank, m in enumerate(order):
            pos.setdefault(m, []).append(rank / denom)
    return {m: (round((1 - sum(v) / len(v)) * 100), len(v)) for m, v in pos.items()}


def trash_kill_priority(o, t, min_samples=2):
    """Mob-type kill-priority index, ours vs benchmark, for the ladder. Keeps mob types seen in at
    least `min_samples` multi-type pulls on either side; sorted by biggest divergence first."""
    oa, ta = _kill_priority_one(o), _kill_priority_one(t)
    rows = []
    for mob in set(oa) | set(ta):
        oi, osn = oa.get(mob, (None, 0))
        ti, tsn = ta.get(mob, (None, 0))
        if max(osn, tsn) < min_samples:
            continue
        rows.append({"mob": mob, "ours": oi, "theirs": ti, "oursSamples": osn, "theirsSamples": tsn,
                     "both": oi is not None and ti is not None})
    rows.sort(key=lambda r: (not r["both"], -abs((r["ours"] or 0) - (r["theirs"] or 0))))
    return rows


def _pair_table(pulls):
    """For every pair of mob types that co-occur in a pull, how often the alphabetically-first one
    died first. Returns {(a, b): [a_first_count, total_pulls]}."""
    tab = {}
    for p in pulls:
        med = _pull_type_medians(p)
        for a, b in itertools.combinations(sorted(med), 2):
            rec = tab.setdefault((a, b), [0, 0])
            rec[1] += 1
            if med[a] < med[b]:
                rec[0] += 1
    return tab


def trash_pairwise_priority(o_pulls, t_pulls, min_pulls=2):
    """Broad target-priority comparison that needs no pack identity: for each pair of mob types both
    raids fought together, how often each kills the first before the second. A pair's order survives
    the merge/split that breaks pack matching, so it covers far more than exact-pack matching.
    Each row orients the pair so `lead` is the mob the benchmark kills first more often."""
    ot, tt = _pair_table(o_pulls), _pair_table(t_pulls)
    rows = []
    for key in set(ot) & set(tt):
        a, b = key
        o_first, o_tot = ot[key]
        t_first, t_tot = tt[key]
        if o_tot < min_pulls or t_tot < min_pulls:
            continue
        o_rate, t_rate = o_first / o_tot, t_first / t_tot
        if t_rate >= 0.5:
            lead, trail, ours, theirs = a, b, o_rate, t_rate
        else:
            lead, trail, ours, theirs = b, a, 1 - o_rate, 1 - t_rate
        rows.append({
            "lead": lead, "trail": trail,
            "ours": round(ours * 100), "theirs": round(theirs * 100),
            "oursPulls": o_tot, "theirsPulls": t_tot,
            "divergence": round(abs(ours - theirs) * 100),
            "reversed": (ours < 0.5),
        })
    rows.sort(key=lambda r: (-r["divergence"], -min(r["oursPulls"], r["theirsPulls"])))
    return rows


def build_trash(ours_dir, theirs_dir):
    """Assemble the Trash tab payload. Present only when both reports have trash data."""
    o, t = load_trash(ours_dir), load_trash(theirs_dir)
    if not o or not t or (not o["fights"] and not t["fights"]):
        return {"present": False}

    # Restrict the comparison to the zone(s) BOTH raids did trash in (e.g. just SSC) — the two reports
    # can cover different content (ours SSC+TK, theirs SSC+Gruul), and comparing across non-shared
    # zones is apples-to-oranges (a 0 just means "they didn't go there"). Mirrors how the boss tab
    # only compares shared encounters. Needs gameZone on trash fights (older data folders lack it →
    # _trash_zones is empty → no filtering, graceful).
    shared_zones = _trash_zones(o) & _trash_zones(t)
    zone_names = _zone_names(o, shared_zones) or _zone_names(t, shared_zones)
    if shared_zones:
        o, t = _filter_to_zones(o, shared_zones), _filter_to_zones(t, shared_zones)
    if not o["fights"] and not t["fights"]:
        return {"present": False}

    cc_rows, cc_tot = trash_cc_compare(o, t)
    o_pulls, t_pulls = _trash_pull_records(o), _trash_pull_records(t)
    return {
        "present": True,
        "zones": zone_names,
        "glance": {"ours": _trash_glance(o), "theirs": _trash_glance(t)},
        "deathCauses": trash_death_causes(o, t),
        # Kill order — two lenses: exact-roster 1:1 packs (primary), and broad pairwise (sub-tab).
        "identicalPacks": trash_identical_packs(o_pulls, t_pulls),
        "killPriority": trash_kill_priority(o, t),
        "pairwisePriority": trash_pairwise_priority(o_pulls, t_pulls),
        "cc": cc_rows, "ccTotals": cc_tot, "ccByMob": trash_cc_by_mob(o, t),
        "packs": trash_packs(o_pulls),
    }


# ---------- ASSEMBLE ----------
def build(ours_dir, theirs_dir, ours_parses, theirs_parses, out_file,
          ours_name="Our Raid", theirs_name="Benchmark", zone_name=""):
    ours_raw = get_fights(ours_parses)
    theirs_raw = get_fights(theirs_parses)
    ours_idx = index_by_encounter(ours_raw)
    theirs_idx = index_by_encounter(theirs_raw)
    common_ids = [k for k in ours_idx if k in theirs_idx]

    bosses = [{"encounterID": int(i), "name": ours_idx[i]["name"], "ours": ours_idx[i], "theirs": theirs_idx[i]}
              for i in common_ids]

    # Raid-wide night death total comes from WCL's zone-ROLLUP entries (sentinel
    # fightID >= 10000), NOT the sum of per-boss kill deaths. The rollup already
    # counts trash + every boss pull (incl. wipes), so the per-boss counts are a
    # SUBSET of it — adding them on top is the double-count bug that produced 179
    # (19 boss-kill + 160 rollup). Restrict to zones BOTH raids cleared (shared
    # rollup encounter ids), mirroring the per-boss intersection. Falls back to
    # per-boss kill deaths when a report predates rollups (e.g. single-boss logs).
    def _zone_rollups(raw):
        return {str(f["encounter"]["id"]): int(f["deaths"])
                for f in raw if f.get("fightID", 0) >= 10000}
    o_roll, t_roll = _zone_rollups(ours_raw), _zone_rollups(theirs_raw)
    shared_roll = [k for k in o_roll if k in t_roll]
    night_wide_deaths = bool(shared_roll)
    if night_wide_deaths:
        ours_deaths_total = ssum([o_roll[k] for k in shared_roll])
        theirs_deaths_total = ssum([t_roll[k] for k in shared_roll])
    else:
        ours_deaths_total = ssum([ours_idx[i]["deaths"] for i in common_ids])
        theirs_deaths_total = ssum([theirs_idx[i]["deaths"] for i in common_ids])

    # Wipe/attempt counts per shared boss (graceful if attempts.json predates this feature).
    ours_att = attempt_map(ours_dir)
    theirs_att = attempt_map(theirs_dir)
    for b in bosses:
        enc = str(b["encounterID"])
        oa, ta = ours_att.get(enc, {}), theirs_att.get(enc, {})
        b["oursWipes"], b["theirsWipes"] = oa.get("wipes", 0), ta.get("wipes", 0)
        b["oursAttempts"], b["theirsAttempts"] = oa.get("attempts", 0), ta.get("attempts", 0)
        b["hasAttempts"] = bool(oa) or bool(ta)
    has_attempts = any(b["hasAttempts"] for b in bosses)

    summary = {
        "bossCount": len(bosses),
        "oursAvgParse": avg([b["ours"]["avgParse"] for b in bosses]),
        "theirsAvgParse": avg([b["theirs"]["avgParse"] for b in bosses]),
        "oursDeaths": ours_deaths_total,
        "theirsDeaths": theirs_deaths_total,
        "nightWideDeaths": night_wide_deaths,
        "oursDurationMs": ssum([b["ours"]["durationMs"] for b in bosses]),
        "theirsDurationMs": ssum([b["theirs"]["durationMs"] for b in bosses]),
        "oursWipes": ssum([b["oursWipes"] for b in bosses]),
        "theirsWipes": ssum([b["theirsWipes"] for b in bosses]),
        "hasAttempts": has_attempts,
    }

    # Composition
    ours_roster = get_roster(ours_idx, common_ids)
    theirs_roster = get_roster(theirs_idx, common_ids)
    ours_spec = {p["name"]: p["spec"] for p in ours_roster}
    theirs_spec = {p["name"]: p["spec"] for p in theirs_roster}
    ours_role = {p["name"]: p["role"] for p in ours_roster}
    theirs_role = {p["name"]: p["role"] for p in theirs_roster}
    ours_cls = {p["name"]: p["class"] for p in ours_roster}
    theirs_cls = {p["name"]: p["class"] for p in theirs_roster}
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
             "theirs": has_provider(theirs_pairs, c["class"], c["spec"]), "impact": c["impact"],
             "class": c["class"], "spec": c["spec"]}
            for c in PROVIDER_CHECKS]
    composition = {
        "oursClasses": class_counts(ours_roster), "theirsClasses": class_counts(theirs_roster),
        "oursSize": len(ours_roster), "theirsSize": len(theirs_roster), "gaps": gaps,
        "specDiff": spec_comp_diff(ours_roster, theirs_roster),
    }

    # Audit
    ours_roster_names = [p["name"] for p in ours_roster]
    theirs_roster_names = [p["name"] for p in theirs_roster]
    audit_ours = audit_report(ours_dir, ours_roster_names)
    audit_theirs = audit_report(theirs_dir, theirs_roster_names)
    audit_ours["avgIlvl"] = avg_ilvl(ours_dir, common_ids)
    audit_theirs["avgIlvl"] = avg_ilvl(theirs_dir, common_ids)
    audit = {"ours": audit_ours, "theirs": audit_theirs}

    # Consumable coverage (flask/food/elixir/drums/potions) from the per-boss Buffs tables.
    consumables = {
        "ours": consumable_report(ours_dir, common_ids, len(ours_roster)),
        "theirs": consumable_report(theirs_dir, common_ids, len(theirs_roster)),
    }
    # Per-player consumable participation (ours only — a coaching view of your own raid).
    per_player_consumes = per_player_consumables(ours_dir, ours_idx, common_ids)

    # Per-boss
    ours_fights = fight_map(ours_dir)
    theirs_fights = fight_map(theirs_dir)
    # Accumulators for the tier-wide views (class damage share + item level by role).
    o_class_dmg, t_class_dmg = {}, {}
    o_ilvl, t_ilvl = {}, {}
    o_raid_dmg_sum = t_raid_dmg_sum = o_raid_heal_sum = t_raid_heal_sum = 0
    # Tier-wide gap rollups: per-spec DPS pools (across all bosses) + buff/debuff uptime samples.
    tier_o_spec, tier_t_spec = {}, {}
    tier_upt = {}  # aura name -> {"kind": buff|debuff, "o": [uptimes], "t": [uptimes]}
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

        # Raid output for this boss (total damage/healing / duration).
        o_raid_dmg, t_raid_dmg = raid_sum(o_b, "dd"), raid_sum(t_b, "dd")
        o_raid_heal, t_raid_heal = raid_sum(o_b, "heal"), raid_sum(t_b, "heal")
        # Feed the tier-wide accumulators.
        accumulate_class_dmg(o_b, o_class_dmg)
        accumulate_class_dmg(t_b, t_class_dmg)
        accumulate_ilvl(o_b, o_ilvl)
        accumulate_ilvl(t_b, t_ilvl)
        o_raid_dmg_sum += o_raid_dmg
        t_raid_dmg_sum += t_raid_dmg
        o_raid_heal_sum += o_raid_heal
        t_raid_heal_sum += t_raid_heal

        # Pool per-spec DPS across bosses for the tier-wide "lowest-hanging fruit" rollup.
        for pool, rep, sp, ro, cl, dur in ((tier_o_spec, o_b, ours_spec, ours_role, ours_cls, o_dur),
                                           (tier_t_spec, t_b, theirs_spec, theirs_role, theirs_cls, t_dur)):
            for key, bucket in spec_dps_buckets(rep, sp, ro, cl, dur).items():
                ent = pool.setdefault(key, {"class": bucket["class"], "spec": bucket["spec"], "dps": []})
                ent["dps"].extend(p["dps"] for p in bucket["players"])
        # Sample buff/debuff uptimes for the tier-wide coverage rollup.
        for kind, rows_ in (("buff", buff_rows), ("debuff", debuff_rows)):
            for r in rows_:
                rec = tier_upt.setdefault(r["name"], {"kind": kind, "o": [], "t": []})
                if r["ours"] is not None:
                    rec["o"].append(r["ours"])
                if r["theirs"] is not None:
                    rec["t"].append(r["theirs"])

        o_lust = lust_sec(_auras(o_b, "buffs"), ours_fights[enc]["start"])
        t_lust = lust_sec(_auras(t_b, "buffs"), theirs_fights[enc]["start"])
        o_deaths = death_list(o_b, ours_fights[enc]["start"])
        t_deaths = death_list(t_b, theirs_fights[enc]["start"])
        o_tl = load_timeline(ours_dir, enc)
        t_tl = load_timeline(theirs_dir, enc)
        per_boss.append({
            "encounterID": b["encounterID"], "name": b["name"],
            "oursLustSec": o_lust,
            "theirsLustSec": t_lust,
            "oursRaidDps": rate(o_raid_dmg, o_dur), "theirsRaidDps": rate(t_raid_dmg, t_dur),
            "oursRaidHps": rate(o_raid_heal, o_dur), "theirsRaidHps": rate(t_raid_heal, t_dur),
            "specGap": spec_gap(o_b, t_b, ours_spec, ours_role, ours_cls,
                                theirs_spec, theirs_role, theirs_cls, o_dur, t_dur),
            "buffs": buff_rows, "debuffs": debuff_rows,
            "oursActivity": activity_pct(o_b, o_dur, ours_dps), "theirsActivity": activity_pct(t_b, t_dur, theirs_dps),
            "oursOverheal": overheal_pct(o_b, ours_heal), "theirsOverheal": overheal_pct(t_b, theirs_heal),
            "oursDmgTaken": o_dmg, "theirsDmgTaken": t_dmg,
            "oursDurMs": o_dur, "theirsDurMs": t_dur,
            "oursDtps": dtps(o_dmg, o_dur), "theirsDtps": dtps(t_dmg, t_dur),
            "dmgCompare": dmg_compare(o_b, ours_tank, t_b, theirs_tank, 7),
            "interrupts": int_compare(o_b, t_b, ours_spec, theirs_spec),
            "unkicked": unkicked_compare(o_b, t_b),
            "dispelsList": disp_compare(o_b, t_b),
            "deaths": {"ours": o_deaths, "theirs": t_deaths},
            "phases": phase_compare(ours_fights[enc], theirs_fights[enc]),
            "timeline": timeline_view(o_tl, t_tl, o_deaths, t_deaths, o_lust, t_lust,
                                      o_dur, t_dur, ours_fights[enc], theirs_fights[enc]),
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
        # Raid DPS/HPS, time-weighted across the shared bosses.
        "oursRaidDps": rate(o_raid_dmg_sum, o_dur_sum), "theirsRaidDps": rate(t_raid_dmg_sum, t_dur_sum),
        "oursRaidHps": rate(o_raid_heal_sum, o_dur_sum), "theirsRaidHps": rate(t_raid_heal_sum, t_dur_sum),
    }

    # Surface per-boss raid DPS/HPS on the Overview boss cards (keyed by encounter).
    raid_out = {p["encounterID"]: p for p in per_boss}
    for b in bosses:
        ro = raid_out.get(b["encounterID"])
        if ro:
            b["oursRaidDps"], b["theirsRaidDps"] = ro["oursRaidDps"], ro["theirsRaidDps"]
            b["oursRaidHps"], b["theirsRaidHps"] = ro["oursRaidHps"], ro["theirsRaidHps"]

    # Tier-wide damage contribution by class + item level by role.
    output_breakdown = {
        "classShare": class_dmg_share(o_class_dmg, t_class_dmg),
        "oursRoleIlvl": role_ilvl(o_ilvl, ours_roster),
        "theirsRoleIlvl": role_ilvl(t_ilvl, theirs_roster),
    }
    # "What's killing us" — death causes aggregated across the whole shared clear.
    death_causes_rows = death_cause_compare(per_boss)
    # Tier-wide comprehensive gap rollups (stitched from the per-boss data above).
    tier_spec = tier_spec_gap(tier_o_spec, tier_t_spec)
    tier_uptime = tier_uptime_gap(tier_upt)
    # "Biggest Gaps" scorecard — rank every tracked dimension by distance to the benchmark.
    gaps_scorecard = biggest_gaps(summary, quality, consumables, audit, gaps,
                                  tier_spec=tier_spec, tier_uptime=tier_uptime)

    eff = {"ours": efficiency(ours_dir), "theirs": efficiency(theirs_dir)}

    # Trash analysis (on by default; graceful {present:false} on older data folders without trash files).
    trash = build_trash(ours_dir, theirs_dir)

    payload = {
        "zone": zone_name, "ours": {"title": ours_name}, "theirs": {"title": theirs_name},
        "summary": summary, "bosses": bosses, "gapsScorecard": gaps_scorecard,
        "deep": {"composition": composition, "audit": audit, "consumables": consumables,
                 "perPlayerConsumes": per_player_consumes, "outputBreakdown": output_breakdown,
                 "deathCauses": death_causes_rows, "tierSpecGap": tier_spec, "tierUptimeGap": tier_uptime,
                 "quality": quality, "perBoss": per_boss, "efficiency": eff, "trash": trash},
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
