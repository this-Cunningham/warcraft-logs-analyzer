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
import positioning  # the Positioning views (features ride positions-<enc>.json; graceful when absent)

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


def primary_role_map(idx, enc_ids):
    """Per player across the shared bosses: their most-frequent (primary) ROLE. Mirrors
    primary_spec_map so role is derived the SAME way as spec — by majority, not by whichever
    fight was iterated first. A player who healed one boss but DPS'd the other four reads as
    'dps' (consistent with their primary spec), so the prep audit, consumable labels, and
    healer/DPS table splits don't mislabel a one-off role as the player's role."""
    counts = {}
    for enc in enc_ids:
        if enc not in idx:
            continue
        for p in idx[enc]["players"]:
            if p["role"]:
                counts.setdefault(p["name"], {})
                counts[p["name"]][p["role"]] = counts[p["name"]].get(p["role"], 0) + 1
    # max by count; ties fall to the first role seen (dict is insertion-ordered)
    return {name: max(c, key=c.get) for name, c in counts.items()}


def get_roster(idx, enc_ids):
    """Roster restricted to the given encounters (the shared bosses), unique by name.
    Spec is the player's PRIMARY (most-frequent) spec; role is likewise the PRIMARY
    (most-frequent) role — both order-independent, so spec and role stay consistent for a
    role/spec switcher (a Feral who bear-tanks one fight reads Feral/dps if she DPS'd the rest)."""
    primary = primary_spec_map(idx, enc_ids)
    primary_role = primary_role_map(idx, enc_ids)
    by_name = {}
    for enc in enc_ids:
        if enc not in idx:
            continue
        for p in idx[enc]["players"]:
            if p["name"] not in by_name:
                by_name[p["name"]] = {"name": p["name"], "class": p["class"],
                                      "spec": primary.get(p["name"], p["spec"]),
                                      "role": primary_role.get(p["name"], p["role"])}
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


# WCL emits feral-tree druid builds under variant spec names — a bear-tank build reads "Warden",
# a feral-tank "Guardian" — that do NOT contain the substring "feral". A naive substring match for
# the Leader-of-the-Pack provider check (and its count) therefore reads 0 for a real Feral druid who
# genuinely provides the buff, flipping the Composition row to a false "your edge" and inflating the
# Overview "buffs the benchmark lacks" count. Canonicalize those variants to Feral for PROVIDER
# MATCHING only (the displayed roster spec is untouched). Verified on the pinned benchmark: its
# bear-tank Ancler reads Warden/Guardian across the shared bosses yet maintains Leader of the Pack at
# 93-100% uptime. Balance variants (e.g. "Dreamstate") are deliberately NOT mapped: a Dreamstate druid
# is often a resto HEALER (no Improved Faerie Fire), so aliasing it would wrongly credit an Imp-FF
# provider — verified on this benchmark (its only Dreamstate druid is a healer; Imp FF theirs=0 is right).
SPEC_ALIASES = {("druid", "warden"): "Feral", ("druid", "guardian"): "Feral"}


def _canon_spec(cls, spec):
    """Normalize a player's primary spec to a canonical provider spec (variant tank builds → Feral)."""
    return SPEC_ALIASES.get((str(cls).lower(), str(spec or "").lower()), spec)


def has_provider(pairs, cls, spec):
    """Does any (class, primary-spec) pair satisfy this provider check? `pairs` is one
    (class, primary-spec) entry per player, taken from the roster."""
    for c, s in pairs:
        if c == cls:
            if not spec:
                return True
            s = _canon_spec(c, s)
            if s and spec.lower() in s.lower():
                return True
    return False


def count_providers(pairs, cls, spec):
    """How MANY (class, primary-spec) pairs satisfy this provider check — the one-level-deeper
    companion to has_provider. The binary check goes silent once each side has ≥1; the COUNT is the
    actual roster lever (how many of a class/spec to slot) and exposes single-points-of-failure (a
    raid-wide buff carried by exactly one provider). Same matching logic as has_provider."""
    n = 0
    for c, s in pairs:
        cs = _canon_spec(c, s)
        if c == cls and (not spec or (cs and spec.lower() in cs.lower())):
            n += 1
    return n


