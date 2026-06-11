---
name: silent-overwrite
description: Audit for dict construction from external data lists where duplicate keys silently clobber earlier entries — last-one-wins with no warning, dropping valid data. Invoked as `/silent-overwrite`.
allowed-tools: Read, Grep, Glob, Bash
---

# silent-overwrite

`{x["name"]: x for x in players}` — if two players share a name, the second silently overwrites the first. No error. One player's data vanishes. WCL data has known sources of duplicates: dual-role players appear in multiple `playerDetails` buckets, same-name NPCs share an actor ID, auras for the same spell can appear more than once.

## What to scan

- Dict comprehensions on external data: `{x["key"]: x for x in <wcl_list>}`
- Manual dict assignment in a loop: `d[x["name"]] = x` where the list comes from WCL
- `setdefault` / `update` patterns that might mask collisions
- Any deduplication that uses `seen.add(key)` — what happens to the second occurrence? Is it silently dropped, or does it need to be merged?

Focus on: `build_deepdive.py`, `fetch_report.py` — anywhere player details, aura lists, fight entries, or NPC data is indexed by name or ID.

## How to verify

Check the cached data for actual duplicates on the key being used:

```bash
python -c "
import json, glob
from collections import Counter
for f in glob.glob('data/**/player-details*.json', recursive=True):
    d = json.load(open(f))
    # check for duplicate player names across role buckets
    names = []
    for role_list in d.values():
        if isinstance(role_list, list):
            names += [p.get('name') for p in role_list if isinstance(p, dict)]
    dupes = {k: v for k, v in Counter(names).items() if v > 1}
    if dupes: print(f, dupes)
"
```

Also check aura lists for duplicate names (same spell, multiple entries):
```bash
python -c "
import json, glob
from collections import Counter
for f in glob.glob('data/**/boss-*.json', recursive=True):
    d = json.load(open(f))
    auras = d.get('reportData',{}).get('report',{}).get('buffs',{}).get('data',{}).get('auras',[])
    dupes = {k:v for k,v in Counter(a['name'] for a in auras).items() if v > 1}
    if dupes: print(f, dupes)
"
```

## Output

For each finding:
- **Location** — file:line
- **Key used** — what field is being used as the dict key
- **Duplicates confirmed?** — yes/no from cached data check
- **What gets dropped** — which entry is lost (first, or a specific role/type)
- **Correct fix** — merge the entries, use a list, or deduplicate intentionally before indexing
