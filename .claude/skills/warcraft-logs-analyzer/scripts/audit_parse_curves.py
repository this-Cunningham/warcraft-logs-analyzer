"""audit_parse_curves.py — ONE-TIME (offline) audit that bakes the per-spec parse-distribution SHAPE.

Parse-amount distributions don't collapse to ONE universal curve (the lower tail splits by spec — pug-heavy
specs like Fire Mage have a long low tail, others are compressed), BUT a given spec's shape is **boss-stable**.
So we characterise each DPS spec's curve ONCE here and bake it as a constant. At report time `build_deepdive`
scales that per-spec curve with a FREE anchor (our own raider's real amount+percentile on the boss) to read
a ghost parse — accurate-ish, zero per-report API cost.

Run occasionally to refresh:  python3 audit_parse_curves.py
Then paste the printed `SPEC_PARSE_CURVE = {...}` block into build_deepdive.py.

Normalisation: each spec's curve is amount-at-percentile ÷ amount-at-p50 (median), so it's scale-free; the
report multiplies it back up via an anchor. Percentile grid is denser in the upper half, where revived
early-death raiders (the ghost-parse use case) land.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

# DPS specs to bake (WCL className/specName, verbatim). Healers excluded — ghost parse is DPS-based.
SPECS = [
    ("Mage", "Fire"), ("Mage", "Arcane"), ("Mage", "Frost"),
    ("Warlock", "Affliction"), ("Warlock", "Destruction"), ("Warlock", "Demonology"),
    ("Priest", "Shadow"),
    ("Hunter", "BeastMastery"), ("Hunter", "Marksmanship"), ("Hunter", "Survival"),
    ("Rogue", "Combat"), ("Rogue", "Assassination"), ("Rogue", "Subtlety"),
    ("Warrior", "Arms"), ("Warrior", "Fury"),
    ("Druid", "Balance"), ("Druid", "Feral"),
    ("Shaman", "Elemental"), ("Shaman", "Enhancement"),
    ("Paladin", "Retribution"),
]
# Encounters to source a distribution from (tried in order until one has a decent population). These are the
# SSC/TK bosses the pinned reports use; the shape is boss-stable so any populous one is representative.
ENCOUNTERS = [100732, 100731, 100733, 100730, 100628, 100626]
PCTS = [1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 85, 90, 93, 95, 97, 99]
MIN_POOL = 300
MAX_PAGES = 40

Q = ("query R($id:Int!,$cl:String!,$sp:String!,$p:Int!){worldData{encounter(id:$id){"
     "characterRankings(metric:dps,className:$cl,specName:$sp,page:$p)}}}")


def _full_dist(eid, cl, sp):
    amts = []
    for p in range(1, MAX_PAGES + 1):
        rk, more = None, False
        for attempt in range(6):
            try:
                r = lib.invoke_query(Q, {"id": eid, "cl": cl, "sp": sp, "p": p})["worldData"]["encounter"]["characterRankings"]
                rk = r.get("rankings") or []
                more = r.get("hasMorePages")
                break
            except Exception as e:
                if any(x in str(e) for x in ("503", "502", "429")):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return []
        if not rk:
            break
        amts += [a["amount"] for a in rk if a.get("amount")]
        if not more:
            break
    return sorted(amts)


def _at_pct(asc, p):
    if not asc:
        return None
    f = p / 100.0 * (len(asc) - 1)
    lo = int(f)
    hi = min(lo + 1, len(asc) - 1)
    return asc[lo] + (asc[hi] - asc[lo]) * (f - lo)


def main():
    curve = {}
    for cl, sp in SPECS:
        dist, used = [], None
        for eid in ENCOUNTERS:
            d = _full_dist(eid, cl, sp)
            if len(d) >= MIN_POOL:
                dist, used = d, eid
                break
        key = "{}|{}".format(cl, sp)
        if not dist:
            print("  # {} — no pool >= {} on any tried encounter, skipped".format(key, MIN_POOL), file=sys.stderr)
            continue
        med = _at_pct(dist, 50) or 1.0
        norm = [(p, round(_at_pct(dist, p) / med, 3)) for p in PCTS]
        curve[key] = norm
        print("  # {:24} N={:<5} (enc {})".format(key, len(dist), used), file=sys.stderr)

    # Emit a paste-ready Python literal.
    print("SPEC_PARSE_CURVE = {")
    for key, norm in curve.items():
        pts = ", ".join("({},{})".format(p, v) for p, v in norm)
        print('    "{}": [{}],'.format(key, pts))
    print("}")


if __name__ == "__main__":
    main()
