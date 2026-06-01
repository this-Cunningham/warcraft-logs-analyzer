"""report_common.py - shared helpers for the two report builders.

Holds the Overview extraction (from parse rankings) and the template-injection
render step, both used by build_comparison.py and build_deepdive.py.
"""

import json
import os

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "report.html")

_ROLE_LABEL = {"tanks": "tank", "healers": "healer", "dps": "dps"}


def read_json(path):
    # utf-8-sig strips a leading BOM if present (PowerShell's Set-Content -Encoding
    # utf8 writes one) and is harmless on BOM-less files written by Python.
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


# ---------- CROWD CONTROL (shared by the fetch + build steps) ----------
# Hard CC = a debuff that holds a mob OUT of the fight, as opposed to an incidental combat stun or
# a slow. Unlike consumable BUFFS (which WCL renames to their effect, so we classify those by spell
# id), CC DEBUFFS keep their real spell name in the logs — so a curated NAME allowlist is both
# reliable and rank-proof here. It deliberately excludes same-rooted non-CC ("Ice Trap"/"Explosive
# Trap" are AoE slow/damage, not a lockout) and rotational stuns (Kidney Shot, Cheap Shot, Gouge,
# Bash, Hammer of Justice) that are used mid-fight rather than to neutralize a mob.
HARD_CC_NAMES = {
    "Polymorph", "Banish", "Sap", "Shackle Undead", "Freezing Trap", "Seduction",
    "Hibernate", "Repentance", "Wyvern Sting", "Cyclone", "Mind Control",
}


def cc_label(name):
    """Return the canonical hard-CC label for a debuff aura name, or None if it isn't hard CC.
    Handles the "… Effect" suffix (e.g. "Freezing Trap Effect") and Polymorph's rank/variant
    names ("Polymorph: Pig")."""
    if not name:
        return None
    base = name[:-len(" Effect")].strip() if name.endswith(" Effect") else name
    if base.startswith("Polymorph"):
        return "Polymorph"
    return base if base in HARD_CC_NAMES else None


def avg(vals):
    """Mean of non-null values, rounded to 1 decimal (0 when empty). Banker's
    rounding matches PowerShell's [math]::Round default."""
    nums = [v for v in vals if v is not None]
    if not nums:
        return 0
    return round(sum(nums) / len(nums), 1)


def ssum(vals):
    """Integer sum, skipping nulls (mirrors PowerShell Measure-Object -Sum)."""
    return int(sum(v for v in vals if v is not None))


def get_fights(path):
    return read_json(path)["reportData"]["report"]["rankings"]["data"]


def get_players(fight):
    players = []
    roles = fight.get("roles") or {}
    for rn in ("tanks", "healers", "dps"):
        role = roles.get(rn)
        if not role:
            continue
        for c in role.get("characters", []):
            players.append({
                "name": c.get("name"),
                "class": c.get("class"),
                "spec": c.get("spec"),
                "role": _ROLE_LABEL[rn],
                "parse": int(c.get("rankPercent", 0)),
                "amount": round(float(c.get("amount", 0)), 1),
            })
    return players


def index_by_encounter(fights):
    """Map str(encounterID) -> {name, durationMs, deaths, avgParse, players}.
    Insertion order follows the API's kill order (Python dicts preserve it)."""
    out = {}
    for f in fights:
        players = get_players(f)
        parses = [p["parse"] for p in players if p["parse"] >= 0]
        avg_parse = round(sum(parses) / len(parses), 1) if parses else 0
        out[str(f["encounter"]["id"])] = {
            "name": f["encounter"]["name"],
            "durationMs": int(f["duration"]),
            "deaths": int(f["deaths"]),
            "avgParse": avg_parse,
            "players": players,
        }
    return out


def render_report(payload, out_file):
    """Inject the data blob into the static HTML template and write the report.

    Mirrors the PowerShell builders: read the template UTF-8, replace the literal
    `/*__DATA__*/null`, write UTF-8 (no BOM). json.dumps defaults to ascii-safe
    output, so multibyte names land as \\uXXXX escapes just like ConvertTo-Json did.
    """
    blob = json.dumps(payload, separators=(",", ":"))
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        tpl = fh.read()
    html = tpl.replace("/*__DATA__*/null", blob)

    out_full = os.path.abspath(out_file)
    out_dir = os.path.dirname(out_full)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(out_full, "w", encoding="utf-8", newline="") as fh:
        fh.write(html)
    return out_full