# High-impact TBC raid contributions: class/spec -> buff/debuff + why it matters.
# `scope` governs the honest reading of the provider COUNT (count_providers):
#   • "raid"  — a boss debuff / raid-wide effect ONE provider delivers in full; extra copies are
#               INSURANCE (count==1 = a single-point-of-failure), so a count delta is NOT better/worse
#               — only the SPOF flag is.
#   • "group" — a party-scoped buff (in TBC, Windfury / Battle Shout / Trueshot / Ferocious
#               Inspiration / Leader of the Pack land on the provider's own 5-man party), so more
#               providers genuinely = more groups covered → a count delta IS a clean coverage signal.
#   NOTE: Bloodlust / Heroism is RAID-WIDE in TBC Anniversary (not party-wide as in original TBC), so
#   it is scoped "raid": one Shaman covers the whole raid and a second is insurance, not more coverage.
PROVIDER_CHECKS = [
    {"buff": "Misery", "class": "Priest", "spec": "Shadow", "scope": "raid", "impact": "+5% spell damage taken by boss, plus a mana battery for casters"},
    {"buff": "Improved Faerie Fire", "class": "Druid", "spec": "Balance", "scope": "raid", "impact": "+3% spell hit for the whole raid (huge for casters)"},
    {"buff": "Ferocious Inspiration", "class": "Hunter", "spec": "Beast", "scope": "group", "impact": "+3% damage to the hunter's party"},
    {"buff": "Trueshot Aura", "class": "Hunter", "spec": "Marksmanship", "scope": "group", "impact": "Attack power for the hunter's party"},
    {"buff": "Expose Weakness", "class": "Hunter", "spec": "Survival", "scope": "raid", "impact": "Raid-wide attack power from crits"},
    {"buff": "Bloodlust / Heroism", "class": "Shaman", "spec": "", "scope": "raid", "impact": "+30% haste burst — raid-wide in TBC Anniversary, so one Shaman covers everyone; a second is insurance, not more coverage"},
    {"buff": "Windfury Totem", "class": "Shaman", "spec": "Enhancement", "scope": "group", "impact": "Big melee boost — party-scoped, needs one per melee group"},
    {"buff": "Improved Scorch (fire)", "class": "Mage", "spec": "Fire", "scope": "raid", "impact": "+15% fire damage taken by boss"},
    {"buff": "Curse of the Elements", "class": "Warlock", "spec": "", "scope": "raid", "impact": "+10% spell damage taken by boss"},
    {"buff": "Leader of the Pack", "class": "Druid", "spec": "Feral", "scope": "group", "impact": "+5% melee/ranged crit — party-scoped aura"},
    {"buff": "Judgement of Wisdom", "class": "Paladin", "spec": "", "scope": "raid", "impact": "Mana return for the raid (one judgement on the boss suffices)"},
    {"buff": "Battle Shout", "class": "Warrior", "spec": "", "scope": "group", "impact": "Attack power — party-scoped, so more warriors cover more groups"},
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

# Windfury Totem buff spell ids (ranks) — a name-match on "Windfury" is the primary detector, these
# back it up. A melee player in a Windfury group won't apply a weapon oil: Windfury substitutes for it.
WINDFURY_IDS = {25587, 25528, 8512, 10613, 10614}


def _is_melee(cls, spec):
    """Melee specs that benefit from Windfury (and so legitimately skip a weapon oil). Warriors and
    Rogues are melee in every spec; the hybrids only in their melee spec. Hunters are excluded — they
    fight at range and don't substitute oil for Windfury (per the design note)."""
    if cls in ("Warrior", "Rogue"):
        return True
    if not spec:
        return False
    if cls == "Shaman" and "Enhanc" in spec:
        return True
    if cls == "Paladin" and "Retribution" in spec:
        return True
    if cls == "Druid" and "Feral" in spec:
        return True
    return False


def _is_windfury(aura):
    """Did this buff aura come from Windfury Totem? Match the name (WCL logs it as 'Windfury Totem')
    or a known rank spell id."""
    nm = aura.get("name") or ""
    guid = aura.get("guid")
    if "Windfury" in nm:
        return True
    return guid is not None and int(guid) in WINDFURY_IDS


def windfury_players(directory, enc_ids):
    """Set of player NAMES who had the Windfury Totem buff on any shared boss. Read per-player from the
    consumes-<enc>.json buff auras (scoped by sourceID), NOT the raid-aggregate Buffs table — Windfury
    is group-scoped, so a raid can have a shaman yet a given player still be in a non-Windfury group.
    Graceful: a data folder without consumes files just yields an empty set (no melee gets upgraded)."""
    name_to_id = name_id_map(directory)
    has = set()
    for enc in enc_ids:
        path = os.path.join(directory, "consumes-{}.json".format(enc))
        if not os.path.isfile(path):
            continue
        per_player = read_json(path).get("perPlayer") or {}
        for nm, pid in name_to_id.items():
            if nm in has:
                continue
            for a in (per_player.get(str(pid)) or []):
                if _is_windfury(a):
                    has.add(nm)
                    break
    return has


def audit_report(directory, allow_names, spec_map=None, windfury_names=None):
    pd = read_json(os.path.join(directory, "playerdetails.json"))
    pd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    spec_map = spec_map or {}
    windfury_names = windfury_names or set()
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
                # WCL can emit an id:0 placeholder ahead of the real item for the same slot (e.g. a
                # two-hand weapon in slot 15 with an empty off-hand placeholder also in slot 15).
                # Skip id:0 entries so the real item wins — without this, next() picks the placeholder
                # and the id!=0 guard short-circuits out, silently dropping any temporaryEnchant.
                item = next((g for g in gear if g.get("slot") == slot and g.get("id", 0) != 0), None)
                if item and item.get("id", 0) != 0:
                    if not item.get("permanentEnchant") or int(item.get("permanentEnchant", 0)) == 0:
                        missing.append(ENCH_SLOTS[slot])
                    if slot == 15 and item.get("temporaryEnchant") and int(item.get("temporaryEnchant", 0)) != 0:
                        weapon_oil = True
            # Windfury substitutes for a weapon oil on melee: a melee player in a Windfury group who
            # has no oil is NOT a gap. Casters/ranged always need their oil. Counting a well-prepared
            # melee as "missing" would be a false positive that erodes trust in the audit.
            melee = _is_melee(pl.get("type"), spec_map.get(pl["name"]))
            windfury = pl["name"] in windfury_names
            weapon_covered = weapon_oil or (melee and windfury)
            players.append({
                "name": pl["name"], "class": pl.get("type"), "role": _ROLE_LABEL[rn],
                "missingEnchants": missing, "missingCount": len(missing),
                "weaponOil": weapon_oil, "melee": melee, "windfury": windfury,
                "weaponCovered": weapon_covered,
            })
    return {
        "players": players,
        "totalMissingEnchants": ssum([p["missingCount"] for p in players]),
        "playersNoWeaponOil": len([p for p in players if not p["weaponCovered"]]),
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


# ---------- HIT / EXPERTISE AUDIT (from combatantInfo.stats) — EXPERIMENTAL ----------
# combatantInfo carries a per-pull stat snapshot (Hit, Expertise, Crit, Haste, …) the report never used.
# Hit rating is the #1 itemization lever in TBC: a caster/melee under the hit cap simply MISSES, bleeding
# throughput that's fixable with gems/enchants/gear. The snapshot's "Hit" is **gear** hit only (rating);
# the talent + raid-buff % also count toward the cap. We surface EFFECTIVE hit = gear + talent + raid:
#   • gear   — the combatantInfo rating, converted to %.
#   • talent — the spec's STANDARD-build hit talent, assumed taken 100% (`SPEC_TALENT_HIT`; e.g. a Shadow
#              Priest's Shadow Focus +10%). Invisible in the data (TBC talents are placeholders), so it's
#              an assumption from the meta, not a read.
#   • raid   — Improved Faerie Fire (+3% spell hit, `IMP_FAERIE_FIRE_HIT`), credited when a Balance Druid
#              is in the roster (raid-wide boss debuff — the one reliably detectable raid source).
# NOT modeled (party-scoped or murky, and they cancel between similar raids): Totem of Wrath / Heroic
# Presence (party-range), Warlock Suppression (Affliction DoTs only, not Shadow Bolt). (Note: Misery is
# +5% spell DAMAGE, not hit.) Melee has no detectable raid hit buff → raid = 0 for melee/ranged.
SPELL_HIT_PER_PCT = 12.6    # spell hit rating per 1% (TBC)
PHYS_HIT_PER_PCT = 15.77    # melee/ranged hit rating per 1% (TBC)
HIT_CAP = {"spell": 16.0, "melee": 9.0, "ranged": 9.0}  # textbook gear hit caps vs a +3 raid boss (the target ceiling)
IMP_FAERIE_FIRE_HIT = 3.0   # Improved Faerie Fire (Balance Druid): +3% spell hit, raid-wide boss debuff

# Hit from a spec's STANDARD PvE talent build — assumed taken 100% (the user's rule: if the common build
# has a hit talent, every raider of that spec has it). ONLY clean cases where the talent boosts ~all of
# the spec's damage (sourced from TBC talent guides). Keyed by (class, spec) — spec strings match the
# roster; the value is added to that spec's hit type (a caster spec → spell, a melee spec → melee/ranged).
# Deliberately OMITTED (partial / no standard hit talent, and they cancel same-spec anyway): Warlock
# Affliction (Suppression helps DoTs but NOT Shadow Bolt — they gear to the SB cap), Destruction/Demonology
# Warlock, Mage Arcane (Elemental Precision is Fire/Frost only), BM/Marksmanship Hunter, Ret Paladin, Feral
# Druid, and the TANKS (Prot Warrior/Paladin, bear) — they itemize to their cap without a counted hit
# talent (e.g. a prot warrior gears to ~9% rather than relying on a talent). (Note: per-spec, so it cancels
# in the same-spec flag; its value is an HONEST effective hit vs the cap — a Shadow Priest at 6% gear is
# capped via Shadow Focus, not under.)
SPEC_TALENT_HIT = {
    # spell hit
    ("Priest", "Shadow"):        10.0,  # Shadow Focus 5/5 (+2%/pt)
    ("Druid", "Balance"):         4.0,  # Balance of Power 2/2 (+2%/pt, all spells)
    ("Mage", "Fire"):             3.0,  # Elemental Precision 3/3 (Fire & Frost spells)
    ("Mage", "Frost"):            3.0,  # Elemental Precision 3/3
    ("Shaman", "Elemental"):      3.0,  # Nature's Guidance 3/3 (the standard 41/0/20 Resto dip)
    # melee / ranged hit
    ("Rogue", "Combat"):          5.0,  # Precision 5/5 (+1%/pt) — every rogue build takes it
    ("Rogue", "Assassination"):   5.0,  # Precision 5/5 (Mutilate dips 20 Combat for it)
    ("Rogue", "Subtlety"):        5.0,  # Precision 5/5
    ("Warrior", "Arms"):          3.0,  # Precision 3/3 (Arms; Fury dips Arms for it)
    ("Warrior", "Fury"):          3.0,  # Precision 3/3
    ("Shaman", "Enhancement"):    3.0,  # Nature's Guidance 3/3 (the standard 0/41/20 Resto dip)
    ("Hunter", "Survival"):       3.0,  # Surefooted 3/3 (ranged hit)
}


def _hit_kind(cls, spec, role):
    """('spell'|'melee'|'ranged') for a hit-relevant role, or None to skip. Healers don't itemize hit;
    hunters use ranged hit; casters use spell hit; everyone else (incl. tanks, for threat) melee hit.
    Protection Paladins are EXCLUDED: their threat is spell-based (Consecration/Holy Shield/Judgement) so
    they itemize SPELL hit, but WCL's combatantInfo exposes only a single PHYSICAL hit field and never
    captures prot-pally spell hit — every prot pally (ours and the benchmark) reads an identical ~15
    melee-residue rating. Grading the stat we can see (melee) against a cap they rightly ignore would only
    paint a false red, so we skip them — same reason healers are out: the hit that matters isn't measurable."""
    if role == "healer":
        return None
    if cls == "Paladin" and (role == "tank" or spec in ("Protection", "Justicar")):
        return None
    if cls == "Hunter":
        return "ranged"
    sp = spec or ""
    if (cls in ("Mage", "Warlock") or (cls == "Priest" and "Shadow" in sp)
            or (cls == "Druid" and "Balance" in sp) or (cls == "Shaman" and "Element" in sp)):
        return "spell"
    return "melee"


def spell_hit_env(roster):
    """Raid-wide spell-hit a side's casters get from its composition, beyond gear. Only the reliably
    detectable source: Improved Faerie Fire (+3%), inferred from a Balance Druid in the roster (boomkins
    talent it ~universally, and it's a raid-wide boss debuff so every caster benefits). ToW / Heroic
    Presence / talents are deliberately excluded (party-scoped or invisible — see the section note)."""
    return IMP_FAERIE_FIRE_HIT if any(p["class"] == "Druid" and "Balance" in (p["spec"] or "")
                                      for p in roster) else 0.0


def stat_audit(directory, role_map, spec_map, class_map, allow_names, spell_env=0.0):
    """Per-raider hit broken into GEAR + TALENT + RAID → EFFECTIVE (+ Expertise), from combatantInfo.stats,
    scoped to the shared-boss roster (healers excluded — no hit itemization). Gear: the snapshot rating ÷
    the spell/physical constant (MAX across the night, so a one-off resist/threat-set swap doesn't
    understate real gear). Talent: the spec's standard-build hit talent (`SPEC_TALENT_HIT`). Raid: `spell_env`
    (Imp FF) for casters, 0 for melee/ranged. effPct = gear + talent + raid."""
    pd = read_json(os.path.join(directory, "playerdetails.json"))
    pd = pd["reportData"]["report"]["playerDetails"]["data"]["playerDetails"]
    allow = set(allow_names)
    seen, out = set(), []
    for rn in ("tanks", "healers", "dps"):
        for pl in (pd.get(rn) or []):
            nm = pl.get("name")
            if (allow and nm not in allow) or nm in seen:
                continue
            ci = pl.get("combatantInfo")
            stats = (ci.get("stats") if isinstance(ci, dict) else None) or {}
            cls = class_map.get(nm) or pl.get("type")
            spec = spec_map.get(nm) or ""
            kind = _hit_kind(cls, spec, role_map.get(nm))
            if not stats or not kind:
                continue
            seen.add(nm)
            per = SPELL_HIT_PER_PCT if kind == "spell" else PHYS_HIT_PER_PCT
            hit_rating = int((stats.get("Hit") or {}).get("max", 0) or 0)
            gear = round(hit_rating / per, 1)
            talent = SPEC_TALENT_HIT.get((cls, spec), 0.0)   # standard-build hit talent, assumed
            raid = spell_env if kind == "spell" else 0.0      # raid Imp FF — casters only
            exp = int((stats.get("Expertise") or {}).get("max", 0) or 0)
            out.append({
                "name": nm, "class": cls, "spec": spec, "role": role_map.get(nm),
                "hitType": kind, "hitRating": hit_rating,
                "gearPct": gear, "talentPct": round(talent, 1), "raidPct": round(raid, 1),
                "effPct": round(gear + talent + raid, 1),
                "cap": HIT_CAP[kind], "expertise": exp, "physical": kind != "spell",
            })
    return out


def stat_audit_compare(ours, theirs):
    """Attach each raider's hit TARGET — the HARDCODED textbook hit cap for their hit type (spell 16% ·
    melee/ranged 9%), independent of the benchmark: every DPS and tank itemizes toward hit cap (DPS for
    landed casts/swings, tanks for threat). Benchmark same-spec expertise is still surfaced as a reference.
    Flag raiders a clear margin under cap, on EFFECTIVE hit (gear + talent + raid). Worst hit gap first."""
    bench = {}
    for p in theirs:
        b = bench.setdefault((p["class"], p["spec"]), {"exp": []})
        if p["physical"]:
            b["exp"].append(p["expertise"])
    rows, n_under = [], 0
    for p in ours:
        b = bench.get((p["class"], p["spec"]), {})
        be = b.get("exp") or []
        bench_exp = round(sum(be) / len(be)) if be else None
        # Target = the textbook hit cap for this hit type — a fixed, benchmark-independent goal every DPS
        # and tank wants to reach. Flag = a clear margin under cap. The margin is TIGHT (1%) when the spec's
        # standard hit talent is MODELED in SPEC_TALENT_HIT (we then see the full gear+talent+raid picture,
        # so any shortfall is real), and WIDER (3%) when it isn't (tanks, Arcane/Affliction casters, BM/MM
        # Hunter, Ret): their effPct understates true hit because we don't assume a talent we can't count, so
        # we only flag a large, unambiguous shortfall to avoid a false red on an actually-capped raider.
        target = p["cap"]
        margin = 1.0 if (p["class"], p["spec"]) in SPEC_TALENT_HIT else 3.0
        under = p["effPct"] < target - margin
        n_under += 1 if under else 0
        rows.append({**p, "benchExp": bench_exp,
                     "target": round(target, 1), "under": under, "gap": round(target - p["effPct"], 1)})
    rows.sort(key=lambda r: (not r["under"], -r["gap"]))

    def _avg_gt(rs, t):
        # gear + talent only — the controllable ITEMIZATION lever, EXCLUDING the raid Imp FF component.
        v = [round(r["gearPct"] + r["talentPct"], 1) for r in rs if r["hitType"] == t]
        return round(sum(v) / len(v), 1) if v else None

    def _env(rs):  # the side's spell-hit environment (Imp FF), read off any spell caster
        return next((r["raidPct"] for r in rs if r["hitType"] == "spell"), 0.0)
    # The summary cards compare gear+talent (the lever the raid actually itemizes), NOT effective hit.
    # If the spell card compared EFFECTIVE hit, an asymmetric raid buff (we field boomkins for +3% Imp FF,
    # the benchmark doesn't) would paint a green "we hit better" delta while our casters' own gear+talent
    # hit is actually WORSE — exactly the lever a leader would want flagged. Melee/ranged carry no raid hit
    # component, so gear+talent == effective there (unchanged). The per-side Imp FF is shown in spellEnv.
    summary = {
        "oursUnder": n_under, "playerCount": len(rows),
        "spell": {"ours": _avg_gt(ours, "spell"), "theirs": _avg_gt(theirs, "spell")},
        "melee": {"ours": _avg_gt(ours, "melee"), "theirs": _avg_gt(theirs, "melee")},
        "ranged": {"ours": _avg_gt(ours, "ranged"), "theirs": _avg_gt(theirs, "ranged")},
        "spellEnv": {"ours": _env(ours), "theirs": _env(theirs)},
    }
    return {"players": rows, "summary": summary}


# ---------- CONSUMABLE COVERAGE (from the per-boss Buffs tables we already fetch) ----------
# The Buffs table carries consumable auras (flask/food/elixir/drums/potions) with a `totalUses`
# count. For flask/food that's ~one application per player, so totalUses ≈ how many raiders showed
# up consumed. It's raid-AGGREGATE (no per-player breakdown), and it can't tell flask-vs-elixir for
# the same player apart — flask is the headline proxy; elixirs/potions are supplementary.
# WCL names most consumable BUFFS by their effect, not the item — so the name often lacks the words
# "Flask"/"Elixir"/"Potion" (e.g. Flask of Supreme Power → buff "Supreme Power"; Ironshield Potion →
# buff "Ironshield"). We therefore detect by **spell id**, mined from the report data (the benchmark
# — a top guild — carries the full set), with a name fallback for "Flask of …"/"Elixir of …" buffs.
# Combat-potion buff spell ids (verified present in data: Haste/Destruction/Ironshield potions).
POTION_IDS = {28507, 28508, 28515}
# THROUGHPUT (offensive DPS) combat potions only — Haste (28507) and Destruction (28508). Ironshield
# (28515) is a tank DEFENSIVE damage-absorb potion: it shares the combat-potion cooldown so it belongs
# in the usage POTION_IDS, but it is NOT a "free DPS opener" — so the Prepot view (whose whole premise
# is "the throughput potion on the pull is free DPS") must scan only these, or a tank's defensive
# Ironshield on the pull fabricates a green "prepotted" cell and halves the real DPS-prepot gap.
THROUGHPUT_POTION_IDS = {28507, 28508}
# IN-COMBAT instant consumables (health/mana potion, healthstone) leave NO buff aura — verified live,
# they don't appear in the Buffs table at all. They DO log in the **Casts** table under their effect name:
# a mana potion casts "Restore Mana", a healthstone "Master Healthstone" (+ rank names containing
# "Healthstone"), a health potion "Restore Health". So the in-combat matrix reads MP/HS/HP from Casts
# (per-player), while the combat throughput potion (P) is the buff-sourced POTION category above.
MANA_POTION_NAMES = {"Restore Mana"}
HEALTH_POTION_NAMES = {"Restore Health"}
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
    28490,  # Elixir of Major Strength — buff "Major Strength" (+35 str); WCL effect-renamed (no "Elixir")
}
ELIXIR_GUARDIAN_IDS = {
    39627,  # Elixir of Draenic Wisdom (+30 int/spi)
    39625,  # Elixir of Major Fortitude (+250 hp, +10 hp/5)
    11371,  # Gift of Arthas (+10 shadow resist + disease proc) — tooltip says "Guardian Elixir"
    28509,  # Elixir of Major Mageblood — buff "Greater Versatility" (+16 mp5); WCL effect-renamed
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
    if _is_elixir(name, guid):
        return "elixir"
    if g in POTION_IDS:
        return "potion"
    return None


def consumable_report(directory, idx, enc_ids, roster_size):
    """Raid consumable coverage, counted PER RAIDER so the headline card reconciles with the per-player
    matrix below. A raider counts as "Flasked / Elixir Pair" when they showed up PREPARED — a flask OR a
    full battle + guardian elixir pair — on at least HALF of the shared bosses they attended. That 0.5
    threshold is deliberately the matrix's own Prep-badge cutoff (green/yellow ≥ 0.5 vs red below it), so
    a leader can tally the green/yellow rows in the matrix and land on this exact number. Both views run
    the identical `_cell_for` pass (same battle+guardian pairing logic), so they can't disagree.

    (This replaces an average-PER-BOSS count, which was the bug the TODO flagged: an avg like "18/25"
    didn't map to anything a leader could see in the per-player matrix, so the two views looked at odds.)

    Food is the same per-raider count for Well Fed. Falls back to the old aggregate
    Buffs flask/food average only when NO shared boss has a consumes file (older data folders), so it
    never regresses to empty. Elixirs/potions aren't surfaced here — the matrix carries that detail."""
    fm = fight_map(directory)
    name_to_id = name_id_map(directory)
    role_map = primary_role_map(idx, enc_ids)  # majority role, so a DPS's battle-only prep counts (matrix-consistent)
    # Per-raider tallies across the shared bosses (same _cell_for pass as the matrix).
    present_cnt, prepared_cnt, fed_cnt = {}, {}, {}
    have_consumes = False
    # Fallback (only if NO boss has a consumes file): aggregate Buffs flask/food, avg per boss.
    fb_prepared, fb_fed = [], []
    for enc in enc_ids:
        rep = load_boss(directory, str(enc))
        if not rep:
            continue
        auras = _auras(rep, "buffs")
        # Prepared/fed PER-PLAYER (flask OR battle+guardian pair) — needs the consumes file.
        cons_path = os.path.join(directory, "consumes-{}.json".format(enc))
        present = (idx.get(enc) or {}).get("players") or []
        if os.path.isfile(cons_path) and present:
            have_consumes = True
            per_player = read_json(cons_path).get("perPlayer") or {}
            seen = set()
            for pl in present:
                nm = pl["name"]
                if nm in seen:
                    continue
                seen.add(nm)
                pid = name_to_id.get(nm)
                cell = _cell_for(per_player.get(str(pid)) if pid is not None else None, role_map.get(nm))
                present_cnt[nm] = present_cnt.get(nm, 0) + 1
                if cell["consumed"]:
                    prepared_cnt[nm] = prepared_cnt.get(nm, 0) + 1
                if cell["food"]:
                    fed_cnt[nm] = fed_cnt.get(nm, 0) + 1
        elif auras:  # fallback: aggregate Buffs flask/food totals (counts a pair only partially — best effort)
            flask = sum(int(a.get("totalUses", 0)) for a in auras
                        if _consumable_cat(a.get("name", ""), a.get("guid")) == "flask")
            food = sum(int(a.get("totalUses", 0)) for a in auras if a.get("name") == "Well Fed")
            fb_prepared.append(flask)
            fb_fed.append(food)

    def iavg(lst, cap=None):
        if not lst:
            return 0
        v = int(round(sum(lst) / len(lst)))
        return min(v, cap) if cap is not None else v

    if have_consumes:
        # A raider is "flasked"/"fed" if prepared on >= half of the bosses they attended (the matrix's
        # own green/yellow Prep-badge threshold), so the card and matrix line up exactly.
        flask = sum(1 for nm, p in present_cnt.items() if p > 0 and prepared_cnt.get(nm, 0) / p >= 0.5)
        food = sum(1 for nm, p in present_cnt.items() if p > 0 and fed_cnt.get(nm, 0) / p >= 0.5)
    else:
        flask = iavg(fb_prepared, roster_size)
        food = iavg(fb_fed, roster_size)

    return {
        "rosterSize": roster_size,
        "flask": flask,
        "food": food,
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


def _cell_for(auras, role=None):
    """Reduce one player's pull auras on one boss to a consumable cell.

    `role` (dps/healer/tank) tunes the prep bar: for a **DPS**, only the BATTLE (offensive) elixir
    affects throughput — a guardian elixir is a defensive/utility choice, so a DPS with a battle elixir
    counts as prepared even without a guardian (and the matrix renders the missing guardian as faint,
    not red). Healers/tanks still need the full flask-or-pair (their guardian elixir IS throughput, e.g.
    Draenic Wisdom). When role is unknown, the strict flask-or-pair rule applies (back-compat)."""
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
    # Consumed = a flask, OR a battle+guardian PAIR (one of each — TBC allows one of each type at once).
    # (The old `total_elixirs >= 2` shortcut wrongly counted two same-type elixirs — only possible via a
    # WCL logging quirk — as a pair; the explicit one-of-each test matches the documented semantics.)
    consumed = flask or (battle >= 1 and guardian >= 1)
    # A DPS is prepared on throughput with just a battle elixir — guardian is optional for them.
    if role == "dps" and battle >= 1:
        consumed = True
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

    # Union roster (class/role from first boss that has the player). Spec is the player's PRIMARY
    # (most-frequent) spec across the shared bosses — more actionable than a bare role label (a
    # leader scanning offenders can tell the Holy Priest from the Disc Priest), and the same map
    # the rest of the report uses, so the labels stay consistent.
    prim = primary_spec_map(idx, enc_ids)
    role_map = primary_role_map(idx, enc_ids)  # majority role (consistent with spec; feeds the DPS guardian-elixir rule)
    info = {}
    for enc in enc_ids:
        for pl in ((idx.get(enc) or {}).get("players") or []):
            info.setdefault(pl["name"], {"class": pl["class"], "role": role_map.get(pl["name"], pl["role"])})

    players = []
    for nm, meta in info.items():
        cells = {}
        present_n = consumed_n = food_n = 0
        for b in boss_meta:
            enc = b["enc"]
            if nm in boss_present.get(enc, set()):
                cell = _cell_for(boss_auras[enc].get(nm), meta["role"])
                present_n += 1
                consumed_n += 1 if cell["consumed"] else 0
                food_n += 1 if cell["food"] else 0
            else:
                cell = {"present": False}
            cells[str(b["encounterID"])] = cell
        players.append({
            "name": nm, "class": meta["class"], "role": meta["role"],
            "spec": prim.get(nm) or meta["role"], "cells": cells,
            "presentCount": present_n, "consumedCount": consumed_n, "foodCount": food_n,
        })

    # Worst-prepared first: lowest consumed ratio, then lowest food ratio, then name.
    def ratio(a, b):
        return (a / b) if b else 1.0
    players.sort(key=lambda p: (ratio(p["consumedCount"], p["presentCount"]),
                                ratio(p["foodCount"], p["presentCount"]), p["name"]))
    return {"bosses": [{"encounterID": b["encounterID"], "name": b["name"]} for b in boss_meta],
            "players": players}


def _is_healthstone(name):
    return bool(name) and "Healthstone" in name


def _incombat_casts_by_id(directory, enc):
    """Per-source in-combat consumable CAST counts {sourceId(str): {"MP","HS"}} for one shared boss,
    from `incombat-<enc>.json` (written by fetch_report from cast EVENTS). Returns None when the file is
    absent — older data folders predate the events-based fetch and fall back to the (truncated) Casts table.

    WHY events, not the Casts table: WCL's `table(dataType:Casts)` returns only each player's TOP 5
    abilities. For most players the 5 most-cast abilities are all rotational/heal spells, so low-count
    consumable casts (a super mana potion's "Restore Mana", a "Master Healthstone") are truncated off the
    bottom and never seen — silently zeroing the matrix for nearly every healer/DPS. Cast EVENTS are not
    capped, so fetch_report sweeps them and buckets MP/HS by sourceID; this reads that pre-bucketed file."""
    path = os.path.join(directory, "incombat-{}.json".format(enc))
    if not os.path.isfile(path):
        return None
    return read_json(path).get("perSource") or {}


def per_player_incombat(directory, idx, enc_ids, roster):
    """Per-player IN-COMBAT consumable USAGE matrix (ours only) — the companion to the prep matrix, but
    for the consumables you press DURING the fight: combat throughput potion (P), mana potion (MP),
    healthstone (HS). One row per raider × shared boss. **P** comes from the buff-sourced POTION category
    (`consumes-<enc>.json`); **MP/HS** come from cast EVENTS, pre-bucketed per-source in `incombat-<enc>.json`
    (instant items leave no buff aura, and the Casts TABLE caps each player at 5 abilities — which hid the
    consumables; see `_incombat_casts_by_id`). This is a USAGE view, not a prep pass/fail: popping a mana
    pot or healthstone is situational, so a non-use is a faint dash, never a red gap (that would falsely
    flag a warrior for not drinking mana). Healthstone is warlock-dependent — if no warlock is in the raid,
    the HS column is flagged unavailable rather than empty. (Health potions are not tracked — nobody runs
    them in TBC raids.) Sorted by total in-combat usage ascending, so raiders leaving throughput on the
    table surface first."""
    name_to_id = name_id_map(directory)
    has_warlock = any(p.get("class") == "Warlock" for p in roster)
    prim = primary_spec_map(idx, enc_ids)
    role_map = primary_role_map(idx, enc_ids)  # majority role, consistent with spec
    boss_meta = []
    boss_data = {}     # enc(str) -> {name -> {"P","MP","HS"}}
    boss_present = {}  # enc(str) -> set(names)
    info = {}
    for enc in enc_ids:
        present = (idx.get(enc) or {}).get("players") or []
        if not present:
            continue
        cons_path = os.path.join(directory, "consumes-{}.json".format(enc))
        per_player = (read_json(cons_path).get("perPlayer") or {}) if os.path.isfile(cons_path) else {}
        # MP/HS from cast EVENTS (untruncated), keyed by source actor id. Fall back to the (capped) Casts
        # table only on older data folders without an incombat file, so a stale folder still shows something.
        per_source = _incombat_casts_by_id(directory, enc)
        cast_mp, cast_hs = {}, {}  # name -> count, used only by the legacy Casts-table fallback
        if per_source is None:
            rep = load_boss(directory, str(enc))
            for e in (_entries(rep, "casts") if rep else []):
                nm = e.get("name")
                if not nm:
                    continue
                for a in (e.get("abilities") or []):
                    an, tot = a.get("name"), int(a.get("total", 0))
                    if an in MANA_POTION_NAMES:
                        cast_mp[nm] = cast_mp.get(nm, 0) + tot
                    elif _is_healthstone(an):
                        cast_hs[nm] = cast_hs.get(nm, 0) + tot
        data, names, seen = {}, [], set()
        for pl in present:
            nm = pl["name"]
            if nm in seen:
                continue
            seen.add(nm)
            names.append(nm)
            pid = name_to_id.get(nm)
            P = sum(int(a.get("uses", 0)) for a in (per_player.get(str(pid)) or [])
                    if _consumable_cat(a.get("name"), a.get("guid")) == "potion")
            if per_source is not None:
                src = per_source.get(str(pid)) or {}
                mp, hs = int(src.get("MP", 0)), int(src.get("HS", 0))
            else:
                mp, hs = cast_mp.get(nm, 0), cast_hs.get(nm, 0)
            data[nm] = {"P": P, "MP": mp, "HS": hs}
            info.setdefault(nm, {"class": pl["class"], "role": role_map.get(nm, pl["role"])})
        boss_meta.append({"encounterID": int(enc), "name": idx[enc]["name"], "enc": enc})
        boss_data[enc] = data
        boss_present[enc] = set(names)

    players = []
    for nm, meta in info.items():
        cells = {}
        use_total = 0
        for b in boss_meta:
            enc = b["enc"]
            if nm in boss_present.get(enc, set()):
                d = boss_data[enc].get(nm) or {"P": 0, "MP": 0, "HS": 0}
                use_total += d["P"] + d["MP"] + d["HS"]
                cells[str(b["encounterID"])] = {"present": True, **d}
            else:
                cells[str(b["encounterID"])] = {"present": False}
        players.append({"name": nm, "class": meta["class"], "role": meta["role"],
                        "spec": prim.get(nm) or meta["role"], "cells": cells, "useTotal": use_total})
    # Worst-first: the least in-combat consumable usage floats to the top (highest counts sink to the
    # bottom), matching the prep matrix's worst-first convention so the leader's eye lands on the gap.
    players.sort(key=lambda p: (p["useTotal"], p["name"]))
    return {"bosses": [{"encounterID": b["encounterID"], "name": b["name"]} for b in boss_meta],
            "players": players, "hasWarlock": has_warlock}


# ---------- THROUGHPUT CONSUMABLE CHOICES (combat-potion gap by spec + which flasks/elixirs) ----------
def potion_usage_by_spec(directory, idx, enc_ids, spec_map, role_map, class_map):
    """Combat (throughput) potion activations pooled by (class, primary spec) across the shared bosses,
    from the per-player POTION-category buff `uses`. Returns {key: {class, spec, role, total, players:set}}
    — `total` is raid-wide activations for that spec (the "you popped N fewer pots" number), `players`
    the distinct count for a per-player average."""
    name_to_id = name_id_map(directory)
    pool = {}
    for enc in enc_ids:
        path = os.path.join(directory, "consumes-{}.json".format(enc))
        present = (idx.get(enc) or {}).get("players") or []
        if not (os.path.isfile(path) and present):
            continue
        per_player = read_json(path).get("perPlayer") or {}
        seen = set()
        for pl in present:
            nm = pl["name"]
            spec = spec_map.get(nm)
            if not spec or nm in seen:
                continue
            seen.add(nm)
            pid = name_to_id.get(nm)
            cls = class_map.get(nm) or pl["class"]
            b = pool.setdefault("{}|{}".format(cls, spec),
                                {"class": cls, "spec": spec, "role": role_map.get(nm) or pl["role"],
                                 "total": 0, "players": set(), "pots": {}})
            for a in (per_player.get(str(pid)) or []):
                if _consumable_cat(a.get("name"), a.get("guid")) != "potion":
                    continue
                u = int(a.get("uses", 0))
                b["total"] += u
                pn = a.get("name") or "Combat Potion"  # which specific potion (Haste / Destruction / …)
                b["pots"][pn] = b["pots"].get(pn, 0) + u
            b["players"].add(nm)
    return pool


def _pot_names(pots):
    """A spec's potion-name breakdown as a sorted "Haste ×12, Destruction ×3" list (most-used first)."""
    return [{"name": n, "count": c} for n, c in sorted((pots or {}).items(), key=lambda kv: -kv[1]) if c > 0]


def potion_gap(o_pool, t_pool):
    """Per-spec combat-potion activation gap, ours vs benchmark, ranked by where the benchmark popped the
    most more (the biggest throughput-potion deficit). Reports raid-wide total + per-player average per
    spec (so the gap reads both as "N fewer pots" and normalized for roster size) plus WHICH specific
    potions each side used (Haste / Destruction / Ironshield). Restricted to specs BOTH raids fielded —
    a spec only one raid runs is a roster question (Composition tab), not a potion-usage gap."""
    rows = []
    # Overlap ONLY (set intersection): both raids fielded this spec. A spec one raid never ran is a
    # roster question (Composition tab), and comparing its potion rate would be apples-to-oranges — a
    # data-integrity violation the soul prohibits. The template re-checks oursPlayers/theirsPlayers > 0.
    for key in sorted(set(o_pool) & set(t_pool), key=repr):
        o, t = o_pool[key], t_pool[key]
        o_n, t_n = len(o["players"]), len(t["players"])
        rows.append({"class": o["class"], "spec": o["spec"], "role": o["role"],
                     "ours": o["total"], "theirs": t["total"], "oursPlayers": o_n, "theirsPlayers": t_n,
                     "oursAvg": round(o["total"] / o_n, 1) if o_n else 0,
                     "theirsAvg": round(t["total"] / t_n, 1) if t_n else 0,
                     "oursPots": _pot_names(o["pots"]), "theirsPots": _pot_names(t["pots"]),
                     "deficit": t["total"] - o["total"]})
    rows.sort(key=lambda r: -r["deficit"])
    return rows


# (throughput_choices was removed — the "Throughput Consumable Choices" flask/battle-elixir meta table
# it fed was descriptive-only and revealed no actionable gap. The per-spec combat-potion gap, which IS
# a clean throughput lever, stays in potion_gap above.)


# ---------- PER-BOSS BUFF/DEBUFF UPTIME + LUST TIMING ----------
def fight_map(directory):
    m = {}
    for f in read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]:
        m[str(f["encounterID"])] = {
            "start": int(f["startTime"]), "end": int(f["endTime"]),
            "phases": f.get("phaseTransitions") or [], "ilvl": float(f["averageItemLevel"]),
        }
    return m


def phase_name_map(directory):
    """encounterID(str) -> {phaseId(int): name} from report.phases (PhaseMetadata). report.phases
    carries the human phase NAMES (e.g. "P5: Gravity Lapse") that phaseTransitions lacks — populated
    in TBC only for scripted multi-phase bosses, so this is naturally empty for the rest and for data
    folders that predate the field (everything downstream falls back to "Phase N")."""
    try:
        rep = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]
    except (OSError, KeyError, ValueError):
        return {}
    out = {}
    for ep in (rep.get("phases") or []):
        names = {int(pm["id"]): pm["name"] for pm in (ep.get("phases") or [])
                 if pm.get("id") is not None and pm.get("name")}
        if names:
            out[str(ep.get("encounterID"))] = names
    return out


def npc_name_map(directory):
    """report actor id -> name, from the report-wide masterData NPCs on fights.json. Lets the
    add-handling view name each enemy (Ember of Al'ar, Phaseshift Bulwark, …) and identify the BOSS
    by name so it's never mistaken for an add. Graceful {} on data folders predating the masterData fetch."""
    try:
        rep = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]
    except (OSError, KeyError, ValueError):
        return {}
    return {int(a["id"]): a.get("name") for a in (((rep.get("masterData") or {}).get("npcs")) or [])
            if a.get("id") is not None}


