---
name: unit-mismatch
description: Audit for wrong unit assumptions — code that treats a WCL value as milliseconds when it's seconds, or as a fraction when it's a percentage, or as radians when it's centiradians — producing silently wrong numeric results. Invoked as `/unit-mismatch`.
allowed-tools: Read, Grep, Glob, Bash
---

# unit-mismatch

WCL data mixes units without labeling them. Fight times and durations are milliseconds. Parse percentiles are 0–100. Facing values are centiradians (radians × 100). Uptime is milliseconds. A single wrong assumption produces a value that's off by 100×, 1000×, or a sign flip — and it looks like a number, so nothing breaks.

## Known units in this codebase

- **Fight times** (`startTime`, `endTime`, band `startTime`/`endTime`) — **milliseconds**
- **`totalUptime`** in aura entries — **milliseconds**
- **Parse percentiles** — **0–100** integer
- **`facing`** in position events — **centiradians** (decode: `heading = -facing / 100`)
- **x/y coordinates** — **yards** (roughly; WCL internal units)
- **DPS / HPS values** — per-second already (not per-millisecond)
- **`totalUses`** in consumable/buff auras — **count** (not a rate)

## What to scan

- Division or multiplication by `1000` — is a ms→s or s→ms conversion correct here?
- Division or multiplication by `100` — is a fraction→percent or percent→fraction conversion correct?
- Division by `dur_ms` or similar — is `dur_ms` definitely in ms, and is `totalUptime` also in ms?
- Use of `facing` values — is the centiradians→radians decode applied before any trig?
- Anywhere a value derived from WCL is compared to a human-readable threshold (e.g. "if uptime > 0.9" — is 0.9 the right scale, or should it be 90?)

Focus on: `build_deepdive.py`, `positioning.py`, any script that reads fight times or position data.

## How to verify

Sample the cached data and spot-check the actual values against the assumed unit:

```bash
python -c "
import json, glob
for f in glob.glob('data/**/boss-*.json', recursive=True):
    d = json.load(open(f))
    rep = d['reportData']['report']
    auras = rep['buffs']['data']['auras']
    total_time = rep['buffs']['data']['totalTime']
    print('totalTime:', total_time, '  first aura uptime:', auras[0].get('totalUptime') if auras else 'n/a')
    break
"
```

If `totalTime` is ~300000 and a fight is ~5 minutes, units are milliseconds. If it's ~300, units are seconds.

## Output

For each finding:
- **Location** — file:line
- **Expression** — the conversion or comparison
- **Assumed unit** — what the code treats the value as
- **Actual unit** — what WCL actually produces (confirmed from cached data or API reference)
- **Magnitude of error** — how wrong the result is (100×, 1000×, sign flip, etc.)
- **Failure mode** — what the report silently shows (uptime of 0.05% instead of 5%, etc.)
