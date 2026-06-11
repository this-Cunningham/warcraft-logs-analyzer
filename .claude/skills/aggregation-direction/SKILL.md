---
name: aggregation-direction
description: Audit for wrong aggregation choices on external data — summing when max/union is correct, taking max when sum is correct, averaging when neither is appropriate — producing silently inflated or deflated values. Invoked as `/aggregation-direction`.
allowed-tools: Read, Grep, Glob, Bash
---

# aggregation-direction

Uptime for a buff that appears in two aura entries: `sum()` double-counts overlapping windows; `max()` takes the larger single entry and ignores the other; the correct operation is a union of the time bands. DPS across multiple players: `sum()` is correct; `max()` would only count the top contributor. Wrong choice → silently wrong number with no error.

## What to scan

Aggregation operations on WCL-sourced lists — look at the semantic meaning of the operation, not just the syntax:

- `sum(x["totalUptime"] for x in auras if ...)` — if multiple aura entries represent the SAME underlying buff on the same target, summing double-counts overlapping time; union of bands is correct
- `sum(x["total"] for x in entries)` — is `total` a per-player absolute value (sum is correct) or a rate/percentage (sum is wrong)?
- `max(...)` across per-boss values — for a cumulative metric (total deaths, total casts), max across bosses is wrong; sum is correct
- Averages (`sum / len`) — is the denominator always non-zero? Is averaging across bosses valid when fight durations differ (duration-weighted average vs simple average)?
- Rolling up per-boss data to a tier-wide total — is the rollup operation consistent with the per-boss metric's definition?

Focus on: `build_deepdive.py` — `tier_cd_usage`, `tier_uptime_gap`, death/damage rollups, parse averaging.

## How to verify

For uptime specifically, check whether multiple aura entries for the same buff can have overlapping `bands`:

```bash
python -c "
import json, glob
for f in glob.glob('data/**/boss-*.json', recursive=True):
    d = json.load(open(f))
    auras = d.get('reportData',{}).get('report',{}).get('buffs',{}).get('data',{}).get('auras',[])
    from collections import Counter
    dupes = {k:v for k,v in Counter(a['name'] for a in auras).items() if v > 1}
    if dupes:
        print(f, dupes)
        for a in auras:
            if a['name'] in dupes:
                print(' ', a['name'], 'totalUptime:', a.get('totalUptime'), 'bands:', len(a.get('bands') or []))
    break
"
```

## Output

For each finding:
- **Location** — file:line
- **Operation** — what aggregation is applied (`sum`, `max`, `avg`, etc.)
- **Data being aggregated** — what the values represent
- **Correct operation** — what it should be and why
- **Failure mode** — inflated (double-counted), deflated (max of a sum), or wrong-unit result