KEY_BUFFS =["Bloodlust", "Heroism", "Battle Shout", "Blessing of Kings", "Gift of the Wild",
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


# Real shaman Bloodlust (2825) / Heroism (32182). Matched by SPELL ID, not name: the benchmark's logs
# carry a DIFFERENT aura literally named "Heroism" (guid 39200, a non-shaman effect) whose band starts
# ~60s in — name-matching would pick it up and read the wrong lust window. (Same spell-id-over-name
# principle the consumable classifier uses.) Across all matches take the EARLIEST band, so iteration
# order can't change the answer.
LUST_GUIDS = {2825, 32182}


def lust_sec(auras, fight_start):
    starts = [min(int(b["startTime"]) for b in x["bands"])
              for x in auras if x.get("guid") in LUST_GUIDS and x.get("bands")]
    if not starts:
        return None
    return round((min(starts) - int(fight_start)) / 1000)


def lust_window_mult(tl, lust, window=40):
    """How hard the raid burst during its Bloodlust/Heroism window — EXPERIMENTAL. Average raid DPS in the
    `window` seconds after lust popped ÷ the fight's average DPS. >1 means damage spiked when lust landed
    (DPS cooldowns/trinkets stacked into the haste window); ~1 means lust was up but nothing was stacked
    with it. Coarse (binned to the timeline's buckets, ~40s lust = a few buckets) and descriptive — a
    payoff read on the lust, not a score. None when lust or the timeline curve is absent."""
    if not tl or lust is None:
        return None
    dps = tl.get("dps") or []
    n = len(dps)
    dur = (tl.get("durMs") or 0) / 1000.0
    if not n or dur <= 0:
        return None
    avg = sum(dps) / n
    if avg <= 0:
        return None
    w = dur / n  # seconds per bucket
    lo, hi = max(0, int(lust // w)), min(n, int((lust + window) // w) + 1)
    seg = dps[lo:hi]
    if not seg:
        return None
    return round((sum(seg) / len(seg)) / avg, 2)


def cooldown_lust_alignment(buff_auras, lust_sec_val, fight_start, window=40):
    """Share of major DPS cooldown TYPES (COOLDOWN_NAMES) that had a band overlapping the Bloodlust
    window — did the raid's burst cooldowns coincide with the haste window — EXPERIMENTAL. Counts cooldown
    TYPES, not activations (you can't hold a 2-min cooldown for one window, so 'did you get this cooldown
    into the window at least once' is the right question). None when no lust was used / no cooldowns fired."""
    if lust_sec_val is None:
        return None
    lo = fight_start + lust_sec_val * 1000
    hi = lo + window * 1000
    used = aligned = 0
    for a in buff_auras:
        if a.get("name") not in COOLDOWN_NAMES:
            continue
        bands = a.get("bands") or []
        if not bands:
            continue
        used += 1
        if any(b["startTime"] < hi and b["endTime"] > lo for b in bands):
            aligned += 1
    if not used:
        return None
    return {"aligned": aligned, "used": used, "pct": round(100 * aligned / used)}


def debuff_timing(auras, fight_start, dur_ms, names):
    """Per key debuff: when it was first ESTABLISHED (sec into fight) and its longest continuous GAP after
    that (sec) — the two TIME dimensions a flat uptime % misses. From the aura `bands` (start/end
    intervals). EXPERIMENTAL. Returns {name: {"est", "gap"}} for the debuffs actually present."""
    out = {}
    for nm in names:
        a = next((x for x in auras if x.get("name") == nm), None)
        bands = sorted((a or {}).get("bands") or [], key=lambda b: b["startTime"])
        if not bands:
            continue
        est = max(0, round((bands[0]["startTime"] - fight_start) / 1000))
        gap = 0
        for i in range(len(bands) - 1):
            g = bands[i + 1]["startTime"] - bands[i]["endTime"]
            if g > gap:
                gap = g
        out[nm] = {"est": est, "gap": round(gap / 1000)}
    return out


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


def pet_owner_map(directory):
    """pet actor id(int) -> owner player actor id(int), from masterData pets on fights.json. Used to
    fold a pet's (or totem's) damage/healing into its OWNER's spec for the per-spec timeline, so a BM
    hunter's pet or a warlock's felguard isn't dropped from that spec's curve. Graceful {} on older data
    folders that predate the pets fetch (per-spec curves then just exclude pet output)."""
    try:
        rep = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]
    except (OSError, KeyError, ValueError):
        return {}
    out = {}
    for p in (((rep.get("masterData") or {}).get("pets")) or []):
        if p.get("id") is not None and p.get("petOwner") is not None:
            out[int(p["id"])] = int(p["petOwner"])
    return out


def _spec_curves(by_source, n, secs, id_to_name, spec_map, role_map, class_map, pet_owner):
    """Fold one fight's per-source RAW bins (sourceID -> [amount per bin]) into per (class, spec) PER-PLAYER
    RATE curves. Each source is first resolved to a player (a pet folds into its owner), then attributed to
    that player's primary spec and pooled; the summed bins are divided by the bin width (`secs`) AND by the
    spec's distinct player count, so the curve is avg DPS/HPS PER PLAYER — matching the sibling DPS-by-Spec
    table (avg/player). Pooling totals instead would make the side with more players of a spec draw ~Nx
    taller even when each of its players is worse, flipping the read. Returns {"class|spec": {class, spec,
    role, players:int, curve:[rates]}}."""
    if not by_source or n <= 0 or secs <= 0:
        return {}
    folded = {}  # owner player id -> [raw sum per bin]
    for sid_str, arr in by_source.items():
        owner = pet_owner.get(int(sid_str), int(sid_str))  # pet -> owner; player -> itself
        f = folded.get(owner)
        if f is None:
            f = folded[owner] = [0.0] * n
        for i, v in enumerate(arr):
            f[i] += v
    pools = {}
    for owner, arr in folded.items():
        nm = id_to_name.get(owner)
        spec = spec_map.get(nm) if nm else None
        if not nm or not spec:
            continue  # only roster players with a known primary spec
        cls = class_map.get(nm) or "Unknown"
        key = "{}|{}".format(cls, spec)
        p = pools.setdefault(key, {"class": cls, "spec": spec, "role": role_map.get(nm),
                                   "sum": [0.0] * n, "players": set()})
        p["players"].add(owner)
        for i, v in enumerate(arr):
            p["sum"][i] += v
    return {key: {"class": p["class"], "spec": p["spec"], "role": p["role"], "players": len(p["players"]),
                  "curve": [round(x / secs / max(1, len(p["players"]))) for x in p["sum"]]}
            for key, p in pools.items()}


def spec_timelines(o_tl, t_tl, o_args, t_args):
    """Per-spec DPS/HPS-over-time curves for a boss, ours vs the benchmark's same spec — the data behind
    the per-spec Timeline sub-tabs. Restricted to specs BOTH raids fielded (the overlap): a spec only one
    raid ran has no same-spec curve to compare against, so showing it would be a misleading apples-to-
    oranges line (the same data-integrity rule as the potion/DPS gaps). A DPS-role spec carries its DPS
    curve; a healer spec carries its HPS curve. Returns [] when either side lacks timeline data."""
    if not o_tl or not t_tl:
        return []

    def side(tl, args):
        id_to_name, spec_map, role_map, class_map, pet = args
        n = tl.get("n") or len(tl.get("dps") or [])
        if not n or not tl.get("durMs"):
            return {}
        secs = (tl["durMs"] / n) / 1000.0
        dps = _spec_curves(tl.get("dpsBySource"), n, secs, id_to_name, spec_map, role_map, class_map, pet)
        hps = _spec_curves(tl.get("hpsBySource"), n, secs, id_to_name, spec_map, role_map, class_map, pet)
        out = {}
        for key, c in dps.items():
            if c["role"] == "dps":
                out[key] = dict(c, metric="dps")
        for key, c in hps.items():
            if c["role"] == "healer":
                out[key] = dict(c, metric="hps")  # healers compared on healing output
        return out

    o, t = side(o_tl, o_args), side(t_tl, t_args)
    rows = []
    for key in sorted(set(o) & set(t), key=repr):  # overlap only — both raids fielded this spec
        oc, tc = o[key], t[key]
        rows.append({"class": oc["class"], "spec": oc["spec"], "role": oc["role"], "metric": oc["metric"],
                     "oursPlayers": oc.get("players"), "theirsPlayers": tc.get("players"),
                     "ours": oc["curve"], "theirs": tc["curve"]})
    rows.sort(key=lambda r: (r["metric"] != "dps", r["class"], r["spec"]))  # DPS specs first, stable order

    # Aggregate "Melee DPS" / "Ranged DPS" curves: the whole melee or ranged core summed over time, ours
    # vs benchmark. Summed over the SAME (overlapping) DPS specs on both sides, so it stays apples-to-
    # apples — a leader sees the melee/ranged group's combined ramp and sustain, not just one spec.
    dps_rows = [r for r in rows if r["metric"] == "dps"]

    def _agg(melee):
        sel = [r for r in dps_rows if _is_melee(r["class"], r["spec"]) == melee]
        if not sel:
            return None
        m = len(sel[0]["ours"])
        o_sum, t_sum = [0] * m, [0] * m
        for r in sel:
            for i in range(m):
                o_sum[i] += r["ours"][i]
                t_sum[i] += r["theirs"][i]
        return {"spec": "Melee DPS" if melee else "Ranged DPS", "agg": "melee" if melee else "ranged",
                "role": "dps", "metric": "dps", "specCount": len(sel), "ours": o_sum, "theirs": t_sum}

    aggs = [a for a in (_agg(True), _agg(False)) if a]
    return aggs + rows  # aggregates first (after the Raid tab), then the individual specs


def _side_timeline(curves, deaths, lust_sec, dur_ms, fight_info):
    """One raid's timeline: DPS/HPS curves + markers placed at ABSOLUTE seconds into its own fight.
    Both sides share one real-time axis, so a shorter kill's line simply ends earlier — the gap is
    visible rather than hidden by 0-100% normalization, and the reader can place events in real time
    ('we lost DPS at 2:30')."""
    dur_sec = round(dur_ms / 1000)
    side = {
        "dps": curves["dps"], "hps": curves["hps"],
        "durSec": dur_sec,
        "deaths": [{"tSec": d["tSec"], "name": d["name"]} for d in deaths],
        "lustSec": lust_sec if lust_sec is not None else None,
        "phases": [],
    }
    start = int(fight_info["start"])
    for p in sorted(fight_info.get("phases") or [], key=lambda x: x["startTime"]):
        t_sec = round((int(p["startTime"]) - start) / 1000)
        # Skip the phase-1 boundary sitting at ~0s (it's just the pull, not a transition).
        if dur_ms > 0 and (int(p["startTime"]) - start) > dur_ms * 0.005:
            side["phases"].append({"id": int(p["id"]), "tSec": t_sec})
    return side


def timeline_view(o_curves, t_curves, o_deaths, t_deaths, o_lust, t_lust, o_dur, t_dur, o_info, t_info):
    """Per-boss DPS/HPS-over-time comparison on an absolute-seconds axis. None if either side lacks
    curve data (older data dir), so the template simply omits the Timeline sub-tab."""
    if not o_curves or not t_curves:
        return None
    return {
        "n": o_curves.get("n", len(o_curves["dps"])),
        "oursDurMs": int(o_dur), "theirsDurMs": int(t_dur),
        "ours": _side_timeline(o_curves, o_deaths, o_lust, o_dur, o_info),
        "theirs": _side_timeline(t_curves, t_deaths, t_lust, t_dur, t_info),
    }


def _targets_by_name(tl, npc_map, boss_name):
    """Per enemy NAME on one side: {count, medLifeSec, firstSec, isBoss}. Includes the BOSS (flagged
    `isBoss`) so it anchors the timeline and council / multi-boss fights surface every member. The boss is
    the target whose name == the encounter (fallback: the single highest-damage target — never hardcoded).
    Non-boss targets below 1% of fight damage are dropped as stray-cleave noise. Every real add is kept,
    long-lived ones included (a raid may hold an add by design). Lifespans are per-instance first-hit→last."""
    spans = ((tl or {}).get("focus") or {}).get("targetSpans") or {}
    if not spans:
        return {}
    total = sum(s.get("dmg", 0) for s in spans.values()) or 1
    name_match = {tid for tid, s in spans.items() if (npc_map.get(int(tid)) or "") == boss_name}
    boss_ids = name_match or {max(spans, key=lambda k: spans[k].get("dmg", 0))}
    agg = {}
    for tid, s in spans.items():
        nm = npc_map.get(int(tid))
        lifes = s.get("lifespans") or []
        if not nm or not lifes:
            continue
        rec = agg.setdefault(nm, {"count": 0, "lifes": [], "firstSec": None, "dmg": 0, "isBoss": False})
        rec["count"] += len(lifes)
        rec["lifes"].extend(lifes)
        rec["dmg"] += s.get("dmg", 0)
        if tid in boss_ids:
            rec["isBoss"] = True
        fs = s.get("firstSec")
        if fs is not None and (rec["firstSec"] is None or fs < rec["firstSec"]):
            rec["firstSec"] = fs
    out = {}
    for nm, r in agg.items():
        if not r["isBoss"] and r["dmg"] / total < 0.01:  # stray-cleave noise (non-boss, <1% of fight damage)
            continue
        out[nm] = {"count": r["count"], "firstSec": r["firstSec"], "isBoss": r["isBoss"],
                   "medLife": round(sorted(r["lifes"])[len(r["lifes"]) // 2], 1)}
    return out


def target_engagement(o_tl, t_tl, o_npc, t_npc, boss_name):
    """ADD KILL SPEED — the actionable read of the per-target spans (the old "engagement & survival"
    timeline was descriptive-but-inert; this reworks it into a ranked gap). For each non-boss ADD that
    EITHER raid engaged on a multi-target fight, how long it survived (median first-hit→last) ours vs the
    benchmark, ranked by how much SLOWER we are (our median − theirs). A slower add kill prolongs the
    add's damage and the fight, so an add the benchmark consistently kills faster is a focus / CC /
    assignment target. DESCRIPTIVE — some adds are held intentionally until called — but the benchmark
    sets the pace, so read it against your plan. The BOSS row is dropped (its engaged span just restates
    kill time) and so is the pure first-appearance timeline (not actionable on its own). The strongest case is a SKIPPED add: the benchmark killed the boss fast enough to never engage an add we
    had to fight (theirsLife=None, ×0) — it counts as 0 lifespan, so it ranks at the top as the biggest
    add-control gap. The reverse (an add WE skipped but they fought) surfaces as a lead. Returns [] only when
    neither raid engaged any non-boss add (a clean single-target kill)."""
    oa = _targets_by_name(o_tl, o_npc, boss_name)
    ta = _targets_by_name(t_tl, t_npc, boss_name)
    rows = []
    for nm in sorted(set(oa) | set(ta), key=repr):
        o, t = oa.get(nm), ta.get(nm)
        if (o and o.get("isBoss")) or (t and t.get("isBoss")):
            continue  # the boss itself — its span just restates kill time
        o_life = o["medLife"] if o else None
        t_life = t["medLife"] if t else None
        rows.append({"name": nm, "oursLife": o_life, "theirsLife": t_life,
                     # a side that never engaged the add = 0 lifespan: skipping it entirely is the extreme
                     # of "killed faster", so the raid that fought it carries the full gap and ranks first.
                     "deficit": round((o_life or 0) - (t_life or 0), 1),
                     "oursCount": o["count"] if o else 0, "theirsCount": t["count"] if t else 0,
                     "oursSkipped": o is None, "theirsSkipped": t is None})
    rows.sort(key=lambda r: -r["deficit"])  # adds we're slowest on (or that the benchmark skipped) first
    return rows


def threat_pulls(report, fight_info, role_map, boss_name, opener_sec=30, max_band_sec=15,
                 spec_map=None, class_map=None):
    """Early-aggro / threat pulls: a NON-TANK roster player who held the NAMED BOSS's aggro (`table(Threat)`
    bands). Scoped two ways to stay clean (both verified against real fights): (1) to the boss target by
    name — counting all enemies over-counts badly on multi-add fights (Al'ar reads 131% tank-uptime, Kael
    62%); (2) to BRIEF bands (<= max_band_sec) — a sustained hold is an intended off-tank, not a snap pull.
    Tanks are excluded (holding aggro is their job); pets and non-roster actors are excluded (only roster
    players count). This UNDER-counts rather than over-counts — a long pull, or a parse-mis-roled feral
    off-tank, is dropped, never falsely flagged. Returns total pulls + opener (first `opener_sec`) +
    earliest pull time + a per-(class,spec) breakdown (`bySpec`/`openerBySpec`) so the count names WHO to
    address (Misdirection/Vanish/hold-for-tanks assignment), not just THAT there's an aggro problem."""
    start = int(fight_info["start"])
    threat = ((report.get("threat") or {}).get("data") or {}).get("threat") or []
    pulls = []
    by_spec, opener_by_spec = {}, {}
    casts = None  # per-fight cast mix, computed lazily only to disambiguate a dps-classified bear Feral
    for t in threat:
        nm = t.get("name")
        if nm not in role_map or role_map.get(nm) == "tank":
            continue  # only roster non-tank players (tanks/pets/NPCs excluded)
        # role_map is the WHOLE-REPORT majority role. A Feral Druid logged as "dps" overall may have
        # BEAR-TANKED this specific fight — holding the boss is then her job, not a threat pull. Use the
        # per-fight cast mix (bear abilities vs cat) to catch that and skip her, so we don't flag a tanking
        # bear as her own aggro problem. Druid-only check; cast table fetched once on first Druid seen.
        if (class_map or {}).get(nm) == "Druid":
            if casts is None:
                casts = _casts_by_name(report)
            if _druid_form(casts.get(nm, {})) == "bear":
                continue
        for tg in (t.get("targets") or []):
            if tg.get("name") != boss_name:
                continue  # scope to the actual boss, not its adds
            for b in (tg.get("bands") or []):
                dur = (int(b["endTime"]) - int(b["startTime"])) / 1000.0
                rel = (int(b["startTime"]) - start) / 1000.0
                if 0 <= dur <= max_band_sec and rel >= 0:
                    pulls.append(round(rel))
                    # Spec attribution (same under-count as the total — only brief boss-target holds).
                    sp = (spec_map or {}).get(nm)
                    if sp:
                        key = "{}|{}".format((class_map or {}).get(nm) or "Unknown", sp)
                        by_spec[key] = by_spec.get(key, 0) + 1
                        if rel <= opener_sec:
                            opener_by_spec[key] = opener_by_spec.get(key, 0) + 1
    pulls.sort()
    return {"total": len(pulls), "opener": sum(1 for r in pulls if r <= opener_sec),
            "earliestSec": pulls[0] if pulls else None,
            "bySpec": by_spec, "openerBySpec": opener_by_spec}


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


# ---------- ACTIVITY BY SPEC (per-player active-GCD uptime, from dd activeTime) — EXPERIMENTAL ----------
def spec_gap(o_report, t_report, o_spec, o_role, o_cls, t_spec, t_role, t_cls, o_dur, t_dur):
    """Per-spec DPS comparison for one boss, ranked by the per-player deficit to the
    benchmark's same spec (biggest gap first → lowest-hanging fruit floats to the top).
    Compares AVERAGE DPS per player so a 3-mage vs 2-mage roster is still fair. `both`
    flags specs only one raid brought (a different kind of gap — surfaced as a roster
    story on the Composition tab, not in the per-boss chart)."""
    ob = spec_dps_buckets(o_report, o_spec, o_role, o_cls, o_dur)
    tb = spec_dps_buckets(t_report, t_spec, t_role, t_cls, t_dur)
    rows = []
    for key in sorted(set(ob) | set(tb), key=repr):
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
def _death_cause_label(d, boss_name):
    """Killing-blow label for the tier-wide death table. Appends the SOURCE MOB in parens when an ADD
    (not the boss) landed the blow — 'Arcing Smash (Coilfang Guardian)' on Lurker vs a bare 'Arcing Smash'
    on Maulgar — turning a shared ability name into an actionable 'kill the add' assignment. Mirrors the
    Trash 'What's Killing Us' labelling. Bare cause when the boss itself (or no enemy actor) landed it."""
    cause = d.get("killedBy") or "Unknown"
    mob = d.get("srcMob")
    return "{} ({})".format(cause, mob) if mob and mob != boss_name else cause


def death_causes(per_boss, side):
    """Per (killing-blow label, boss): how many of `side`'s deaths it caused. One entry PER BOSS (not
    pooled across bosses), so the tier table can split e.g. 'Melee on Vashj' from 'Melee on Maulgar'
    instead of burying both in one total. Returns {(label, boss): count}."""
    agg = {}
    for pb in per_boss:
        for d in pb["deaths"][side]:
            key = (_death_cause_label(d, pb["name"]), pb["name"])
            agg[key] = agg.get(key, 0) + 1
    return agg


def ghost_run_for_boss(deaths, dur_ms, raid_dps, avg_dps):
    """The counterfactual "ghost run" for ONE boss: if nobody had died, how much output did the deaths
    forfeit — and (as a clearly-bounded estimate) how much sooner could it have died? Each death forfeits
    the dead raider's **average DPS across the raid night** (`avg_dps` — a stable, sustainable rate, not a
    single-fight burst) for the time they were down. Summed = forfeited damage (the SOLID number — "their
    normal output × time dead"), also shown as a share of the raid's actual damage on the boss. Dividing by
    the raid's DPS gives an **upper-bound** kill-time (a pure-DPS-race estimate; phase-gated fights — air
    phases, scripted transitions — cap how much extra DPS actually compresses, so it's a ceiling, not a
    claim). Names who forfeited most, to coach not shame. Returns None when nobody died / no usable data."""
    dur_sec = dur_ms / 1000.0
    if dur_sec <= 0 or raid_dps <= 0:
        return None
    forfeited, per = 0.0, {}
    for d in deaths:
        nm, t = d.get("name"), d.get("tSec")
        rate_ = avg_dps.get(nm)
        if not rate_ or t is None or t <= 0 or t >= dur_sec:
            continue
        f = rate_ * (dur_sec - t)                  # their NIGHT-AVERAGE DPS, projected over the time down
        forfeited += f
        rec = per.setdefault(nm, {"name": nm, "class": d.get("class"), "dmg": 0.0, "sec": t,
                                  "rate": round(rate_)})
        rec["dmg"] += f
        rec["sec"] = min(rec["sec"], t)
    if forfeited <= 0:
        return None
    raid_dmg = raid_dps * dur_sec
    raiders = sorted(per.values(), key=lambda r: -r["dmg"])
    # Time saved = forfeited ÷ the GHOST raid DPS (actual + the revived raiders' own DPS), NOT the actual
    # raid DPS — if those raiders were alive they'd ALSO be speeding the kill, so the extra damage lands
    # against a faster raid. (Each dead PLAYER counts once toward the ghost DPS, not once per death.) This
    # is the self-consistent kill-time and is smaller than forfeited/actual-DPS, which over-states it.
    ghost_raid_dps = raid_dps + sum(avg_dps.get(nm, 0) for nm in per)
    return {"timeSavedSec": round(forfeited / ghost_raid_dps),
            "forfeitedDmg": round(forfeited),
            "pctOfRaid": round(100 * forfeited / raid_dmg, 1) if raid_dmg > 0 else 0,
            "deaths": sum(1 for d in deaths if avg_dps.get(d.get("name")) and (d.get("tSec") or 0) > 0),
            "durSec": round(dur_sec), "raidDps": round(raid_dps),
            "raiders": [{"name": r["name"], "class": r["class"], "dmg": round(r["dmg"]),
                         "sec": round(r["sec"]), "rate": r["rate"]} for r in raiders]}


def avoidable_damage_gap(o_acc, t_acc, o_dur_ms, t_dur_ms, n=12):
    """Tier-wide avoidable damage by MECHANIC — the damage analog of What's Killing Us (which counts the
    deaths). Pools each non-tank damage-taken ABILITY across the shared bosses, ours vs benchmark, as a
    **per-second rate** (normalized for fight length — the honest frame, since the two raids' fights differ
    in length, so raw totals would just track who fought longer), ranked by where WE take the most MORE.
    Damage taken is the LEADING indicator *before* anyone dies, so a mechanic we eat far more of than the
    benchmark is the next thing to dodge — actionable at the ability grain. EXPERIMENTAL. (Ex-tanks via
    `ability_agg`; roster sizes differ slightly, an accepted minor caveat noted in the UI.)"""
    rows = []
    for nm in sorted(set(o_acc) | set(t_acc), key=repr):
        o_ps = round(o_acc.get(nm, 0) * 1000 / o_dur_ms) if o_dur_ms > 0 else 0
        t_ps = round(t_acc.get(nm, 0) * 1000 / t_dur_ms) if t_dur_ms > 0 else 0
        if o_ps <= 0 and t_ps <= 0:
            continue
        rows.append({"name": nm, "ours": o_ps, "theirs": t_ps, "deficit": o_ps - t_ps})
    rows.sort(key=lambda r: -r["deficit"])  # where we take the most MORE than the benchmark, first
    return rows[:n]


def death_cause_compare(per_boss):
    """Ranked ours-vs-theirs death-cause table, ONE ROW PER (killing blow, boss), biggest improvable
    delta first. Splitting by boss (vs pooling a cause across the clear) makes the gap actionable: '7
    Melee deaths on Vashj vs 0' points at one fight to fix, where a pooled '11 Melee across 4 bosses'
    hides where to look. Ranked by payoff: biggest IMPROVABLE delta first (a death the benchmark avoids
    and we don't), then raw ours, then theirs — mirrors the trash death-cause sort."""
    o = death_causes(per_boss, "ours")
    t = death_causes(per_boss, "theirs")
    rows = []
    for key in sorted(set(o) | set(t), key=repr):
        label, boss = key
        rows.append({"cause": label, "boss": boss, "ours": o.get(key, 0), "theirs": t.get(key, 0)})
    rows.sort(key=lambda r: (-(r["ours"] - r["theirs"]), -r["ours"], -r["theirs"]))
    return rows


def death_time_compare(per_boss, o_avail, t_avail):
    """Output-TIME lost to deaths, by killing-blow cause, pooled across the shared clear — EXPERIMENTAL.
    Each death costs (fight end − death time) player-seconds of lost output; we sum that per cause and
    rank by the biggest improvable delta. The TIME companion to 'What's Killing Us' (which COUNTS deaths):
    not how OFTEN a mechanic kills, but how much raid output-time it burns — a death at 90% boss-HP costs
    far more than one at 2%. UPPER BOUND: assumes a downed raider stays down, so a battle-res reduces it.
    o_avail/t_avail = roster × total shared-boss fight time (player-seconds) = the base for the % lost."""
    def by_cause(side):
        agg, dur_key = {}, ("oursDurMs" if side == "ours" else "theirsDurMs")
        for pb in per_boss:
            dsec = round(pb[dur_key] / 1000)
            for d in pb["deaths"][side]:
                cost = max(0, dsec - int(d.get("tSec", 0)))
                lbl = _death_cause_label(d, pb["name"])
                agg[lbl] = agg.get(lbl, 0) + cost
        return agg
    o, t = by_cause("ours"), by_cause("theirs")
    rows = [{"cause": c, "oursMin": round(o.get(c, 0) / 60, 1), "theirsMin": round(t.get(c, 0) / 60, 1),
             "deficitMin": round((o.get(c, 0) - t.get(c, 0)) / 60, 1)} for c in sorted(set(o) | set(t), key=repr)]
    rows.sort(key=lambda r: (-r["deficitMin"], -r["oursMin"]))
    o_total, t_total = sum(o.values()), sum(t.values())
    return {"rows": rows[:15],
            "oursMin": round(o_total / 60, 1), "theirsMin": round(t_total / 60, 1),
            "oursPct": round(100 * o_total / o_avail, 1) if o_avail > 0 else 0,
            "theirsPct": round(100 * t_total / t_avail, 1) if t_avail > 0 else 0}


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
        rec = out.setdefault(enc, {"kills": 0, "wipes": 0, "bestWipePct": None, "bestWipePhase": None})
        if f.get("kill"):
            rec["kills"] += 1
        else:
            rec["wipes"] += 1
            # Wipe DEPTH: the closest attempt = the wipe with the LOWEST boss-HP% remaining
            # (fightPercentage). Track it + the phase it died in, so a progression wall surfaces
            # ("best Kael'thas attempt: 21.6%, P5"). fightPercentage may be absent on older data.
            pct = f.get("fightPercentage")
            if pct is not None and (rec["bestWipePct"] is None or float(pct) < rec["bestWipePct"]):
                rec["bestWipePct"] = round(float(pct), 1)
                rec["bestWipePhase"] = f.get("lastPhase")
    for rec in out.values():
        rec["attempts"] = rec["kills"] + rec["wipes"]
    return out


def wipe_recovery(directory):
    """Per encounter, the average wall-clock gap between a WIPE ending and the next pull starting — how
    long the raid takes to reset/rebuff/re-pull (a raid-night pacing read on progression). EXPERIMENTAL.
    Needs attempts.json with startTime/endTime (older folders without them → empty, graceful). The gap is
    recovery + prep + any break, so it's directional (less = tighter), not a pure mechanical reset."""
    path = os.path.join(directory, "attempts.json")
    if not os.path.isfile(path):
        return {}
    fights = read_json(path)["reportData"]["report"]["fights"]
    by_enc = {}
    for f in fights:
        enc = str(f.get("encounterID"))
        if not enc or enc == "0" or f.get("startTime") is None or f.get("endTime") is None:
            continue
        by_enc.setdefault(enc, []).append(f)
    out = {}
    for enc, fl in by_enc.items():
        fl.sort(key=lambda f: f["startTime"])
        gaps = [(fl[i + 1]["startTime"] - fl[i]["endTime"]) / 1000.0
                for i in range(len(fl) - 1) if not fl[i].get("kill")]  # gap after each wipe pull
        gaps = [g for g in gaps if g >= 0]
        if gaps:
            out[enc] = {"avgSec": round(sum(gaps) / len(gaps)), "maxSec": round(max(gaps)), "wipes": len(gaps)}
    return out


def wipe_recovery_compare(o_rec, t_rec, enc_names):
    """Per-boss wipe-recovery rows (bosses WE wiped), ours vs benchmark where they also wiped, slowest
    reset first, plus a raid aggregate. Largely a FIRST-PARTY pacing view — a benchmark on farm wipes
    little, so theirs is often absent (shown '—'); that's expected, not a hole. EXPERIMENTAL."""
    rows = []
    o_tot_gap = o_tot_n = t_tot_gap = t_tot_n = 0
    for enc, o in o_rec.items():
        t = t_rec.get(enc)
        rows.append({"boss": enc_names.get(enc, enc), "oursAvg": o["avgSec"], "oursMax": o["maxSec"],
                     "oursWipes": o["wipes"], "theirsAvg": (t or {}).get("avgSec"),
                     "theirsWipes": (t or {}).get("wipes")})
        o_tot_gap += o["avgSec"] * o["wipes"]
        o_tot_n += o["wipes"]
        if t:
            t_tot_gap += t["avgSec"] * t["wipes"]
            t_tot_n += t["wipes"]
    rows.sort(key=lambda r: -r["oursAvg"])
    return {"rows": rows,
            "oursAvg": round(o_tot_gap / o_tot_n) if o_tot_n else None,
            "theirsAvg": round(t_tot_gap / t_tot_n) if t_tot_n else None,
            "oursWipes": o_tot_n, "theirsWipes": t_tot_n}


# ---------- TIER-WIDE GAP ROLLUPS (stitch per-boss data into one comprehensive view) ----------
def tier_spec_gap(o_pool, t_pool):
    """Comprehensive "lowest-hanging fruit" view: pool every DPS player's per-boss DPS by spec across
    ALL shared bosses, then rank specs by the per-player deficit to the benchmark's same spec. Floats
    the spec that's most behind tier-wide to the top — that's where coaching pays off most."""
    rows = []
    for key in sorted(set(o_pool) | set(t_pool), key=repr):
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


def load_enemy_debuffs(directory, enc):
    """enemydebuffs-<enc>.json for one boss (per-enemy-target debuff uptime), or None if absent."""
    p = os.path.join(directory, "enemydebuffs-{}.json".format(enc))
    if not os.path.isfile(p):
        return None
    try:
        return read_json(p)
    except (OSError, ValueError):
        return None


def per_target_debuffs(o_dir, t_dir, enc):
    """The ZOOM under the aggregate Boss Debuffs: which specific ENEMY each KEY raid debuff lands on, ours vs
    benchmark, for one boss. Uptime is normalized to each target's ACTIVE window (the time that enemy was
    engaged), not the whole fight — so a council add tanked for 40s reads "how well we held the curse WHILE we
    fought it," the honest grain. Targets are matched across raids by NAME. Only surfaced when there's a real
    multi-target split (≥2 distinct enemies carry a key debuff) — on a single-target boss the aggregate bar
    already says everything and this would just repeat it. Returns a list of per-target groups, each with the
    key-debuff rows present on it (ours/theirs % of that enemy's active window), or [] when there's no split."""
    o = load_enemy_debuffs(o_dir, enc)
    t = load_enemy_debuffs(t_dir, enc)
    if not o and not t:
        return []

    def by_name(side):
        return {tg["name"]: tg for tg in ((side or {}).get("targets") or [])}
    om, tm = by_name(o), by_name(t)

    def upt(tg, ability):
        """(value, ok): uptime % over the enemy's engaged window, or 0 when the debuff was never applied /
        the enemy is absent on this side. ok=False when the raw debuff ms is implausibly larger than that
        enemy's active window — a multi-instance pooling / fight-end force-close artifact (seen at 600-1500%
        on reused phased-add NPC ids) that would otherwise CLAMP to a fake clean 100% and manufacture a
        false 'they held it, you didn't' assignment lever. Such cells are dropped, not laundered."""
        if not tg:
            return 0, True  # enemy not present on this side -> an honest 0%
        active = tg.get("activeMs") or 0
        ms = (tg.get("debuffs") or {}).get(ability)
        if not active or ms is None:
            return 0, True  # debuff never landed on this enemy -> 0%
        if ms > active * 1.1:
            return None, False  # raw uptime far exceeds the engaged window -> data artifact, unmeasurable
        return min(100, round(ms / active * 100)), True

    groups = []
    for nm in sorted(set(om) | set(tm)):
        o_tg, t_tg = om.get(nm), tm.get(nm)
        rows = []
        for ability in KEY_DEBUFFS:
            o_u, o_ok = upt(o_tg, ability)
            t_u, t_ok = upt(t_tg, ability)
            if not o_ok or not t_ok:
                continue  # unmeasurable on at least one side -> not a valid comparison, drop the row
            if (o_u or 0) < 5 and (t_u or 0) < 5:
                continue  # neither raid meaningfully held this debuff on this enemy
            rows.append({"name": ability, "ours": o_u or 0, "theirs": t_u or 0,
                         "deficit": (t_u or 0) - (o_u or 0)})
        if rows:
            rows.sort(key=lambda r: -r["deficit"])
            groups.append({"target": nm, "rows": rows})
    # Only a real split is worth the zoom: a single enemy carrying the debuffs == the aggregate bar already.
    if len(groups) < 2:
        return []
    # Rank targets by the biggest single deficit on them (where coverage most slipped vs the benchmark), and
    # cap to the worst few — a phased fight (Kael'thas weapons) can field a dozen enemies; showing them all is
    # a data dump. The top offenders carry the lever; the rest repeat it.
    groups.sort(key=lambda g: -max(r["deficit"] for r in g["rows"]))
    return groups[:6]


def tier_debuff_timing(acc):
    """Debuff RAMP + CONTINUITY across the shared bosses — EXPERIMENTAL. Per key debuff, average the
    establish-time (sec into fight before it first lands) and the longest continuous gap, ours vs theirs,
    over the bosses each side ran it on. Ranked by the biggest establish-delay deficit (we're slowest to
    get it up). The benchmark column is the honest frame: a phased fight delays the boss debuff on BOTH
    sides, so the DELTA — not the raw seconds — is the signal. Only debuffs both raids actually applied."""
    rows = []
    for nm, r in acc.items():
        if not (r["o_est"] and r["t_est"]):
            continue  # need both sides for a fair ramp comparison
        rows.append({
            "name": nm,
            "oursEst": round(sum(r["o_est"]) / len(r["o_est"])),
            "theirsEst": round(sum(r["t_est"]) / len(r["t_est"])),
            "oursGap": round(sum(r["o_gap"]) / len(r["o_gap"])) if r["o_gap"] else 0,
            "theirsGap": round(sum(r["t_gap"]) / len(r["t_gap"])) if r["t_gap"] else 0,
        })
    rows.sort(key=lambda r: -(r["oursEst"] - r["theirsEst"]))
    return rows


# ---------- CASTS: cooldown/trinket usage ----------
# Major on-demand DPS cooldowns, classified by NAME. **Sourced from BUFFS, not Casts:** verified live
# in TBC, the marquee off-GCD cooldowns (Death Wish, Recklessness, Bestial Wrath, Rapid Fire, Arcane
# Power, Icy Veins, ...) generate NO cast events — they log only as buffs, where the table carries a
# `totalUses` (= activation) count. Reading them from Casts silently missed hunters'/warriors' signature
# CDs entirely; reading the per-player buff `uses` captures them. (Trinkets are the opposite — see below.)
COOLDOWN_NAMES = {
    "Death Wish", "Recklessness",                                                # Warrior
    "Adrenaline Rush", "Blade Flurry",                                           # Rogue
    "Arcane Power", "Icy Veins", "Combustion", "Presence of Mind", "Cold Snap",  # Mage
    "Rapid Fire", "Bestial Wrath",                                               # Hunter
    "Elemental Mastery",                                                         # Shaman (Elemental)
    "Power Infusion",                                                            # Priest burst (often onto a DPS)
    "Blood Fury", "Berserking",                                                  # Racials (Orc / Troll)
}
# On-use DPS trinkets, classified by NAME — sourced from CASTS, the mirror image of the cooldowns above:
# a trinket's USE logs as a cast under its item name, but its resulting BUFF is renamed by WCL to the
# effect ("Haste", etc.), so the buff table can't be matched by item name. Casts is the right source.
# Disjoint from COOLDOWN_NAMES (CDs←buffs, trinkets←casts), so the two never double-count. Extensible.
TRINKET_NAMES = {
    "Abacus of Violent Odds", "Bloodlust Brooch", "Icon of the Silver Crescent", "Shard of Contempt",
    "Berserker's Call", "Bladefist's Breadth", "Shifting Naaru Sliver", "Hourglass of the Unraveller",
}


def cd_usage_pool(directory, idx, enc_ids, spec_map, role_map, class_map, fights):
    """Per (class, primary spec) DPS cooldown+trinket activations PER MINUTE, pooled across shared bosses.
    Combines TWO sources per player so neither blind spot bites (and they can't double-count, being
    disjoint): buff `uses` for the cooldowns (consumes-<enc>.json — the only place TBC records them) and
    cast `total` for on-use trinkets (boss-<enc>.json Casts — where trinkets keep their item name).
    Per-player so we can bucket by spec; normalized by fight length so a longer fight doesn't inflate it.
    Graceful: a boss with no consumes file (older data / non-shared) is skipped."""
    name_to_id = name_id_map(directory)
    id_to_name = {v: k for k, v in name_to_id.items()}
    pool = {}
    for enc in enc_ids:
        fi = fights.get(str(enc))
        cons_path = os.path.join(directory, "consumes-{}.json".format(enc))
        if not fi or not os.path.isfile(cons_path):
            continue
        mins = max(int(fi["end"]) - int(fi["start"]), 1) / 60000.0
        count_by_name = {}  # player name -> {cooldown/trinket name -> activations this boss}
        # 1) Cooldowns from per-player BUFF uses.
        for pid, auras in (read_json(cons_path).get("perPlayer") or {}).items():
            nm = id_to_name.get(int(pid)) if str(pid).isdigit() else None
            if nm:
                d = count_by_name.setdefault(nm, {})
                for a in (auras or []):
                    if a.get("name") in COOLDOWN_NAMES:
                        d[a["name"]] = d.get(a["name"], 0) + int(a.get("uses", 0))
        # 2) On-use trinkets from CASTS (the resulting buff is renamed, so casts is the only match).
        boss_path = os.path.join(directory, "boss-{}.json".format(enc))
        if os.path.isfile(boss_path):
            rep = read_json(boss_path)["reportData"]["report"]
            for e in _entries(rep, "casts"):
                nm = e.get("name")
                if nm:
                    d = count_by_name.setdefault(nm, {})
                    for a in (e.get("abilities") or []):
                        if a.get("name") in TRINKET_NAMES:
                            d[a["name"]] = d.get(a["name"], 0) + int(a.get("total", 0))
        for nm, abil_counts in count_by_name.items():
            spec = spec_map.get(nm)
            if not spec or role_map.get(nm) != "dps":
                continue
            cls = class_map.get(nm) or "Unknown"
            b = pool.setdefault("{}|{}".format(cls, spec),
                                {"class": cls, "spec": spec, "abilUses": {}, "minsTotal": 0.0})
            # Per-cooldown pooled totals (uses + the player-minutes they were on the boss) so both the spec
            # total and the breakdown share one minutes-weighted denominator and reconcile: a spec's pooled
            # per-minute rate, cooldown by cooldown.
            b["minsTotal"] += mins
            for an, c in abil_counts.items():
                b["abilUses"][an] = b["abilUses"].get(an, 0) + c
    return pool


def tier_cd_usage(o_pool, t_pool):
    """Tier-wide cooldown-usage rollup: each spec's per-minute CD activations across all shared bosses, ours
    vs the benchmark's same spec, ranked by the biggest deficit (where we most sit on our cooldowns). Only
    specs BOTH raids fielded are scored; same shape/ordering as tier_spec_gap. Each row also carries a
    per-cooldown breakdown (`byAbility`) — the spec's pooled rate cooldown by cooldown vs the benchmark's same
    spec — so the leader sees the actual lever (which CD to push), not just the spec total.

    The spec total is the SAME minutes-weighted pooled rate as the breakdown (total activations / total
    player-minutes on the boss), so the per-cooldown rows sum to the spec total — they reconcile by
    construction (modulo ±0.01 display rounding), rather than the total being an unweighted mean-of-rates that
    silently disagreed with the minutes-weighted breakdown beneath it."""
    def pooled_rate(pool_ent, ability):
        m = pool_ent.get("minsTotal", 0) if pool_ent else 0
        return round(pool_ent["abilUses"].get(ability, 0) / m, 2) if m else 0

    def pooled_total(pool_ent):
        m = pool_ent.get("minsTotal", 0) if pool_ent else 0
        return round(sum((pool_ent.get("abilUses") or {}).values()) / m, 2) if m else 0
    rows = []
    for key in sorted(set(o_pool) | set(t_pool), key=repr):
        o, t = o_pool.get(key), t_pool.get(key)
        ref = o or t
        o_avg = pooled_total(o)
        t_avg = pooled_total(t)
        # Per-cooldown breakdown: every cooldown/trinket either side's same spec used, pooled to a per-minute
        # rate, ranked by the biggest deficit (where this spec most sits on a specific cooldown). Same
        # denominator (minsTotal) as the spec total above, so the rows sum back to it.
        abilities = set((o or {}).get("abilUses", {})) | set((t or {}).get("abilUses", {}))
        by_ability = []
        for an in abilities:
            o_ar, t_ar = pooled_rate(o, an), pooled_rate(t, an)
            if o_ar == 0 and t_ar == 0:
                continue
            by_ability.append({"name": an, "ours": o_ar, "theirs": t_ar, "deficit": round(t_ar - o_ar, 2)})
        by_ability.sort(key=lambda a: -a["deficit"])
        both = bool(o and o.get("minsTotal")) and bool(t and t.get("minsTotal"))
        rows.append({"class": ref["class"], "spec": ref["spec"], "ours": o_avg, "theirs": t_avg,
                     "deficit": round(t_avg - o_avg, 2), "both": both,
                     "byAbility": by_ability})
    rows.sort(key=lambda r: (not r["both"], -r["deficit"]))
    return rows


def _casts_by_name(report):
    """{player name -> {ability name -> total casts}} for one boss report's Casts table. Powers the
    Optimize tab, which compares each of OUR raiders' cast mix to a world-best player on the same boss."""
    out = {}
    for e in _entries(report, "casts"):
        nm = e.get("name")
        if not nm:
            continue
        d = out.setdefault(nm, {})
        for a in (e.get("abilities") or []):
            an = a.get("name")
            if an:
                d[an] = d.get(an, 0) + int(a.get("total", 0))
    return out


def _rotation_diff(p_abil, w_abil, min_share, top):
    """One raider's cast mix vs the world-best player's, as ability cast-SHARE rows (ours%, theirs%, Δ),
    biggest divergence first — per-individual-player vs a single same-faction world-best benchmark. Powers
    the Optimize tab. None if either side has no casts. `min_share` drops trivial fillers so the rotation's
    backbone shows, not noise."""
    p_tot, w_tot = sum(p_abil.values()), sum(w_abil.values())
    if p_tot <= 0 or w_tot <= 0:
        return None
    rows = []
    for an in sorted(set(p_abil) | set(w_abil), key=repr):
        o_pct = 100.0 * p_abil.get(an, 0) / p_tot
        t_pct = 100.0 * w_abil.get(an, 0) / w_tot
        if max(o_pct, t_pct) < min_share:
            continue
        rows.append({"name": an, "ours": round(o_pct, 1), "theirs": round(t_pct, 1),
                     "diff": round(o_pct - t_pct, 1)})
    rows.sort(key=lambda x: -abs(x["diff"]))
    return rows[:top]


# TBC Feral druid is ONE spec for TWO forms/roles (cat DPS vs bear tank/threat). WCL's role label can
# disagree with what a player actually did on a fight — a Feral logged as "dps" may have been in BEAR form
# (parsing low on the DPS metric while threat-tanking). Their casts are the ground truth: bear abilities
# (Lacerate/Maul/Swipe) vs cat (Shred/Rake/Mangle-Cat). We use this to keep the Optimize comparison
# like-for-like — a bear Feral must NOT be benchmarked against a cat-DPS world best, or the form mismatch
# reads as a huge phantom rotation gap (Lacerate 55% vs Shred 55%). Mangle is form-suffixed in the log.
_DRUID_BEAR_ABILITIES = {"Maul", "Lacerate", "Swipe", "Mangle (Bear)", "Demoralizing Roar",
                         "Bear Form", "Dire Bear Form", "Frenzied Regeneration", "Enrage"}
_DRUID_CAT_ABILITIES = {"Shred", "Rake", "Mangle (Cat)", "Claw", "Ferocious Bite", "Rip",
                        "Tiger's Fury", "Cat Form", "Ravage", "Pounce"}


def _druid_form(abil):
    """A Feral druid's FORM from their cast mix: 'bear' vs 'cat' (None if neither's abilities appear).
    Counts cast TOTALS (not ability variety), so a few stray Cat Form shifts don't flip a tanking bear."""
    bear = sum(v for k, v in abil.items() if k in _DRUID_BEAR_ABILITIES)
    cat = sum(v for k, v in abil.items() if k in _DRUID_CAT_ABILITIES)
    if bear == 0 and cat == 0:
        return None
    return "bear" if bear > cat else "cat"


def build_optimize(ours_dir, ours_idx, ours_spec, ours_cls, shared_encs,
                   min_share=3.0, top=10, collapse_diff=5.0, hit_map=None):
    """Optimize tab payload: per class -> per spec -> PER SHARED BOSS, each of OUR raiders' rotation
    benchmarked against the same-faction WORLD-BEST player of that exact class/spec ON THAT BOSS. Reads
    `worldbest.json` (written in the fetch stage by fetch_worldbest, now per boss); pure/deterministic
    here. Graceful {"present": False} when the file is absent (older data folders) or no guild faction was
    resolvable.

    Two integrity rules make every gap a real one:
      • PER BOSS, not pooled — our raider's casts and the world-best's casts are summed on the SAME
        encounter and compared there, so the gap is a true per-boss rotation read (the user wants the
        breakdown for EACH boss, not one tier-wide average that blends fights).
      • FORM/ROLE-AWARE — a raider is compared on a boss only if the role they ACTUALLY played there (from
        that boss's parse rankings) matches the benchmark's role. A Feral who bear-TANKED Al'ar is excluded
        from Al'ar's cat-DPS benchmark (a bear-vs-cat 'gap' is a role mismatch, not a rotation gap), but
        still compared on the bosses where she DPS'd. Spec/class still match the roster's primary."""
    wb = read_json(os.path.join(ours_dir, "worldbest.json")) if \
        os.path.isfile(os.path.join(ours_dir, "worldbest.json")) else None
    if not wb or not wb.get("present"):
        return {"present": False}

    # Cache per-boss casts-by-name + per-boss player role/parse so multiple specs reuse one load per boss.
    boss_casts, boss_meta = {}, {}

    def _casts_for(enc):  # enc: str
        if enc not in boss_casts:
            rep = load_boss(ours_dir, enc)
            boss_casts[enc] = _casts_by_name(rep) if rep else {}
        return boss_casts[enc]

    def _meta_for(enc):  # enc: str -> {name: {"role","parse"}} from THIS boss's parse rankings
        if enc not in boss_meta:
            m = {}
            for p in (ours_idx.get(enc, {}).get("players") or []):
                m.setdefault(p["name"], {"role": p.get("role"), "parse": p.get("parse")})
            boss_meta[enc] = m
        return boss_meta[enc]

    by_class = {}
    for sp in (wb.get("specs") or []):
        cls, spec, role = sp.get("class"), sp.get("spec"), sp.get("role")
        metric = sp.get("metric")
        slot = by_class.setdefault(cls, [])
        spec_bosses = []
        shared_set = {int(e) for e in (shared_encs or [])}
        for bn in (sp.get("bosses") or []):
            enc = bn.get("encounterID")
            # Defensive: never render a boss outside the CURRENT shared set even if a stale worldbest.json
            # from a prior benchmark pairing lingered (the cache key now guards this, but belt-and-suspenders).
            if shared_set and int(enc) not in shared_set:
                continue
            player = bn.get("player") or {}
            w_abil = bn.get("abilities") or {}
            casts = _casts_for(str(enc))
            meta = _meta_for(str(enc))
            # For a Feral spec, the benchmark's own form on THIS boss (cat for a DPS world best) — our
            # raiders must match it, so a bear isn't compared to a cat rotation.
            bench_form = _druid_form(w_abil) if (cls == "Druid" and spec == "Feral") else None
            players = []
            for nm, p_abil in casts.items():
                mm = meta.get(nm)
                if not mm:
                    continue
                # Same class + roster primary spec, AND the raider played THIS role on THIS boss
                # (form/role-aware — excludes a bear-tank from the cat-DPS benchmark).
                if ours_cls.get(nm) != cls or ours_spec.get(nm) != spec or mm.get("role") != role:
                    continue
                # Feral form check from CASTS: even when WCL labels a bear "dps", their bear cast mix
                # (Lacerate/Maul) must not be benchmarked against a cat-DPS world best (Shred/Rake).
                if bench_form is not None and _druid_form(p_abil) not in (None, bench_form):
                    continue
                abil = _rotation_diff(p_abil, w_abil, min_share, top)
                if not abil:
                    continue
                max_diff = max((abs(a["diff"]) for a in abil), default=0.0)
                players.append({"name": nm, "parse": mm.get("parse"),
                                "matches": max_diff <= collapse_diff, "maxDiff": round(max_diff, 1),
                                "abilities": abil,
                                # Prep hit/expertise flag (EXPERIMENTAL) — present only when this raider
                                # is under their effective-hit cap, so the row can note the gear FIX.
                                "hit": (hit_map or {}).get(nm)})
            players.sort(key=lambda p: -p["maxDiff"])  # most-divergent raider first (most to coach)
            spec_bosses.append({
                "encounterID": enc, "name": bn.get("name"), "metric": metric,
                "benchmark": {"name": player.get("name"), "guild": player.get("guild"),
                              "server": player.get("server"), "region": player.get("region"),
                              "amount": player.get("amount"), "globalRank": player.get("globalRank"),
                              "sameFaction": player.get("sameFaction", True),
                              "metric": metric} if player.get("name") else None,
                # Did the world-best player's CAST table actually fetch? When it didn't (empty abilities),
                # every raider is dropped and players==[], which would otherwise render the "no raider
                # played that role/form" empty-state — a wrong reason (the raiders DID play; the benchmark
                # rotation just couldn't be fetched). The renderer uses this to pick the honest message.
                "benchHasCasts": bool(w_abil),
                "players": players,
                "worstDiff": max((p["maxDiff"] for p in players), default=0.0),
            })
        slot.append({"spec": spec, "role": role, "metric": metric, "bosses": spec_bosses,
                     "worstDiff": max((b["worstDiff"] for b in spec_bosses), default=-1)})

    classes = []
    for cls in sorted(by_class):
        specs = by_class[cls]
        # Within a class, the spec with the biggest rotation gap (across its bosses) floats up.
        specs.sort(key=lambda s: -s.get("worstDiff", 0))
        classes.append({"class": cls, "specs": specs})
    return {"present": True, "factionName": wb.get("factionName"), "region": wb.get("region"),
            "classes": classes}


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
    """Interrupts breakdown, ability-first: per interrupted enemy ability, the total kicks AND a
    per-(spec, class) tally of WHO kicked it. `details[]` on each Interrupts entry carries the per-player
    kick counts; we bucket them by primary spec. Returns {ability: {"total": int, "specs": {(spec,cls): n}}}."""
    abil = {}
    for ab in _inner_entries(report, "intr"):
        if not ab or not ab.get("name"):
            continue
        rec = abil.setdefault(str(ab["name"]), {"total": 0, "specs": {}})
        for d in (ab.get("details") or []):
            if not d:
                continue
            c = int(d.get("total", 0))
            rec["total"] += c
            cls = str(d["type"]) if d.get("type") else "Unknown"
            spec = str(spec_map.get(str(d.get("name")), "")) if d.get("name") else ""
            key = (spec, cls)
            rec["specs"][key] = rec["specs"].get(key, 0) + c
    return abil


def int_compare(o_report, t_report, o_spec, t_spec):
    """Ability-first interrupts: one row per interrupted ability with ours/theirs totals AND the kicking
    specs nested under it, ours vs benchmark side by side ("benchmark kicked it with Fire Mages, you used
    Ele Shaman"). Descriptive — a different spec assignment isn't better/worse, it reveals strategy."""
    o = int_break(o_report, o_spec)
    t = int_break(t_report, t_spec)
    rows = []
    for name in sorted(set(o) | set(t), key=repr):
        orec = o.get(name, {"total": 0, "specs": {}})
        trec = t.get(name, {"total": 0, "specs": {}})
        specs = [{"spec": spec, "class": cls,
                  "ours": int(orec["specs"].get((spec, cls), 0)),
                  "theirs": int(trec["specs"].get((spec, cls), 0))}
                 for (spec, cls) in sorted(set(orec["specs"]) | set(trec["specs"]), key=repr)]
        specs.sort(key=lambda s: (-max(s["ours"], s["theirs"]), s["class"], s["spec"]))
        rows.append({"name": name, "ours": int(orec["total"]), "theirs": int(trec["total"]), "specs": specs})
    rows.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    return {"abilities": rows}


def death_list(report, fight_start, npc_map=None):
    """Deaths: name + spec (from icon) + killing blow + the SOURCE MOB that landed it + when (sec into
    fight). The source mob (`srcMob`) disambiguates a killing blow shared by the boss and an add — e.g.
    'Arcing Smash' is Maulgar's cleave on one boss but a Coilfang Guardian add's on Lurker. Resolved from
    the death's killing-blow event via `_death_source_mob` (no extra API call). None for a boss/self/
    environment death where the boss itself or no enemy actor landed the blow (caller compares vs boss name)."""
    out = []
    if not report.get("deaths"):
        return out
    npc_map = npc_map or {}
    for d in _entries(report, "deaths"):
        if not d or not d.get("name"):
            continue
        kb = str(d["killingBlow"]["name"]) if d.get("killingBlow") and d["killingBlow"].get("name") else "Unknown"
        t = round((int(d["timestamp"]) - int(fight_start)) / 1000)
        out.append({"name": str(d["name"]), "class": str(d.get("type")),
                    "icon": str(d.get("icon")), "killedBy": kb, "tSec": int(t),
                    "srcMob": _death_source_mob(d, npc_map)})
    out.sort(key=lambda x: x["tSec"])
    return out


def death_timing(deaths, fight_info, phase_names=None):
    """When OUR deaths cluster on a boss: the phase (or third of the fight) most deaths land in.
    A '1-level-deeper' read on the death list that pairs the *what* (killing blow, shown below) with
    the *when*. Returns "" unless there are >=3 deaths AND a clear concentration — silence over noise."""
    phase_names = phase_names or {}
    deaths = [d for d in (deaths or []) if d.get("tSec") is not None]
    n = len(deaths)
    if n < 3:
        return ""
    start, end = int(fight_info["start"]), int(fight_info["end"])
    dur_s = max(1, end - start) / 1000.0
    pts = sorted(fight_info.get("phases") or [], key=lambda p: p["startTime"])
    if len(pts) >= 2:
        bounds = []  # (phaseId, startSec, endSec)
        for i, p in enumerate(pts):
            ps = (int(p["startTime"]) - start) / 1000.0
            pe = (int(pts[i + 1]["startTime"]) - start) / 1000.0 if i + 1 < len(pts) else dur_s
            bounds.append((int(p["id"]), ps, pe))
        counts = {}
        for d in deaths:
            t = d["tSec"]
            for j, (pid, ps, pe) in enumerate(bounds):
                if t >= ps and (t < pe or j == len(bounds) - 1):
                    counts[pid] = counts.get(pid, 0) + 1
                    break
        if counts:
            top_id, top_n = max(counts.items(), key=lambda kv: kv[1])
            if len(counts) > 1 and top_n >= max(3, round(n * 0.4)):
                label = phase_names.get(top_id) or "Phase {}".format(top_id)
                return "{} of {} deaths struck in {} — the phase to review.".format(top_n, n, label)
        return ""
    # No phase transitions exposed: split the fight into thirds.
    third = dur_s / 3.0
    counts = [0, 0, 0]
    for d in deaths:
        counts[min(2, int(d["tSec"] // third)) if third > 0 else 0] += 1
    labels = ["the opening third", "the middle third", "the final third"]
    top = max(range(3), key=lambda i: counts[i])
    if counts[top] >= max(3, round(n * 0.45)):
        return "{} of {} deaths struck in {} of the fight.".format(counts[top], n, labels[top])
    return ""


def death_cascades(deaths, window=15, min_cluster=4):
    """Detect a death CASCADE — a burst of deaths inside a short window, i.e. a near-wipe / single
    mechanic failure (vs. scattered attrition). From OUR death timestamps. Two-pointer over the sorted
    times finds the densest `window`-second span. Returns "" unless >= `min_cluster` deaths fall in it."""
    ds = sorted(int(d["tSec"]) for d in (deaths or []) if d.get("tSec") is not None)
    n = len(ds)
    if n < min_cluster:
        return ""
    best_count, best_start, best_end = 0, 0, 0
    j = 0
    for i in range(n):
        if j < i:
            j = i
        while j < n and ds[j] - ds[i] <= window:
            j += 1
        if j - i > best_count:
            best_count, best_start, best_end = j - i, ds[i], ds[j - 1]
    if best_count < min_cluster:
        return ""
    span = max(1, best_end - best_start)
    mm, ss = divmod(int(best_start), 60)
    return ("{} deaths within {}s starting {}:{:02d} — a cascade (one mechanic/moment), not scattered "
            "attrition. Find what went out there.".format(best_count, span, mm, ss))


def opener_gap(o_tl, t_tl, secs=30):
    """Compare the first `secs` of raid DPS, ours vs benchmark, from the binned timeline curves — a
    weak opener means no prepot/precast or a slow pull. Each curve is binned across its OWN fight
    duration, so we average the buckets covering the first `secs` of real time on each side. Returns
    {oursDps, theirsDps, secs} or None when timeline data is absent (graceful)."""
    def first_dps(tl):
        if not tl or not tl.get("dps") or not tl.get("durMs"):
            return None
        dps = tl["dps"]
        n = len(dps)
        if n == 0:
            return None
        bin_ms = tl["durMs"] / n
        k = max(1, min(n, int(round(secs * 1000.0 / bin_ms))))
        return round(sum(dps[:k]) / k)
    o = first_dps(o_tl)
    t = first_dps(t_tl)
    if o is None or t is None:
        return None
    return {"oursDps": o, "theirsDps": t, "secs": secs}


def disp_list(report):
    """Dispels: which ENEMY auras the raid removed (purges off a hostile target), with counts. Counts
    only removals whose TARGET actor is hostile (type Boss/NPC). The WCL Dispels table also lists FRIENDLY
    cleanses — a Mind-Control break off a raider, an ally poison-cure — whose target actor is a player
    class; those are defensive plays, not "enemy auras the raid chose to remove", so including them
    mislabels the view (its header says "enemy auras") and inflates the dispel-priority read with
    cleanse activity. `details[].actors[]` are the dispel TARGETS; filter to the hostile ones."""
    m = {}
    for a in _inner_entries(report, "disp"):
        if not a or not a.get("name"):
            continue
        cnt = 0
        for det in (a.get("details") or []):
            for act in (det.get("actors") or []):
                if act.get("type") in ("Boss", "NPC"):
                    cnt += int(act.get("total", 0))
        if cnt:
            m[str(a["name"])] = int(cnt)
    return m


def disp_compare(o_report, t_report):
    o = disp_list(o_report)
    t = disp_list(t_report)
    names = sorted(set(o) | set(t))
    rows = [{"name": n, "ours": int(o.get(n, 0)), "theirs": int(t.get(n, 0))} for n in names]
    rows.sort(key=lambda r: max(r["ours"], r["theirs"]), reverse=True)
    return rows


# Auto-attacks are never interruptible — a backstop to the CC discount below. A ranged "Shoot" auto-shot
# can be incidentally stopped by a Polymorph, which would otherwise fake-prove it kickable; name-block the
# handful of auto-attack labels so they can never enter the interrupt views regardless of CC noise.
AUTO_ATTACK_NAMES = {"Shoot", "Auto Attack", "Auto Shot", "Melee", "Attack"}


def _real_interrupt_kicks(entry):
    """Count interrupts on this Interrupts-table entry whose INTERRUPTING ability is a real interrupt
    (Counterspell, Kick, Pummel, Shield Bash, Earth Shock, Spell Lock, …) — NOT a hard CC. WCL credits a
    cast as 'interrupted' even when a Polymorph/Banish merely CC'd the caster mid-cast, but that is not
    proof the cast is kickable. `details[].abilities[]` carries the interrupting abilities; we sum only
    those that aren't hard CC (`cc_label` is None). Zero ⇒ the cast was only ever stopped by CC, so it is
    NOT proven interruptible (this is what was fake-proving auto-attacks like 'Shoot' interruptible)."""
    n = 0
    for d in (entry.get("details") or []):
        for ab in (d.get("abilities") or []):
            if cc_label(ab.get("name")) is None:
                n += int(ab.get("total", 0))
    return n


def unkicked_list(report):
    """Interruptible casts that went off un-kicked (raid failed to interrupt). An ability is only
    'interruptible' once the raid has kicked it with a REAL interrupt (not a CC that incidentally
    stopped a cast) — see `_real_interrupt_kicks`. Keep only abilities whose un-interrupted casts
    (missedCasts) have a hostile caster."""
    rows = []
    for a in _inner_entries(report, "intr"):
        if not a:
            continue
        if a.get("name") in AUTO_ATTACK_NAMES:
            continue  # auto-attacks are never interruptible (backstop to the CC discount)
        missed = a.get("missedCasts") or []
        hostile = [m for m in missed if m.get("type") in ("NPC", "Boss")]
        if len(missed) > 0 and len(hostile) == 0:
            continue  # friendly-ability noise
        kicked = _real_interrupt_kicks(a)
        if kicked <= 0:
            continue  # only ever CC-stopped, never truly kicked → not proven interruptible
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


def leaked_casts(report):
    """Per ability: (kicked, leaked) for the tier-wide leaked-interrupts view.

    The WCL public API exposes NO 'is interruptible' flag, and the Interrupts table only ever lists
    abilities the raid interrupted at least once — so a kick is our PROOF the ability is interruptible (we
    never assume). But the table credits a cast as 'interrupted' even when a hard CC (Polymorph, Banish, …)
    merely stopped it mid-cast, which is NOT proof it's kickable — so we count only REAL interrupt kicks
    (`_real_interrupt_kicks`, which discounts CC) and require ≥1 of them. `leaked` counts only HOSTILE
    (NPC/Boss) casts that went off un-interrupted (`missedCasts`); friendly casts (e.g. a raider's own
    Regrowth that took an incidental interrupt) are excluded. Known blind spot: an interruptible ability the
    raid NEVER kicked is absent from the table entirely, so a total interrupt failure is invisible — this
    UNDER-counts, never over-counts. We deliberately do NOT fall back to `spellsCompleted` (no caster proof)."""
    out = {}
    for a in _inner_entries(report, "intr"):
        if not a or not a.get("name"):
            continue
        if a.get("name") in AUTO_ATTACK_NAMES:
            continue  # auto-attacks are never interruptible (a Poly can incidentally stop "Shoot")
        kicked = _real_interrupt_kicks(a)
        if kicked <= 0:
            continue  # only ever CC-stopped, never truly kicked → not proven interruptible
        leaked = sum(1 for m in (a.get("missedCasts") or []) if m.get("type") in ("NPC", "Boss"))
        out[str(a["name"])] = {"kicked": kicked, "leaked": leaked}
    return out


def leaked_interrupts_gap(o_acc, t_acc):
    """Tier-wide leaked-interrupt rows, ours vs benchmark, ranked by our leaks then by improvable delta.
    Only abilities where at least one side LEAKED are returned (a 0/0-leak ability implies no action)."""
    rows = []
    for n in sorted(set(o_acc) | set(t_acc), key=repr):
        o = o_acc.get(n, {"kicked": 0, "leaked": 0})
        t = t_acc.get(n, {"kicked": 0, "leaked": 0})
        if o["leaked"] <= 0 and t["leaked"] <= 0:
            continue
        rows.append({"name": n, "oursKicked": o["kicked"], "oursLeaked": o["leaked"],
                     "theirsKicked": t["kicked"], "theirsLeaked": t["leaked"]})
    rows.sort(key=lambda r: (-r["oursLeaked"], -(r["oursLeaked"] - r["theirsLeaked"]), r["name"]))
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


def phase_compare(o_info, t_info, names=None):
    names = names or {}
    op = phase_list(o_info)
    tp = phase_list(t_info)
    if not op and not tp:
        return []
    o_by_id = {str(p["id"]): p["durMs"] for p in op}
    t_by_id = {str(p["id"]): p["durMs"] for p in tp}
    ids = sorted(set(o_by_id) | set(t_by_id), key=lambda x: int(x))
    return [{"id": int(i), "name": names.get(int(i)), "oursMs": int(o_by_id.get(i, 0)),
             "theirsMs": int(t_by_id.get(i, 0))} for i in ids]


# ---------- CLEAR EFFICIENCY (wall-clock vs in-combat) ----------
def efficiency(directory, enc_ids):
    """Clear efficiency SCOPED TO THE SHARED BOSSES (the BUG fix). Wall-clock = first pull to last kill
    spanning only the shared encounters on this side — so a benchmark that also cleared another zone the
    same night isn't compared on its whole-report clock (which made the old full-report span meaningless
    when the two reports covered different content). In-combat = sum of the shared-boss kill durations;
    downtime = the rest of that window (trash + wipes between the shared bosses). Each side is scoped to
    its OWN shared-boss window, so the comparison stays apples-to-apples. Falls back to all kills only if
    none of the shared encounters are present (shouldn't happen via the normal flow)."""
    enc_set = {str(e) for e in enc_ids}
    fights = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]
    shared = [f for f in fights if str(f["encounterID"]) in enc_set] or fights
    first = min(int(f["startTime"]) for f in shared)
    last = max(int(f["endTime"]) for f in shared)
    combat = ssum([int(f["endTime"]) - int(f["startTime"]) for f in shared])
    span = last - first
    return {"spanMs": span, "combatMs": combat, "downtimeMs": span - combat, "kills": len(shared)}


# ---------- ITEM LEVEL BY ROLE ----------
def accumulate_ilvl(report, ilvl_map):
    """Record name -> item level from any output table (ilvl is static per report, so the
    first sighting wins). dd covers dps, heal covers healers, dt covers tanks."""
    for alias in ("dd", "heal", "dt"):
        for e in _entries(report, alias):
            nm = e.get("name")
            il = e.get("itemLevel")
            if nm and il and nm not in ilvl_map:
                ilvl_map[nm] = float(il)


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


def biggest_gaps(summary, quality, consumables, audit, comp_gaps, tier_spec=None, tier_uptime=None,
                 trash=None, death_causes=None, leaked=None, threat=None, n=7):
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
            add(worst["deficit"] / 800.0, "A spec is underperforming across all bosses",
                "{} {} average {}/s vs {}/s across all bosses — your biggest per-spec DPS gap. Coach rotation/gear."
                .format(worst["spec"], worst["class"], _fmt_k(worst["oursAvg"]), _fmt_k(worst["theirsAvg"])))

    # Biggest buff/debuff uptime deficit tier-wide.
    if tier_uptime:
        worst = next((r for r in tier_uptime if r["deficit"] >= 3), None)
        if worst:
            add(worst["deficit"] / 40.0, "A raid buff/debuff is under-maintained",
                "{} {} uptime averages {}% vs {}% across all bosses. Keeping it up is free throughput."
                .format(worst["name"], worst["kind"], worst["ours"], worst["theirs"]))

    # Trash deaths (lower better). A high-leverage gap that otherwise only lives in the Trash tab —
    # the night-wide "Too many deaths" card pools boss + trash, so this isolates the avoidable-trash slice.
    if trash and trash.get("present"):
        o_td = (trash["glance"]["ours"] or {}).get("deaths", 0)
        t_td = (trash["glance"]["theirs"] or {}).get("deaths", 0)
        if o_td - t_td > 0:
            add((o_td - t_td) / 30.0, "Dying too much on trash",
                "{} trash deaths vs {} for the benchmark. Trash deaths are almost always avoidable — CC, "
                "interrupt, or position around the pull.".format(o_td, t_td))

    # The single most avoidable killing blow tier-wide: the mechanic the benchmark has solved and we
    # haven't (death_causes is pre-sorted improvable-delta-first). Names the specific mechanic the raid
    # keeps dying to, where the count-only "Too many deaths" card just sums them.
    if death_causes:
        worst = next((r for r in death_causes if r["ours"] - r["theirs"] > 0), None)
        if worst:
            where = " on {}".format(worst["boss"]) if worst.get("boss") else ""
            add((worst["ours"] - worst["theirs"]) / 6.0, "A killing blow keeps getting you",
                "You die to {}{} {}× vs {}× for the benchmark — a recurring killing blow they "
                "largely avoid. Interrupt, CC, or position around it."
                .format(worst["cause"], where, worst["ours"], worst["theirs"]))

    # Worst leaked interrupt: an interruptible cast (proven by >=1 kick) you let through more than the
    # benchmark. High-leverage — assigning a kick is a cheap, repeatable fix.
    if leaked:
        worst = max(leaked, key=lambda r: r["oursLeaked"] - r["theirsLeaked"], default=None)
        if worst and (worst["oursLeaked"] - worst["theirsLeaked"]) >= 2:
            add((worst["oursLeaked"] - worst["theirsLeaked"]) / 8.0, "Interruptible casts are leaking",
                "You let {} {} cast{} through un-interrupted vs {} for the benchmark — your worst leak "
                "on a cast you do kick. Assign a kick rotation.".format(
                    worst["oursLeaked"], worst["name"], "s" if worst["oursLeaked"] != 1 else "",
                    worst["theirsLeaked"]))

    # Early aggro: a non-tank held a boss's aggro in the opener (first 30s) more than the benchmark.
    # The cleanest threat signal (opener pulls are unambiguous, vs mechanic-driven mid-fight churn).
    if threat:
        do = (threat.get("oursOpener", 0) or 0) - (threat.get("theirsOpener", 0) or 0)
        if do >= 1:
            add(do / 3.0, "Pulling aggro in the opener",
                "A non-tank held a boss's aggro in the first 30s {}× vs {}× for the benchmark — open "
                "softer, or use Misdirection / Tricks of the Trade.".format(
                    threat.get("oursOpener", 0), threat.get("theirsOpener", 0)))

    cand.sort(key=lambda c: -c["sev"])
    out = []
    for c in cand:
        # Drop "Minor" (low-severity) cards entirely — user directive: only surface gaps worth acting on.
        if c["sev"] < 0.25:
            continue
        c["level"] = "high" if c["sev"] >= 0.5 else "med"
        out.append(c)
        if len(out) >= n:
            break
    return out


def strengths(summary, quality, consumables, audit, comp_gaps, tier_spec=None, tier_uptime=None,
              trash=None, n=5):
    """The honest positive half of the Biggest Gaps engine: the dimensions where the raid MATCHES or
    BEATS the benchmark, ranked by margin. Same inputs, sign flipped — facts where you lead, not
    cheerleading. Only dimensions where we're actually ahead make the list; trail everywhere and it
    stays empty (so it never manufactures praise)."""
    co, ct = consumables["ours"], consumables["theirs"]
    ao, at = audit["ours"], audit["theirs"]
    bosses = max(summary["bossCount"], 1)
    cand = []

    def add(margin, title, text):
        if margin > 0:
            cand.append({"m": margin, "title": title, "text": text})

    # Raid parse (higher better).
    dp = summary["oursAvgParse"] - summary["theirsAvgParse"]
    add(dp / 50.0, "Raid parses beat the benchmark",
        "Raid parses average {} vs {} — a {}-point lead. A strength to protect."
        .format(summary["oursAvgParse"], summary["theirsAvgParse"], round(dp, 1)))

    # Kill time (lower better) — we're faster.
    od, td = summary["oursDurationMs"], summary["theirsDurationMs"]
    if od > 0 and od < td:
        add((td / od - 1), "Kills are faster",
            "Total kill time {} vs {} — {}% faster than the benchmark."
            .format(_fmt_dur(od), _fmt_dur(td), round((1 - od / td) * 100)))

    # Raid DPS (higher better).
    od2, td2 = quality["oursRaidDps"], quality["theirsRaidDps"]
    if td2 > 0 and od2 > td2:
        add((od2 - td2) / td2, "Raid DPS is higher",
            "Raid DPS averages {} vs {} — the engine behind the faster kills."
            .format(_fmt_k(od2), _fmt_k(td2)))

    # Deaths (lower better).
    ddh = summary["theirsDeaths"] - summary["oursDeaths"]
    if ddh > 0:
        scope = "across the full clear (trash + all pulls)" if summary.get("nightWideDeaths") \
            else "across {} bosses".format(bosses)
        add(ddh / (bosses * 2.0), "Staying alive",
            "{} deaths vs {} {} — fewer deaths means more uptime and less wipe risk."
            .format(summary["oursDeaths"], summary["theirsDeaths"], scope))

    # Healer overheal (lower better).
    oh = quality["theirsOverheal"] - quality["oursOverheal"]
    if oh > 0:
        add(oh / 40.0, "Tight healing",
            "Healers overheal {}% vs {}% — less throughput wasted than the benchmark."
            .format(quality["oursOverheal"], quality["theirsOverheal"]))

    # DPS activity (higher better).
    ac = quality["oursActivity"] - quality["theirsActivity"]
    if ac > 0:
        add(ac / 30.0, "High DPS activity",
            "DPS spend {}% of the fight active vs {}% — few wasted GCDs."
            .format(quality["oursActivity"], quality["theirsActivity"]))

    # Avoidable damage taken / sec (lower better).
    dtk_o, dtk_t = quality["oursDtps"], quality["theirsDtps"]
    if dtk_o > 0 and dtk_o < dtk_t:
        add((dtk_t / dtk_o - 1), "Avoiding damage",
            "Raid takes {}/s (ex-tanks) vs {}/s — cleaner on avoidable damage."
            .format(_fmt_k(dtk_o), _fmt_k(dtk_t)))

    # Flask coverage.
    o_fl = co["flask"] / max(co["rosterSize"], 1)
    t_fl = ct["flask"] / max(ct["rosterSize"], 1)
    if o_fl - t_fl > 0:
        add(o_fl - t_fl, "Well flasked",
            "~{}/{} raiders flasked vs ~{}/{} for the benchmark."
            .format(co["flask"], co["rosterSize"], ct["flask"], ct["rosterSize"]))

    # Food coverage.
    o_fd = co["food"] / max(co["rosterSize"], 1)
    t_fd = ct["food"] / max(ct["rosterSize"], 1)
    if o_fd - t_fd > 0:
        add(o_fd - t_fd, "Well fed",
            "~{}/{} raiders ate food vs ~{}/{} for the benchmark."
            .format(co["food"], co["rosterSize"], ct["food"], ct["rosterSize"]))

    # Enchants (fewer missing better).
    o_me = ao["totalMissingEnchants"] / max(ao["playerCount"], 1)
    t_me = at["totalMissingEnchants"] / max(at["playerCount"], 1)
    if t_me - o_me > 0:
        add((t_me - o_me) / 3.0, "Gear is enchanted",
            "{} missing enchants across the raid vs {} for the benchmark."
            .format(ao["totalMissingEnchants"], at["totalMissingEnchants"]))

    # Wipes (fewer better).
    if summary.get("hasAttempts"):
        ow, tw = summary["oursWipes"], summary["theirsWipes"]
        if tw > ow:
            add((tw - ow) / (bosses * 3.0), "Clean progression",
                "{} wipes across the shared bosses vs {} for the benchmark."
                .format(ow, tw))

    # A spec that out-performs the benchmark tier-wide (deficit < 0 = we lead).
    if tier_spec:
        best = min((r for r in tier_spec if r["both"]), key=lambda r: r["deficit"], default=None)
        if best and best["deficit"] < 0:
            add(-best["deficit"] / 800.0, "A spec out-DPSes the benchmark",
                "{} {} average {}/s vs {}/s across all bosses — ahead of the benchmark's same spec."
                .format(best["spec"], best["class"], _fmt_k(best["oursAvg"]), _fmt_k(best["theirsAvg"])))

    # A raid buff/debuff kept up better than the benchmark. Require theirs > 0 so this is a genuine
    # "we maintain it better" comparison — a benchmark 0% means they don't run that provider, which the
    # "Buffs the benchmark lacks" card already covers (and "84% vs 0%" reads like a typo, not a strength).
    if tier_uptime:
        best = min((r for r in tier_uptime if r["theirs"] > 0), key=lambda r: r["deficit"], default=None)
        if best and best["deficit"] <= -3:
            add(-best["deficit"] / 40.0, "A raid buff/debuff is well-maintained",
                "{} {} uptime averages {}% vs {}% across all bosses — kept up better than the benchmark."
                .format(best["name"], best["kind"], best["ours"], best["theirs"]))

    # Raid buff/debuff providers WE bring that the benchmark doesn't.
    extra = [g["buff"] for g in comp_gaps if g["ours"] and not g["theirs"]]
    if extra:
        eg = extra[0] + (", " + extra[1] if len(extra) > 1 else "")
        add(len(extra) / 5.0, "Buffs the benchmark lacks",
            "You bring {} raid-wide buff/debuff{} the benchmark doesn't (e.g. {})."
            .format(len(extra), "s" if len(extra) > 1 else "", eg))

    # Trash deaths (fewer better).
    if trash and trash.get("present"):
        o_td = (trash["glance"]["ours"] or {}).get("deaths", 0)
        t_td = (trash["glance"]["theirs"] or {}).get("deaths", 0)
        if t_td - o_td > 0:
            add((t_td - o_td) / 30.0, "Clean on trash",
                "{} trash deaths vs {} for the benchmark.".format(o_td, t_td))

    cand.sort(key=lambda c: -c["m"])
    return [{"title": c["title"], "text": c["text"]} for c in cand[:n]]


def dps_diagnosis(quality):
    """Decompose the raid-DPS gap into an activity (uptime/movement) component vs a throughput
    (gear/rotation/buffs) component, from the Raid DPS + DPS-activity numbers already shown above.
    Tells a leader *what kind* of fix the gap calls for. Approximate by design — DPS-activity is the
    DPS core's while Raid DPS is whole-raid — so it's framed as an estimate, not a precise figure.
    Returns "" unless we trail on raid DPS with usable activity numbers."""
    o_dps, t_dps = quality.get("oursRaidDps"), quality.get("theirsRaidDps")
    o_act, t_act = quality.get("oursActivity"), quality.get("theirsActivity")
    if not (o_dps and t_dps and o_dps < t_dps and o_act and t_act):
        return ""
    gap = t_dps - o_dps
    # Matching their activity scales our DPS by t_act/o_act (same damage per active second).
    closed = max(0.0, min(o_dps * (t_act / o_act) - o_dps, gap))
    share = closed / gap if gap > 0 else 0
    act_behind = t_act - o_act
    if act_behind >= 1 and share >= 0.5:
        return ("Most of your ~{}/s raid-DPS gap looks like an activity gap — DPS are active {}% of the "
                "fight vs {}%. Matching that uptime alone would recover roughly {}/s; drill movement and "
                "positioning before chasing gear.".format(_fmt_k(gap), o_act, t_act, _fmt_k(round(closed))))
    if act_behind >= 1 and share > 0.15:
        return ("Your ~{}/s raid-DPS gap is part uptime, part throughput — closing the activity gap "
                "({}% vs {}%) recovers about {}/s; the rest is damage-while-active: gear, rotations, and "
                "raid buffs.".format(_fmt_k(gap), o_act, t_act, _fmt_k(round(closed))))
    return ("Your ~{}/s raid-DPS gap is mostly throughput, not uptime — activity is close ({}% vs {}%), so "
            "the deficit is damage-while-active: gear, rotations, and raid buffs."
            .format(_fmt_k(gap), o_act, t_act))


# ---------- TRASH ANALYSIS (the Trash tab) ----------
# WCL splits trash into discrete pull segments; we layer benchmark-compared views on top, all honoring
# the product's hybrid rule: compare only what aligns across guilds (clear time, deaths, CC counts,
# mob-type kill priority, exact-roster pack matches — mob TYPES align even when pull boundaries don't).
# The raw single-raid per-pull drill-down (Pack-by-Pack) was removed as a near data-dump. Kill order & CC
# are DESCRIPTIVE vs the benchmark, never moralized — if the benchmark CCs more or focuses a target later,
# that's the bar, not a fault.
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


def _death_source_mob(death, npc_map):
    """Resolve which MOB landed the killing blow on a player. Prefer the killing-blow EVENT's source
    (the actual fatal hit — the death entry carries its death-window `events`, each with a `sourceID`),
    falling back to the top hostile damage source on the entry. Returns the mob NAME, or None for an
    environment / fall / self death where no enemy actor is credited."""
    kb = death.get("killingBlow") or {}
    kb_guid = kb.get("guid")
    evs = [e for e in (death.get("events") or [])
           if e.get("type") == "damage" and (e.get("ability") or {}).get("guid") == kb_guid]
    if evs:
        src = npc_map.get((max(evs, key=lambda e: e.get("timestamp", 0))).get("sourceID"))
        if src and src != "Environment":
            return src
    for s in (((death.get("damage") or {}).get("sources")) or []):
        if s.get("type") in ("NPC", "Boss") and s.get("name") and s["name"] != "Environment":
            return s["name"]  # "Environment" (ground effects/fall) is not a nameable mob — leave it bare
    return None


def trash_death_causes(o, t, n=None, o_npc=None, t_npc=None):
    """Player trash deaths aggregated by killing blow, ranked by the biggest IMPROVABLE delta
    (our deaths − theirs), ours vs benchmark. Each NAMED killing blow now carries the SOURCE MOB in
    parens ("Fragmentation Bomb (Tempest-Smith)") — the mob is the actionable half (CC/kite/position
    that mob), resolved from the death's killing-blow event. "Melee" is kept as one aggregate row here
    (mob varies) and broken out by mob in `trash_melee_by_mob`. Ability+mob align across guilds, so the
    comparison stays clean; ranking by delta floats the blows the benchmark has solved and we haven't.

    NOT truncated by default (n=None): trash mob/ability cardinality is small, and the sort pushes
    theirs-only rows (a death the benchmark took and we avoided) to the bottom — an earlier `rows[:15]`
    cap silently dropped exactly those, so the table's `theirs` column under-summed vs the Trash-Deaths
    glance card sitting directly above it (a visible contradiction) and hid the benchmark's worst named
    trash mechanic. Both columns now always reconcile with the glance totals."""
    o_npc = o_npc if o_npc is not None else o["npc"]
    t_npc = t_npc if t_npc is not None else t["npc"]

    def agg(side, npc):
        m = {}
        for d in side["friendly"]:
            cause = (d.get("killingBlow") or {}).get("name") or "Unknown"
            if cause == "Melee":
                label = "Melee"  # mob varies — see the melee-by-mob sub-breakdown
            else:
                mob = _death_source_mob(d, npc)
                label = "{} ({})".format(cause, mob) if mob else cause
            m[label] = m.get(label, 0) + 1
        return m
    oa, ta = agg(o, o_npc), agg(t, t_npc)
    rows = [{"cause": c, "ours": oa.get(c, 0), "theirs": ta.get(c, 0)} for c in sorted(set(oa) | set(ta), key=repr)]
    # Biggest improvable delta first (a death the benchmark avoids); ties → raw ours, then theirs.
    rows.sort(key=lambda r: (-(r["ours"] - r["theirs"]), -r["ours"], -r["theirs"]))
    return rows if n is None else rows[:n]


def trash_melee_by_mob(o, t):
    """"Melee" killing blows broken out by the MOB whose melee did the killing, ours vs benchmark,
    biggest improvable delta first. A bare "Melee" death is opaque; naming the mob points straight at a
    CC, kite, or tank-positioning fix. Mob names align across guilds, so the comparison is clean."""
    def agg(side, npc):
        m = {}
        for d in side["friendly"]:
            if ((d.get("killingBlow") or {}).get("name")) != "Melee":
                continue
            mob = _death_source_mob(d, npc) or "Unknown"
            m[mob] = m.get(mob, 0) + 1
        return m
    oa, ta = agg(o, o["npc"]), agg(t, t["npc"])
    rows = [{"mob": mb, "ours": oa.get(mb, 0), "theirs": ta.get(mb, 0)} for mb in sorted(set(oa) | set(ta), key=repr)]
    rows.sort(key=lambda r: (-(r["ours"] - r["theirs"]), -r["ours"], -r["theirs"]))
    return rows


def trash_chain_pull(o, t, big=10):
    """Pull-size / chain-pull comparison: how many mobs each raid pulls at once, ours vs benchmark.
    WCL exposes no 'pack' object — a trash segment IS one pull — so we can't directly count how many
    packs were merged, and a single-pack baseline per zone isn't exposed (a 16-mob pull could be two
    big packs or four small ones), so we deliberately do NOT claim "they merged N packs." What IS clean:
    a segment with far more mobs than typical is a chain-pull. Reports avg + max mobs per pull and the
    count of LARGE pulls (>= `big` mobs), plus each side's single biggest pull (segment + roster) as a
    concrete example. Descriptive — aggressive chain-pulling is a throughput lever and a wipe risk both;
    the benchmark sets the bar."""
    def stats(side):
        sizes, biggest = [], None
        for f in side["fights"]:
            ncs = f.get("enemyNPCs") or []
            total = sum(int(x.get("instanceCount") or 1) for x in ncs)
            if total <= 0:
                continue
            sizes.append(total)
            if biggest is None or total > biggest["mobs"]:
                roster = sorted(({"name": side["npc"].get(int(x["id"]), "Unknown"),
                                  "count": int(x.get("instanceCount") or 1)}
                                 for x in ncs if side["npc"].get(int(x["id"])) not in (None, "Environment")),
                                key=lambda r: -r["count"])
                biggest = {"name": f.get("name"), "mobs": total, "roster": roster}
        if not sizes:
            return None
        return {"avg": round(sum(sizes) / len(sizes), 1), "max": max(sizes),
                "large": sum(1 for s in sizes if s >= big), "pulls": len(sizes), "biggest": biggest}
    return {"ours": stats(o), "theirs": stats(t), "bigThreshold": big}


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
            for (mob, lab) in sorted(set(oa) | set(ta), key=repr)]
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
    for sig in sorted(set(og) & set(tg), key=repr):
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
    for mob in sorted(set(oa) | set(ta), key=repr):
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
    for key in sorted(set(ot) & set(tt), key=repr):
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


def boss_kill_zones(directory):
    """Set of gameZone ids the report's BOSS KILLS happened in, from fights.json. A real raid zone is one
    we actually downed a boss in; outdoor trash that WCL tags to a neighbouring zone (e.g. Zangarmarsh
    trash outside SSC mislabelled 'Isle of Quel'Danas') has no boss kill there. Graceful empty set on
    older data folders whose kills query predates the gameZone field (→ the boss-zone filter is skipped)."""
    try:
        fights = read_json(os.path.join(directory, "fights.json"))["reportData"]["report"]["fights"]
    except (OSError, KeyError, ValueError):
        return set()
    return {(f.get("gameZone") or {}).get("id") for f in fights
            if (f.get("gameZone") or {}).get("id") is not None}


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
    # Drop zones the raid never actually fought a BOSS in — WCL tags some outdoor trash (e.g. the
    # Zangarmarsh pulls just outside the SSC entrance) to a neighbouring zone like "Isle of Quel'Danas",
    # which then passes the shared-trash intersection and shows up as a zone the raid "cleared" though it
    # never entered. Keep only trash zones that are also a boss-kill zone on at least one side. Graceful:
    # if neither side carries boss-kill gameZone data (older folders), the union is empty → skip the filter.
    boss_zones = boss_kill_zones(ours_dir) | boss_kill_zones(theirs_dir)
    if boss_zones:
        shared_zones = {z for z in shared_zones if z in boss_zones}
    zone_names = _zone_names(o, shared_zones) or _zone_names(t, shared_zones)
    if shared_zones:
        o, t = _filter_to_zones(o, shared_zones), _filter_to_zones(t, shared_zones)
    if not o["fights"] and not t["fights"]:
        return {"present": False}

    o_pulls, t_pulls = _trash_pull_records(o), _trash_pull_records(t)
    return {
        "present": True,
        "zones": zone_names,
        "glance": {"ours": _trash_glance(o), "theirs": _trash_glance(t)},
        "chainPull": trash_chain_pull(o, t),
        "deathCauses": trash_death_causes(o, t, o_npc=o["npc"], t_npc=t["npc"]),
        "meleeByMob": trash_melee_by_mob(o, t),
        # Kill order — two lenses: exact-roster 1:1 packs (primary), and broad pairwise (sub-tab).
        "identicalPacks": trash_identical_packs(o_pulls, t_pulls),
        "killPriority": trash_kill_priority(o, t),
        "pairwisePriority": trash_pairwise_priority(o_pulls, t_pulls),
        # CC is the per-mob breakdown only (the by-type summary table was cut as redundant).
        "ccByMob": trash_cc_by_mob(o, t),
        # Trash deaths decomposed by pull SIZE (EXPERIMENTAL) — death-rate per pull, the honest
        # one-level-deeper of the flat trash-deaths count (and aligned across guilds per-pull-of-size-N).
        "deathsByPullSize": trash_deaths_by_pull_size(o, t),
    }


# ---------- NEW EXPERIMENTAL DECOMPOSITIONS (one level deeper than an existing surfaced number) ----------
# Each of these takes a flat aggregate the report already shows and decomposes it by the dimension that
# names the lever (who=spec / what=mechanic / when=on-the-pull / by pull-size). All run on data already
# fetched — no extra API calls. They ship behind an "Experimental" chip.

# --- Overview: the Avg Raid Parse mean, decomposed into its distribution + the specs at the floor ---
# --- Prep: the throughput-potion COUNT, decomposed into WHEN it landed (opener prepot vs reactive) ---
PREPOT_WINDOW_MS = 3000  # a potion buff band starting within 3s of (or before) the pull = an opener prepot


def prepot_timing(directory, idx, enc_ids):
    """Did the raid's throughput (combat) potion land ON THE PULL — the free TBC opener prepot — or only
    reactively mid-fight? One level deeper than the potion-USES count: its TIMING. From the aggregate Buffs
    `bands` (earliest potion-buff band start vs the fight start). RAID-AGGREGATE (bands merge across
    players), so it's an honest raid-level "opener potion on the pull: yes/no" per boss, NOT a per-player
    prepotter count — labelled as such, same precedent as the aggregate Drums uptime. EXPERIMENTAL."""
    fm = fight_map(directory)
    bosses = []
    for enc in enc_ids:
        rep = load_boss(directory, str(enc))
        fi = fm.get(str(enc))
        if not rep or not fi:
            continue
        start = int(fi["start"])
        earliest = None
        for a in _auras(rep, "buffs"):
            # Throughput potions only — a tank's defensive Ironshield on the pull is not a DPS prepot.
            if a.get("guid") not in THROUGHPUT_POTION_IDS:
                continue
            for b in (a.get("bands") or []):
                st = int(b["startTime"])
                if earliest is None or st < earliest:
                    earliest = st
        nm = (idx.get(enc) or {}).get("name")
        if earliest is None:
            bosses.append({"encounterID": int(enc), "name": nm, "used": False, "prepot": False, "sec": None})
        else:
            bosses.append({"encounterID": int(enc), "name": nm, "used": True,
                           "prepot": (earliest - start) <= PREPOT_WINDOW_MS,
                           "sec": round((earliest - start) / 1000, 1)})
    used = [b for b in bosses if b["used"]]
    return {"bosses": bosses, "prepotBosses": sum(1 for b in bosses if b["prepot"]),
            "usedBosses": len(used), "totalBosses": len(bosses)}


# --- Execution: the raid Overheal% number, decomposed by HEALER SPEC ---
# --- Trash: the flat trash-deaths count, decomposed by PULL SIZE (death-rate per pull) ---
PULL_SIZE_BUCKETS = [(1, 3, "1–3"), (4, 7, "4–7"), (8, 12, "8–12"), (13, 9999, "13+")]


def trash_deaths_by_pull_size(o, t):
    """Trash deaths decomposed by PULL SIZE: death-rate per pull, bucketed by mob count, ours vs benchmark.
    One level deeper than the flat "Trash deaths: X vs Y" glance — it names WHETHER the deaths come from big
    chain-pulls (and whether the benchmark survives the same-size pulls). This is the rare trash metric that
    is BOTH aligned across guilds (pull boundaries don't align, but death-rate-per-pull-of-size-N does) and a
    clean better/worse gap. Counts ride along beside the rates (small samples — be honest). EXPERIMENTAL."""
    def agg(side):
        deaths_by_fight = {}
        for d in side["friendly"]:
            deaths_by_fight[d.get("fight")] = deaths_by_fight.get(d.get("fight"), 0) + 1
        buckets = {lab: {"pulls": 0, "deaths": 0} for _, _, lab in PULL_SIZE_BUCKETS}
        for f in side["fights"]:
            size = sum(int(x.get("instanceCount") or 1) for x in (f.get("enemyNPCs") or []))
            if size <= 0:
                continue
            lab = next((l for lo, hi, l in PULL_SIZE_BUCKETS if lo <= size <= hi), None)
            if lab is None:
                continue
            buckets[lab]["pulls"] += 1
            buckets[lab]["deaths"] += deaths_by_fight.get(int(f["id"]), 0)
        return buckets
    oa, ta = agg(o), agg(t)
    rows = []
    for _, _, lab in PULL_SIZE_BUCKETS:
        ob, tb = oa[lab], ta[lab]
        if ob["pulls"] == 0 and tb["pulls"] == 0:
            continue
        rows.append({"size": lab,
                     "oursPulls": ob["pulls"], "oursDeaths": ob["deaths"],
                     "oursRate": round(ob["deaths"] / ob["pulls"], 2) if ob["pulls"] else None,
                     "theirsPulls": tb["pulls"], "theirsDeaths": tb["deaths"],
                     "theirsRate": round(tb["deaths"] / tb["pulls"], 2) if tb["pulls"] else None})
    return rows


# --- Wipes tab: comprehensive per-boss wipe progression (attempts.json + wipe-deaths.json) ---
def _load_attempt_fights(directory):
    path = os.path.join(directory, "attempts.json")
    if not os.path.isfile(path):
        return []
    try:
        return read_json(path)["reportData"]["report"]["fights"]
    except (OSError, KeyError, ValueError):
        return []


def _wipe_trend(seq, downed):
    """A one-line read of the wipe %-remaining sequence (lower = closer to a kill): converging, plateaued,
    or regressing. None when there are too few wipes (<3) to call a trend honestly. When `downed` is True
    the boss was eventually KILLED, so the read is retrospective (past tense, no "keep pushing"/"reset"
    coaching — that would be stale advice on a dead boss)."""
    vals = [(i, v) for i, v in enumerate(seq) if v is not None]
    if len(vals) < 3:
        return None
    n = len(seq)
    best_i, best_v = min(vals, key=lambda iv: iv[1])
    converging = best_i >= n - max(1, n // 3)
    early_best = min(v for i, v in vals if i < max(1, n // 2))
    late_best = min(v for i, v in vals if i >= n // 2)
    regressing = late_best > early_best + 5
    if downed:
        if converging:
            return "Converged — the closest pulls were the most recent, then the kill landed."
        if regressing:
            return "Killed despite drift — pulls got further from the kill mid-progression before it came together."
        return "Killed off a plateau — attempts clustered at one depth, then the kill came."
    if converging:
        return "Converging — the closest attempt was among the most recent pulls; keep pushing."
    if regressing:
        return ("Regressing — pulls got further from the kill after the early attempts "
                "(fatigue/tilt; a short reset may help).")
    return ("Plateaued — attempts cluster at the same depth without getting closer; change something "
            "(assignments, cooldown timing, positioning).")


# Auto-attack names — "sustained" damage, as opposed to a discrete avoidable mechanic.
_AUTO_DMG_NAMES = {"Melee", "Auto Attack", "Auto Shot", "Shoot", "Attack"}

# Friendly / self-sacrifice abilities WCL can attribute as a death's "killing blow" that are NOT a hostile
# wipe cause (a Paladin's Divine Intervention sacrifices the caster). Excluded from the killing-blow /
# first-death tallies and the mechanic/sustained split so they don't pose as a hostile mechanic that ends
# attempts. (A self-sacrifice has damage.total 0 / no abilities, so it would otherwise fall to "sustained".)
_FRIENDLY_KB_NAMES = {"Divine Intervention"}


def _classify_wipe_death(d):
    """Disambiguate WHY a death happened, from the death-window damage mix (the "last hits"): the either/or
    a raid leader actually argues about — a **mechanics/positioning** failure vs **sustained damage**
    (healing/gear/tuning). Heuristic, honest about its limits: it reads the damage composition, not intent,
    and can't see a missed defensive cooldown. Returns (bucket, label):
      • "mechanic"  — a discrete NAMED, non-melee ability dominates the death window (an avoidable hit you
                      should have dodged/LoS'd/soaked correctly) → positioning/timing fix. Labelled by the
                      killing mechanic. (Healers can't out-heal a one-shot — this isn't a healing miss.)
      • "sustained" — melee/attrition dominates with no single mechanic → a healing-assignment, defensive,
                      gear, or tuning question, NOT a "stand somewhere else" drill."""
    dmg = d.get("damage") or {}
    abils = dmg.get("abilities") or []
    total = sum(float(a.get("total", 0)) for a in abils) or float(dmg.get("total", 0)) or 1.0
    melee = sum(float(a.get("total", 0)) for a in abils if a.get("name") in _AUTO_DMG_NAMES)
    named = sorted(((a.get("name"), float(a.get("total", 0))) for a in abils
                    if a.get("name") and a.get("name") not in _AUTO_DMG_NAMES), key=lambda x: -x[1])
    if melee / total >= 0.5 or not named:
        return "sustained", "Sustained / melee damage"
    kb = (d.get("killingBlow") or {}).get("name")
    label = kb if (kb and kb not in _AUTO_DMG_NAMES) else named[0][0]
    return "mechanic", label


def wipe_analysis(directory, enc_names, phase_names):
    """Comprehensive per-boss wipe progression — EXPERIMENTAL, first-party by nature (a benchmark on farm
    rarely wipes). From attempts.json (every pull) + wipe-deaths.json (the friendly Deaths table on the
    wipe pulls, when fetched). For each shared boss the raid WIPED on: attempts/wipes/downed, best depth
    (% remaining + the phase), time spent wiping (the progression TAX the kill-time number hides), the WALL
    (the phase most wipes end in + the typical %-remaining there), the progression TREND (are pulls
    converging on a kill?), and — from the wipe deaths — WHAT ENDS the attempts (the most common FIRST death
    + the killing blows on wipes). Scoped to `enc_names` (shared bosses, id→name); `phase_names` is
    id→{phaseId:name}. Graceful {present:False} without attempts.json."""
    fights = _load_attempt_fights(directory)
    if not fights:
        return {"present": False}
    wd_path = os.path.join(directory, "wipe-deaths.json")
    wd = read_json(wd_path) if os.path.isfile(wd_path) else None
    deaths_by_fight = {}
    if wd:
        for d in (wd.get("deaths") or []):
            deaths_by_fight.setdefault(d.get("fight"), []).append(d)

    by_enc = {}
    for f in fights:
        enc = str(f.get("encounterID"))
        if enc in enc_names:  # shared bosses only — names + wipe-death data are scoped to them
            by_enc.setdefault(enc, []).append(f)

    def pname(enc, pid):
        # Only return a label for a REAL named phase. The synthetic "Phase N" fallback carries no signal
        # (lastPhase is 0 on short/non-phased fights — wcl-api.md) yet renders as a drillable "the phase to
        # drill", so return None and let the renderer omit the phase clause.
        if pid is None:
            return None
        return (phase_names.get(enc) or {}).get(pid)

    def depth_reliable(enc, f):
        """Is this wipe's fightPercentage a real boss-HP% depth? NO when it reports sub-1% on a boss whose
        lastPhase has no NAMED phase — that's the phase-reset artifact (WCL emits ~0% HP during a phase
        transition, e.g. Al'ar's P1→P2), a false near-kill rather than a genuine doorstep wipe. (wcl-api.md:
        only trust lastPhase / sub-1% depth where named phases exist.)"""
        fp = f.get("fightPercentage")
        if fp is None:
            return False
        if float(fp) < 1 and not (phase_names.get(enc) or {}).get(f.get("lastPhase")):
            return False
        return True

    def dsec(f):
        return max(0, int(f.get("endTime", 0)) - int(f.get("startTime", 0))) / 1000.0

    bosses = []
    for enc, fl in by_enc.items():
        fl = sorted(fl, key=lambda x: x.get("startTime", 0))
        wipes = [f for f in fl if not f.get("kill")]
        if not wipes:
            continue  # only bosses the raid actually wiped on
        kills = [f for f in fl if f.get("kill")]
        # Only wipes with a TRUSTWORTHY depth feed the near-kill numbers — a phase-reset boss reporting ~0%
        # is not a real near-kill (see depth_reliable), so it must not become the "closest attempt".
        depth = [f for f in wipes if depth_reliable(enc, f)]
        best = min(depth, key=lambda f: float(f["fightPercentage"])) if depth else None
        # THE WALL — which phase do wipes end in most, and the typical %-remaining there.
        phase_ct, phase_pcts = {}, {}
        for f in wipes:
            ph = f.get("lastPhase")
            phase_ct[ph] = phase_ct.get(ph, 0) + 1
            if depth_reliable(enc, f):
                phase_pcts.setdefault(ph, []).append(float(f["fightPercentage"]))
        wall = None
        if phase_ct:
            wp = max(phase_ct, key=phase_ct.get)
            pcts = sorted(phase_pcts.get(wp) or [])
            wall = {"phase": pname(enc, wp), "wipes": phase_ct[wp], "ofTotal": len(wipes),
                    "medPct": round(pcts[len(pcts) // 2], 1) if pcts else None}
        # Trend sequence: only trustworthy depths (a phase-reset ~0% would otherwise read as a near-kill
        # spike in the progression bars).
        seq = [round(float(f["fightPercentage"]), 1) if depth_reliable(enc, f) else None for f in wipes]
        # WHAT ENDS ATTEMPTS — first death + killing blows on the wipe pulls (when wipe deaths present).
        first_causes, blow_causes, tracked = {}, {}, 0
        cause_mech, cause_sust, mech_names = 0, 0, {}  # death-cause disambiguation: mechanics vs sustained
        for f in wipes:
            ds = sorted(deaths_by_fight.get(f.get("id"), []), key=lambda d: d.get("timestamp", 0))
            # Drop friendly/self-sacrifice "killing blows" (e.g. Divine Intervention) — not a hostile cause.
            ds = [d for d in ds if (d.get("killingBlow") or {}).get("name") not in _FRIENDLY_KB_NAMES]
            if not ds:
                continue
            tracked += 1
            fc = (ds[0].get("killingBlow") or {}).get("name") or "Unknown"
            first_causes[fc] = first_causes.get(fc, 0) + 1
            for d in ds:
                bc = (d.get("killingBlow") or {}).get("name") or "Unknown"
                blow_causes[bc] = blow_causes.get(bc, 0) + 1
                bucket, label = _classify_wipe_death(d)
                if bucket == "mechanic":
                    cause_mech += 1
                    mech_names[label] = mech_names.get(label, 0) + 1
                else:
                    cause_sust += 1

        def rank(m):
            return [{"cause": c, "count": n} for c, n in sorted(m.items(), key=lambda kv: -kv[1])]

        bosses.append({
            "encounterID": int(enc), "name": enc_names.get(enc, "Encounter {}".format(enc)),
            "attempts": len(fl), "wipes": len(wipes), "downed": bool(kills),
            "wipeTimeSec": round(sum(dsec(f) for f in wipes)),
            "killTimeSec": round(sum(dsec(f) for f in kills)),
            "bestPct": round(float(best["fightPercentage"]), 1) if best else None,
            "bestPhase": pname(enc, best.get("lastPhase")) if best else None,
            "wall": wall, "trendSeq": seq, "trend": _wipe_trend(seq, bool(kills)),
            "firstDeaths": rank(first_causes), "killingBlows": rank(blow_causes)[:8],
            "deathsTracked": tracked,
            # Death-cause disambiguation: avoidable mechanic (positioning) vs sustained (healing/gear/tuning).
            "causeMechanic": cause_mech, "causeSustained": cause_sust,
            "topMechanics": rank(mech_names)[:4],
        })
    # Active walls (not yet downed) first, then the bosses that ate the most wipe-time.
    bosses.sort(key=lambda b: (b["downed"], -b["wipeTimeSec"]))
    biggest = max(bosses, key=lambda b: b["wipeTimeSec"], default=None)
    return {"present": True, "hasDeaths": wd is not None,
            "bosses": bosses,
            "totalWipes": sum(b["wipes"] for b in bosses),
            "totalWipeTimeSec": sum(b["wipeTimeSec"] for b in bosses),
            "biggestSink": biggest["name"] if biggest else None}


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

    # Named phases (report.phases). Same boss ⇒ same journal phase names regardless of guild, so ours
    # is authoritative; fall back to theirs per-encounter if only one side carries them. Empty/graceful.
    ours_phase_names = phase_name_map(ours_dir)
    theirs_phase_names = phase_name_map(theirs_dir)
    # Report-wide NPC names (for naming adds + excluding the boss by name in the Add Handling view).
    ours_npc = npc_name_map(ours_dir)
    theirs_npc = npc_name_map(theirs_dir)

    # Wipe/attempt counts + WIPE DEPTH per shared boss (graceful if attempts.json predates this feature).
    ours_att = attempt_map(ours_dir)
    theirs_att = attempt_map(theirs_dir)
    for b in bosses:
        enc = str(b["encounterID"])
        oa, ta = ours_att.get(enc, {}), theirs_att.get(enc, {})
        b["oursWipes"], b["theirsWipes"] = oa.get("wipes", 0), ta.get("wipes", 0)
        b["oursAttempts"], b["theirsAttempts"] = oa.get("attempts", 0), ta.get("attempts", 0)
        b["hasAttempts"] = bool(oa) or bool(ta)
        # Wipe depth: how close the best attempt got (boss HP% remaining) + that attempt's phase name.
        b["oursBestWipePct"], b["theirsBestWipePct"] = oa.get("bestWipePct"), ta.get("bestWipePct")
        _bp = oa.get("bestWipePhase")
        b["oursBestWipePhase"] = (ours_phase_names.get(enc) or {}).get(_bp) if _bp else None
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
             "class": c["class"], "spec": c["spec"], "scope": c.get("scope", "raid"),
             # provider COUNT (one level deeper than the binary ✓/✗) — drives the count delta on
             # group-scoped buffs and the single-point-of-failure flag on raid-wide ones.
             "oursCount": count_providers(ours_pairs, c["class"], c["spec"]),
             "theirsCount": count_providers(theirs_pairs, c["class"], c["spec"])}
            for c in PROVIDER_CHECKS]
    composition = {
        "oursClasses": class_counts(ours_roster), "theirsClasses": class_counts(theirs_roster),
        "oursSize": len(ours_roster), "theirsSize": len(theirs_roster), "gaps": gaps,
        "specDiff": spec_comp_diff(ours_roster, theirs_roster),
    }

    # Audit
    ours_roster_names = [p["name"] for p in ours_roster]
    theirs_roster_names = [p["name"] for p in theirs_roster]
    # Windfury presence (per-player, from the shared-boss consumes files) lets the weapon-oil check
    # treat Windfury as a valid substitute for melee — no false "missing oil" on a Windfury-group melee.
    ours_wf = windfury_players(ours_dir, common_ids)
    theirs_wf = windfury_players(theirs_dir, common_ids)
    audit_ours = audit_report(ours_dir, ours_roster_names, ours_spec, ours_wf)
    audit_theirs = audit_report(theirs_dir, theirs_roster_names, theirs_spec, theirs_wf)
    audit_ours["avgIlvl"] = avg_ilvl(ours_dir, common_ids)
    audit_theirs["avgIlvl"] = avg_ilvl(theirs_dir, common_ids)
    audit = {"ours": audit_ours, "theirs": audit_theirs}

    # Consumable coverage (flask/food/elixir/drums/potions) from the per-boss Buffs tables.
    consumables = {
        "ours": consumable_report(ours_dir, ours_idx, common_ids, len(ours_roster)),
        "theirs": consumable_report(theirs_dir, theirs_idx, common_ids, len(theirs_roster)),
    }
    # Opener-potion (prepot) timing (EXPERIMENTAL) — did the throughput potion land ON THE PULL, ours vs
    # benchmark, per boss. The timing decomposition of the potion-uses count (raid-aggregate, labelled).
    prepot = {"ours": prepot_timing(ours_dir, ours_idx, common_ids),
              "theirs": prepot_timing(theirs_dir, theirs_idx, common_ids)}
    # Per-player consumable participation (ours only — a coaching view of your own raid).
    per_player_consumes = per_player_consumables(ours_dir, ours_idx, common_ids)
    # Per-player IN-COMBAT consumable usage (ours only): combat potion / health pot / mana pot / healthstone.
    per_player_incombat_ours = per_player_incombat(ours_dir, ours_idx, common_ids, ours_roster)
    # Throughput consumables: combat-potion activations by spec (ours vs benchmark) + which flasks/elixirs.
    potion_spec_gap = potion_gap(
        potion_usage_by_spec(ours_dir, ours_idx, common_ids, ours_spec, ours_role, ours_cls),
        potion_usage_by_spec(theirs_dir, theirs_idx, common_ids, theirs_spec, theirs_role, theirs_cls))

    # Per-boss
    ours_fights = fight_map(ours_dir)
    theirs_fights = fight_map(theirs_dir)
    # Maps for the per-spec timeline curves: source actor id -> name, and pet -> owner (computed once).
    o_id_to_name = {v: k for k, v in name_id_map(ours_dir).items()}
    t_id_to_name = {v: k for k, v in name_id_map(theirs_dir).items()}
    o_pet = pet_owner_map(ours_dir)
    t_pet = pet_owner_map(theirs_dir)
    # Positioning role maps (actor id -> tank/melee/ranged/healer) + tank-id sets, computed once. Drive the
    # per-boss Positioning views; graceful when no positions-<enc>.json exists (the section just won't render).
    o_pos_roles = positioning.role_map(ours_roster, name_id_map(ours_dir))
    t_pos_roles = positioning.role_map(theirs_roster, name_id_map(theirs_dir))
    o_tank_ids = {a for a, r in o_pos_roles.items() if r == "tank"}
    t_tank_ids = {a for a, r in t_pos_roles.items() if r == "tank"}
    pos_spread_gaps = []   # per-vetted-boss spread-vs-demand gaps → Overview headline
    pos_melee_rows = []    # per-non-mobile-boss melee in-range % → Execution view
    # Accumulators for the tier-wide views (item level by role).
    o_ilvl, t_ilvl = {}, {}
    o_raid_dmg_sum = t_raid_dmg_sum = o_raid_heal_sum = t_raid_heal_sum = 0
    # Tier-wide gap rollups: per-spec DPS pools (across all bosses) + buff/debuff uptime samples.
    tier_o_spec, tier_t_spec = {}, {}
    tier_o_dmg, tier_t_dmg = {}, {}  # avoidable damage by ability (ex-tanks), pooled tier-wide — EXPERIMENTAL
    ours_player_dps = {}  # name -> [per-boss DPS] → night-average DPS per raider, for the Ghost Run
    tier_upt = {}  # aura name -> {"kind": buff|debuff, "o": [uptimes], "t": [uptimes]}
    tier_dtime = {}  # debuff name -> {"o_est":[],"o_gap":[],"t_est":[],"t_gap":[]} — ramp/continuity, EXPERIMENTAL
    o_leaked_acc, t_leaked_acc = {}, {}  # ability -> {"kicked","leaked"}, pooled tier-wide
    per_boss = []
    for b in bosses:
        enc = str(b["encounterID"])
        o_b = load_boss(ours_dir, enc)
        t_b = load_boss(theirs_dir, enc)
        if not o_b or not t_b:
            continue
        o_dur = ours_fights[enc]["end"] - ours_fights[enc]["start"]
        t_dur = theirs_fights[enc]["end"] - theirs_fights[enc]["start"]
        pn = ours_phase_names.get(enc) or theirs_phase_names.get(enc) or {}  # phase id -> name

        # Pool leaked-interrupt counts tier-wide (proven-interruptible casts that went off).
        for _acc, _rep in ((o_leaked_acc, o_b), (t_leaked_acc, t_b)):
            for _nm, _v in leaked_casts(_rep).items():
                _e = _acc.setdefault(_nm, {"kicked": 0, "leaked": 0})
                _e["kicked"] += _v["kicked"]
                _e["leaked"] += _v["leaked"]

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
        # Debuff RAMP + CONTINUITY (EXPERIMENTAL): when each key debuff first landed + its longest gap.
        o_dt = debuff_timing(_auras(o_b, "debuffs"), ours_fights[enc]["start"], o_dur, KEY_DEBUFFS)
        t_dt = debuff_timing(_auras(t_b, "debuffs"), theirs_fights[enc]["start"], t_dur, KEY_DEBUFFS)
        for nm, v in o_dt.items():
            rec = tier_dtime.setdefault(nm, {"o_est": [], "o_gap": [], "t_est": [], "t_gap": []})
            rec["o_est"].append(v["est"])
            rec["o_gap"].append(v["gap"])
        for nm, v in t_dt.items():
            rec = tier_dtime.setdefault(nm, {"o_est": [], "o_gap": [], "t_est": [], "t_gap": []})
            rec["t_est"].append(v["est"])
            rec["t_gap"].append(v["gap"])

        o_dmg = dmg_taken_ex_tanks(o_b, ours_tank)
        t_dmg = dmg_taken_ex_tanks(t_b, theirs_tank)
        # Pool non-tank damage-taken by ability tier-wide → Avoidable Damage by Mechanic (EXPERIMENTAL).
        for _nm, _v in ability_agg(o_b, ours_tank).items():
            tier_o_dmg[_nm] = tier_o_dmg.get(_nm, 0) + _v
        for _nm, _v in ability_agg(t_b, theirs_tank).items():
            tier_t_dmg[_nm] = tier_t_dmg.get(_nm, 0) + _v
        # Each raider's per-boss DPS → their night-average DPS, the projection rate for the Ghost Run.
        for _e in _entries(o_b, "dd"):
            _nm = _e.get("name")
            if _nm:
                ours_player_dps.setdefault(_nm, []).append(rate(int(_e.get("total", 0)), o_dur))

        # Raid output for this boss (total damage/healing / duration).
        o_raid_dmg, t_raid_dmg = raid_sum(o_b, "dd"), raid_sum(t_b, "dd")
        o_raid_heal, t_raid_heal = raid_sum(o_b, "heal"), raid_sum(t_b, "heal")
        # Feed the tier-wide accumulators.
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
        o_deaths = death_list(o_b, ours_fights[enc]["start"], ours_npc)
        t_deaths = death_list(t_b, theirs_fights[enc]["start"], theirs_npc)
        o_tl = load_timeline(ours_dir, enc)
        t_tl = load_timeline(theirs_dir, enc)
        tl_payload = timeline_view(o_tl, t_tl, o_deaths, t_deaths, o_lust, t_lust,
                                   o_dur, t_dur, ours_fights[enc], theirs_fights[enc])
        if tl_payload:
            # Per-spec DPS/HPS curves (overlapping specs only) for the per-spec Timeline sub-tabs.
            tl_payload["specs"] = spec_timelines(
                o_tl, t_tl,
                (o_id_to_name, ours_spec, ours_role, ours_cls, o_pet),
                (t_id_to_name, theirs_spec, theirs_role, theirs_cls, t_pet))
        # Positioning (feature 2 — tabbed formation snapshots + spread-vs-demand verdict) — one per-boss sub-tab
        # fragment + the scalars the Overview headline (spread gap) and Execution melee view consume. Mobile
        # bosses DO render (their plant-window snapshots); pos_html is None only when there's no positions file
        # (older data folder) or no settled plant window long enough to snapshot.
        pos_html = None
        o_pos = positioning.load_positions(ours_dir, enc)
        t_pos = positioning.load_positions(theirs_dir, enc)
        if o_pos and t_pos:
            # Phase boundaries (id + sec into fight) per side → phase-anchored formation snapshots.
            o_ph = (tl_payload.get("ours") or {}).get("phases") if tl_payload else None
            t_ph = (tl_payload.get("theirs") or {}).get("phases") if tl_payload else None
            # Spread-over-time: the squishy-cohort spread radius (yd) bucketed across the fight, ours vs
            # benchmark, on the SAME time axis as the DPS curves so a leader can read WHEN spread blew out
            # (e.g. spiking at a mechanic while the benchmark held). Frame-independent, so it's valid on
            # every boss class (mobile included). Lives in the per-boss Timeline sub-tab.
            o_spread = positioning.spread_series(o_pos, o_pos_roles)
            t_spread = positioning.spread_series(t_pos, t_pos_roles)
            if tl_payload and (o_spread or t_spread):
                tl_payload["spread"] = {"ours": o_spread, "theirs": t_spread}
            pos_res = positioning.boss_positioning(
                o_pos, t_pos, o_pos_roles, t_pos_roles, o_tank_ids, t_tank_ids,
                b["name"], ours_name, theirs_name, o_phases=o_ph, t_phases=t_ph, phase_names=pn)
            if pos_res:
                pos_html = pos_res["html"]
                if pos_res.get("spreadGap"):
                    pos_spread_gaps.append(pos_res["spreadGap"])
                if pos_res.get("meleeUptime"):
                    pos_melee_rows.append(pos_res["meleeUptime"])
        per_boss.append({
            "positioning": pos_html,
            "encounterID": b["encounterID"], "name": b["name"],
            "oursLustSec": o_lust,
            "theirsLustSec": t_lust,
            # Bloodlust window payoff (EXPERIMENTAL): DPS in the 40s lust window ÷ fight-average DPS.
            "oursLustMult": lust_window_mult(o_tl, o_lust),
            "theirsLustMult": lust_window_mult(t_tl, t_lust),
            # Cooldown↔lust alignment (EXPERIMENTAL): share of major cooldowns that fired in the lust window.
            "oursLustCd": cooldown_lust_alignment(_auras(o_b, "buffs"), o_lust, ours_fights[enc]["start"]),
            "theirsLustCd": cooldown_lust_alignment(_auras(t_b, "buffs"), t_lust, theirs_fights[enc]["start"]),
            "oursRaidDps": rate(o_raid_dmg, o_dur), "theirsRaidDps": rate(t_raid_dmg, t_dur),
            "oursRaidHps": rate(o_raid_heal, o_dur), "theirsRaidHps": rate(t_raid_heal, t_dur),
            "specGap": spec_gap(o_b, t_b, ours_spec, ours_role, ours_cls,
                                theirs_spec, theirs_role, theirs_cls, o_dur, t_dur),
            "buffs": buff_rows, "debuffs": debuff_rows,
            # Per-enemy-target debuff zoom (which enemy each key debuff lands on, ours vs theirs); [] unless
            # the boss has a real multi-target split (e.g. Kael'thas council). Renders under Boss Debuffs.
            "targetDebuffs": per_target_debuffs(ours_dir, theirs_dir, enc),
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
            "deathTiming": death_timing(o_deaths, ours_fights[enc], pn),
            "deathCascade": death_cascades(o_deaths),
            "openerGap": opener_gap(o_tl, t_tl),
            "phases": phase_compare(ours_fights[enc], theirs_fights[enc], pn),
            "threat": {"ours": threat_pulls(o_b, ours_fights[enc], ours_role, b["name"],
                                            spec_map=ours_spec, class_map=ours_cls),
                       "theirs": threat_pulls(t_b, theirs_fights[enc], theirs_role, b["name"],
                                              spec_map=theirs_spec, class_map=theirs_cls)},
            "targetEngagement": target_engagement(o_tl, t_tl, ours_npc, theirs_npc, b["name"]),
            "timeline": tl_payload,
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
    # Derived read: is the raid-DPS gap an uptime/movement problem or a throughput one?
    quality["dpsDiagnosis"] = dps_diagnosis(quality)

    # Surface per-boss raid DPS/HPS on the Overview boss cards (keyed by encounter).
    raid_out = {p["encounterID"]: p for p in per_boss}
    for b in bosses:
        ro = raid_out.get(b["encounterID"])
        if ro:
            b["oursRaidDps"], b["theirsRaidDps"] = ro["oursRaidDps"], ro["theirsRaidDps"]
            b["oursRaidHps"], b["theirsRaidHps"] = ro["oursRaidHps"], ro["theirsRaidHps"]

    # Tier-wide item level by role.
    output_breakdown = {
        "oursRoleIlvl": role_ilvl(o_ilvl, ours_roster),
        "theirsRoleIlvl": role_ilvl(t_ilvl, theirs_roster),
    }
    # "What's killing us" — death causes aggregated across the whole shared clear.
    death_causes_rows = death_cause_compare(per_boss)
    # Avoidable Damage by Mechanic (EXPERIMENTAL) — the damage analog: non-tank damage-taken per ability,
    # per-second (fight-length-normalized), tier-wide, where we take the most more than the benchmark.
    avoidable_damage = avoidable_damage_gap(tier_o_dmg, tier_t_dmg, o_dur_sum, t_dur_sum)
    # Tier-wide comprehensive gap rollups (stitched from the per-boss data above).
    tier_spec = tier_spec_gap(tier_o_spec, tier_t_spec)
    tier_uptime = tier_uptime_gap(tier_upt)
    # Hit / Expertise itemization audit (combatantInfo.stats) — EXPERIMENTAL. The snapshot is GEAR hit;
    # we fold in each side's detectable raid spell-hit (Improved Faerie Fire, +3% when a Balance Druid is
    # in the roster) → effective hit, and compare effective-to-effective so a buff asymmetry (we run
    # boomkins, the benchmark doesn't) doesn't wrongly flag our effectively-capped casters.
    stat_audit_payload = stat_audit_compare(
        stat_audit(ours_dir, ours_role, ours_spec, ours_cls, ours_roster_names, spell_hit_env(ours_roster)),
        stat_audit(theirs_dir, theirs_role, theirs_spec, theirs_cls, theirs_roster_names, spell_hit_env(theirs_roster)))
    # Time lost to deaths (EXPERIMENTAL) — the TIME companion to "What's Killing Us": output-minutes
    # burned by deaths, by cause + raid total. % base = roster × total shared-boss fight time.
    o_avail = len(ours_roster) * (o_dur_sum / 1000.0)
    t_avail = len(theirs_roster) * (t_dur_sum / 1000.0)
    death_time = death_time_compare(per_boss, o_avail, t_avail)
    # Ghost run (EXPERIMENTAL) — the counterfactual cost of our deaths. Projected at each raider's
    # NIGHT-AVERAGE DPS (a stable rate), forfeited output is the solid number; the kill-time is an
    # upper-bound (pure-DPS-race) estimate. Assembled per boss after the loop, once avg DPS is known.
    avg_dps = {nm: (sum(v) / len(v)) for nm, v in ours_player_dps.items() if v}
    ghost_bosses = []
    for p in per_boss:
        # DPS-ONLY: the ghost run is a lost-DPS-output story, so only DPS-role deaths count. A dead healer
        # or tank costs the raid differently (healing/survivability, not raid DPS), which lives in the death
        # views, not here.
        dps_deaths = [d for d in p["deaths"]["ours"] if ours_role.get(d.get("name")) == "dps"]
        gb = ghost_run_for_boss(dps_deaths, p["oursDurMs"], p["oursRaidDps"], avg_dps)
        if not gb:
            continue
        ghost_bosses.append(dict(gb, boss=p["name"]))
    ghost_run = {"bosses": ghost_bosses,
                 "totalTimeSavedSec": ssum([b["timeSavedSec"] for b in ghost_bosses]),
                 "totalForfeitedDmg": ssum([b["forfeitedDmg"] for b in ghost_bosses])}
    # Bloodlust/Heroism timing + window payoff + cooldown alignment (EXPERIMENTAL), from per-boss lust data.
    def _cdpct(cd):
        return cd.get("pct") if isinstance(cd, dict) else None
    bloodlust = {"rows": [{"boss": p["name"], "oursSec": p["oursLustSec"], "theirsSec": p["theirsLustSec"],
                           "oursMult": p.get("oursLustMult"), "theirsMult": p.get("theirsLustMult"),
                           "oursCdPct": _cdpct(p.get("oursLustCd")), "theirsCdPct": _cdpct(p.get("theirsLustCd"))}
                          for p in per_boss
                          if p["oursLustSec"] is not None or p["theirsLustSec"] is not None]}
    # Debuff ramp + continuity (EXPERIMENTAL): tier-wide establish-time + longest gap per key debuff.
    debuff_timing_rows = tier_debuff_timing(tier_dtime)
    # Wipe recovery (EXPERIMENTAL): wall-clock reset time between a wipe and the next pull, per boss.
    enc_names = {str(b["encounterID"]): b["name"] for b in bosses}
    wipe_rec = wipe_recovery_compare(wipe_recovery(ours_dir), wipe_recovery(theirs_dir), enc_names)
    # Wipes tab (EXPERIMENTAL) — comprehensive per-boss wipe progression: the wall, the trend, the
    # progression tax, and (from the wipe-fight deaths) what ends the attempts. First-party by nature.
    wipes = {"ours": wipe_analysis(ours_dir, enc_names, ours_phase_names),
             "theirs": wipe_analysis(theirs_dir, enc_names, theirs_phase_names)}
    # Tier-wide leaked interrupts (proven-interruptible casts that went off un-kicked, ours vs benchmark).
    leaked_rows = leaked_interrupts_gap(o_leaked_acc, t_leaked_acc)
    # Tier-wide cooldown/trinket usage (clean better/worse; buff- + cast-sourced). cd_usage_pool reads the
    # per-player buff `uses` + trinket casts per side.
    tier_cd = tier_cd_usage(
        cd_usage_pool(ours_dir, ours_idx, common_ids, ours_spec, ours_role, ours_cls, ours_fights),
        cd_usage_pool(theirs_dir, theirs_idx, common_ids, theirs_spec, theirs_role, theirs_cls, theirs_fights))
    # Tier-wide early-aggro (threat pulls) + focus-fire concentration, rolled up from the per-boss data.
    threat_rows = []
    for p in per_boss:
        o = (p.get("threat") or {}).get("ours") or {}
        t = (p.get("threat") or {}).get("theirs") or {}
        if (o.get("total") or 0) or (t.get("total") or 0):
            # Spec attribution for OUR pulls only — the actionable side (who on our team to coach). Sorted
            # most-pulls-first so the offender names itself; opener pulls flagged separately (the real signal).
            by_spec = sorted(
                ({"class": k.split("|", 1)[0], "spec": k.split("|", 1)[1], "count": c,
                  "openerCount": (o.get("openerBySpec") or {}).get(k, 0)}
                 for k, c in (o.get("bySpec") or {}).items()),
                key=lambda r: (-r["count"], -r["openerCount"]))
            threat_rows.append({"boss": p["name"], "oursTotal": o.get("total", 0), "oursOpener": o.get("opener", 0),
                                "theirsTotal": t.get("total", 0), "theirsOpener": t.get("opener", 0),
                                "oursEarliest": o.get("earliestSec"), "oursBySpec": by_spec})
    threat_summary = {"rows": threat_rows,
                      "oursTotal": ssum([r["oursTotal"] for r in threat_rows]),
                      "theirsTotal": ssum([r["theirsTotal"] for r in threat_rows]),
                      "oursOpener": ssum([r["oursOpener"] for r in threat_rows]),
                      "theirsOpener": ssum([r["theirsOpener"] for r in threat_rows])}
    # Per-boss target engagement (boss + named adds: when each first appeared + how long it was engaged).
    target_eng_rows = [{"boss": p["name"], "targets": p["targetEngagement"]}
                       for p in per_boss if p.get("targetEngagement")]

    # Trash analysis (on by default; graceful {present:false} on older data folders without trash files).
    # Built before the scorecard so the big trash-deaths gap can feed the Overview Biggest Gaps cards.
    trash = build_trash(ours_dir, theirs_dir)

    # Optimize tab — each raider's rotation vs a same-faction world-best player of their spec (reads
    # worldbest.json from the fetch stage; graceful {present:false} on older folders without it).
    # Cross-link (EXPERIMENTAL): a per-raider hit/expertise flag from the Prep stat audit, so a diverging
    # rotation row can note when part of the gap is a fixable GEAR problem (under the hit cap → missed
    # casts), not a sequencing choice. Reuses the already-computed stat audit — coach-not-blame, absolute.
    hit_map = {p["name"]: {"effPct": p["effPct"], "cap": p["cap"], "under": p["under"],
                           "gap": p["gap"], "hitType": p["hitType"]}
               for p in stat_audit_payload["players"] if p.get("under")}
    optimize = build_optimize(ours_dir, ours_idx, ours_spec, ours_cls, common_ids, hit_map=hit_map)

    # "Biggest Gaps" scorecard — rank every tracked dimension by distance to the benchmark.
    gaps_scorecard = biggest_gaps(summary, quality, consumables, audit, gaps,
                                  tier_spec=tier_spec, tier_uptime=tier_uptime, trash=trash,
                                  death_causes=death_causes_rows, leaked=leaked_rows, threat=threat_summary)
    # "What You're Doing Well" — the same comparison, the other direction (where we lead the benchmark).
    did_well = strengths(summary, quality, consumables, audit, gaps,
                         tier_spec=tier_spec, tier_uptime=tier_uptime, trash=trash)

    eff = {"ours": efficiency(ours_dir, common_ids), "theirs": efficiency(theirs_dir, common_ids)}

    # Positioning tier payloads: the Execution melee-uptime view (non-mobile bosses) + the single biggest
    # spread-vs-demand call for the Overview headline. Both are pre-rendered HTML fragments (stdlib SVG);
    # "" when no boss supports them, so the template renders nothing.
    positioning_payload = {
        "meleeView": positioning.melee_uptime_view(pos_melee_rows, ours_name, theirs_name),
        "headline": positioning.spread_headline(pos_spread_gaps),
    }

    # The Bosses tab only needs each shared boss's id + name to build its sub-tabs (the old Kill
    # Summary & Rosters block that consumed the full per-side rosters/parses was cut). Ship a slim
    # list instead of the heavy index objects (which still carry full `players` rosters used elsewhere
    # in the builder) so the report payload doesn't haul a roster dump nothing renders.
    bosses_slim = [{"encounterID": b["encounterID"], "name": b["name"]} for b in bosses]
    payload = {
        "zone": zone_name, "ours": {"title": ours_name}, "theirs": {"title": theirs_name},
        "summary": summary, "bosses": bosses_slim, "gapsScorecard": gaps_scorecard, "didWell": did_well,
        "deep": {"composition": composition, "audit": audit, "consumables": consumables,
                 "perPlayerConsumes": per_player_consumes, "perPlayerInCombat": per_player_incombat_ours,
                 "potionGap": potion_spec_gap, "prepot": prepot,
                 "outputBreakdown": output_breakdown,
                 "deathCauses": death_causes_rows, "avoidableDamage": avoidable_damage,
                 "tierSpecGap": tier_spec, "tierUptimeGap": tier_uptime,
                 "statAudit": stat_audit_payload,
                 "deathTime": death_time, "ghostRun": ghost_run, "bloodlust": bloodlust,
                 "debuffTiming": debuff_timing_rows, "wipeRecovery": wipe_rec,
                 "leakedInterrupts": leaked_rows, "tierCdUsage": tier_cd,
                 "threatPulls": threat_summary, "targetEngagement": target_eng_rows,
                 "quality": quality, "perBoss": per_boss, "efficiency": eff, "trash": trash,
                 "wipes": wipes, "optimize": optimize, "positioning": positioning_payload},
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
