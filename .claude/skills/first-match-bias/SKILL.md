---
name: first-match-bias
description: Audit for next() / [0] / slice calls that take the first matching item from external data when multiple candidates can exist — silently returning the wrong one instead of the best one. Invoked as `/first-match-bias`.
allowed-tools: Read, Grep, Glob, Bash
---

# first-match-bias

`next((x for x in auras if x["name"] == "Foo"), None)` takes the *first* match. If WCL returns multiple entries for the same concept (two aura entries for the same buff, two player entries for a dual-role player, multiple NPC instances), first isn't necessarily correct — and the code has no idea it picked wrong.

## What to scan

- `next((x for x in <external_list> if ...), ...)` — taking first match from a WCL-sourced list
- `list[0]` or `list[-1]` on a list derived from external data without sorting or deduplication
- Any pattern that assumes a list filtered from external data has exactly one result

Focus on: `build_deepdive.py`, `fetch_report.py` — anywhere that reads auras, player details, fight entries, or cast lists from cached JSON.

## How to verify

For each `next()` / `[0]` found:

1. Check the cached data to confirm whether multiple matches can actually exist for that filter condition.
2. Ask: if there are multiple matches, is "first" correct? Or should it be "highest uptime", "earliest cast", "latest", "sum of all"?

```bash
python -c "
import json, glob
# Example: check how many auras share a given name
for f in glob.glob('data/**/boss-*.json', recursive=True):
    d = json.load(open(f))
    auras = d.get('reportData',{}).get('report',{}).get('buffs',{}).get('data',{}).get('auras',[])
    from collections import Counter
    c = Counter(a['name'] for a in auras)
    dupes = {k:v for k,v in c.items() if v > 1}
    if dupes: print(f, dupes)
"
```

## Output

For each finding:
- **Location** — file:line
- **What it takes first from** — the list/generator being iterated
- **Multiple matches possible?** — confirmed yes/no from cached data
- **Correct selection** — what it should take instead (max uptime, earliest, sum, etc.)
- **Failure mode** — what goes wrong silently when first isn't correct
