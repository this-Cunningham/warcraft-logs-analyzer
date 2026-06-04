"""fetch_worldbest.py - fetch each of our specs' WORLD-BEST same-faction rotation.

The Optimize tab benchmarks every individual raider's cast mix against a top-ranked
player of the SAME class/spec and the SAME faction as our raid. This module does the
network half (it must run where credentials live, alongside the rest of the fetch
stage) and writes a single `worldbest.json` into our report's data dir; the build
stage reads that file and is otherwise pure/deterministic.

For each distinct DPS/healer (class, spec) our raid fielded, and for EACH shared boss:
  1. `worldData.encounter(id).characterRankings(metric, className, specName)` returns
     the global leaderboard for that encounter (top 100, sorted by amount desc). Each
     entry carries the player's `report{code,fightID}`, `guild`, `server`, and a raw
     `faction` int. We take the best entry whose faction matches ours — i.e. the best
     same-faction parse for that spec ON THAT BOSS (a different player may top each boss).
  2. We fetch that player's Casts table for their ranked fight and keep the raw
     per-ability cast tally (the build computes cast SHARE, so our raiders and the
     world-best are normalized the same way).
This is PER BOSS, not pooled: the build compares each raider to that boss's benchmark on
the same encounter, so every Optimize-tab gap is a real per-boss rotation gap.

FACTION ENCODING (verified live, 2026-06-03): a guild's `GameFaction` is id 1=Alliance,
2=Horde, but a characterRankings entry's `faction` int is 0=Alliance, 1=Horde. So the
ranking-entry faction we want is `guildFactionId - 1`.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # find sibling modules
import lib

# Guild faction (1=Alliance, 2=Horde) for our report — maps to the ranking-entry faction int below.
GUILD_Q = "query G($code:String!){reportData{report(code:$code){guild{name faction{id name}} region{slug}}}}"
RANK_Q = ("query R($enc:Int!,$cls:String!,$spec:String!,$metric:CharacterRankingMetricType!)"
          "{worldData{encounter(id:$enc){characterRankings(metric:$metric,className:$cls,specName:$spec)}}}")
CASTS_Q = "query C($code:String!,$f:[Int]!){reportData{report(code:$code){casts:table(dataType:Casts,fightIDs:$f)}}}"


def our_faction(code):
    """(factionId, factionName, regionSlug) for our report's guild. factionId is the GameFaction id
    (1=Alliance, 2=Horde). Returns (None, None, None) when the report has no guild (a PUG night)."""
    rep = (lib.invoke_query(GUILD_Q, {"code": code}).get("reportData") or {}).get("report") or {}
    g = rep.get("guild") or {}
    f = g.get("faction") or {}
    region = (rep.get("region") or {}).get("slug")
    return f.get("id"), f.get("name"), region


def _best_same_faction(enc, cls, spec, metric, want_faction):
    """The highest-ranked characterRankings entry on `enc` whose faction == want_faction (the best
    same-faction parse for this spec on this boss), tagged with its 1-based GLOBAL rank in the full
    (all-faction) leaderboard. None if the call fails or no same-faction entry is in the top page."""
    try:
        data = lib.invoke_query(RANK_Q, {"enc": enc, "cls": cls, "spec": spec, "metric": metric})
    except Exception as exc:  # a bad spec/metric or transient API error shouldn't sink the whole tab
        print("  [worldbest] rankings {}/{} enc {} failed: {}".format(cls, spec, enc, exc))
        return None
    cr = ((data.get("worldData") or {}).get("encounter") or {}).get("characterRankings") or {}
    for i, r in enumerate(cr.get("rankings") or []):
        if r.get("faction") == want_faction:
            return {"entry": r, "globalRank": i + 1}
    return None


def _world_casts(report_code, fight_id, player_name):
    """Raw {ability name -> cast total} for one player on one fight, from that report's Casts table.
    Empty dict if the report/fight/player can't be read (graceful — the spec still lists its benchmark
    player, just without a rotation to compare)."""
    try:
        data = lib.invoke_query(CASTS_Q, {"code": report_code, "f": [fight_id]})
    except Exception as exc:
        print("  [worldbest] casts {} fight {} failed: {}".format(report_code, fight_id, exc))
        return {}
    entries = (((data.get("reportData") or {}).get("report") or {}).get("casts") or {}).get("data") or {}
    for e in entries.get("entries") or []:
        if e.get("name") == player_name:
            out = {}
            for a in e.get("abilities") or []:
                if a.get("name"):
                    out[a["name"]] = out.get(a["name"], 0) + int(a.get("total", 0))
            return out
    return {}


def fetch(ours_code, specs, shared_encs, enc_names, out_path):
    """Find + fetch the same-faction world-best rotation for each spec; write worldbest.json.

    specs: list of {"class","spec","role"} (distinct, DPS/healer only — tanks have no clean ranking
           metric, mirroring the Rotation view which also excludes them).
    shared_encs: encounter ids (ints) to benchmark — EACH is searched for its own top same-faction parse,
                 so every shared boss our raiders killed gets a per-boss benchmark.
    enc_names: {encId(int) -> boss name} for labeling.
    Writes {"present", "factionId", "factionName", "region", "specs":[{class,spec,role,metric,bosses:[
            {encounterID,name,metric,player,abilities}, ...]}]} to out_path.
    """
    # World-ranking player/guild names carry accents (e.g. "Disastèr"); a cp1252 Windows console — or any
    # non-UTF-8 pipe — would raise UnicodeEncodeError on the first such print and abort the whole fetch,
    # leaving the Optimize tab empty. Make stdout lossy-but-safe so a name can never sink the fetch.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    fid, fname, region = our_faction(ours_code)
    if fid not in (1, 2):
        # No guild faction (PUG) -> can't honor "same faction"; write a graceful empty marker.
        print("  [worldbest] no guild faction for {} -> skipping world-best tab".format(ours_code))
        payload = {"present": False, "reason": "no-faction"}
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return payload

    want = fid - 1  # GameFaction id (1/2) -> ranking-entry faction int (0/1)
    print("  [worldbest] our faction: {} (id {}) -> ranking faction int {}".format(fname, fid, want))
    out_specs = []
    for sp in specs:
        cls, spec, role = sp["class"], sp["spec"], sp["role"]
        metric = "hps" if role == "healer" else "dps"
        # PER BOSS: the top same-faction player for this spec ON THAT BOSS (may be a different person per
        # boss), with their casts on that boss's fight. The build compares our raiders to that boss's
        # benchmark on the SAME encounter — an apples-to-apples per-boss rotation read, not one pooled
        # across the whole tier. (Was: only the first shared boss with a ranking was benchmarked.)
        bosses_out = []
        for enc in shared_encs:
            hit = _best_same_faction(enc, cls, spec, metric, want)
            if not hit:
                continue
            e = hit["entry"]
            rep = e.get("report") or {}
            abilities = _world_casts(rep.get("code"), rep.get("fightID"), e.get("name"))
            bosses_out.append({
                "encounterID": enc, "name": enc_names.get(enc, str(enc)), "metric": metric,
                "player": {
                    "name": e.get("name"),
                    "guild": (e.get("guild") or {}).get("name"),
                    "server": (e.get("server") or {}).get("name"),
                    "region": (e.get("server") or {}).get("region"),
                    "amount": e.get("amount"),
                    "globalRank": hit["globalRank"],
                    "reportCode": rep.get("code"), "fightID": rep.get("fightID"),
                },
                "abilities": abilities,
            })
            p = bosses_out[-1]["player"]
            print("  [worldbest] {} {} on {}: #{} {} ({}) — {} casts".format(
                spec, cls, bosses_out[-1]["name"], p["globalRank"], p["name"],
                p["guild"] or "no guild", len(abilities)))
        if not bosses_out:
            print("  [worldbest] {} {}: no same-faction ranking on any shared boss".format(spec, cls))
        out_specs.append({"class": cls, "spec": spec, "role": role, "metric": metric, "bosses": bosses_out})

    payload = {"present": True, "factionId": fid, "factionName": fname, "region": region, "specs": out_specs}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print("  [worldbest] wrote {} ({} specs)".format(out_path, len(out_specs)))
    return payload


def fetch_for_report(ours_code, ours_parses, shared_encs, enc_names, out_path):
    """Convenience entry point for the pipeline: derive our distinct DPS/healer specs from the parses
    file, then fetch their same-faction world-best rotations. Keeps spec derivation identical to the
    report (same roster helpers) and gives compare_raids a one-line call."""
    specs = _specs_from_parses(ours_parses, shared_encs)
    return fetch(ours_code, specs, shared_encs, enc_names, out_path)


def _specs_from_parses(parses_path, shared_encs):
    """Distinct DPS/healer (class, primary-spec) combos in our roster — the CLI helper for manual runs.
    Imports the build's roster helpers so spec derivation stays identical to the report."""
    import report_common as rc
    import build_deepdive as bd
    idx = rc.index_by_encounter(rc.get_fights(parses_path))
    enc_strs = [str(e) for e in shared_encs]
    prim = bd.primary_spec_map(idx, enc_strs)
    seen, out = set(), []
    for enc in enc_strs:
        for p in idx.get(enc, {}).get("players", []):
            if p["role"] not in ("dps", "healer"):
                continue
            spec = prim.get(p["name"], p["spec"])
            key = (p["class"], spec, p["role"])
            if spec and key not in seen:
                seen.add(key)
                out.append({"class": p["class"], "spec": spec, "role": p["role"]})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Fetch same-faction world-best rotations for a report's specs.")
    p.add_argument("--ours-code", required=True)
    p.add_argument("--ours-parses", required=True, help="path to <code>-parses.json")
    p.add_argument("--shared", required=True, help="comma-separated shared encounter ids")
    p.add_argument("--enc-names", default="", help="optional id:name,id:name pairs for labels")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    shared = [int(x) for x in args.shared.split(",") if x.strip()]
    enc_names = {}
    for pair in args.enc_names.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            enc_names[int(k)] = v
    specs = _specs_from_parses(args.ours_parses, shared)
    fetch(args.ours_code, specs, shared, enc_names, args.out)


if __name__ == "__main__":
    main()
