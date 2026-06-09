---
name: name-mismatch
description: Audit for hardcoded string lookup keys that don't match what the external data (WCL API / cached JSON) actually produces — causing silent 0 / None / missing row instead of an error. The narrowed, precise form of stale-assumptions. Invoked as `/name-mismatch`.
allowed-tools: Read, Grep, Glob, Bash
---

# name-mismatch

Find every hardcoded string used as a lookup key against WCL data, then verify the string actually appears in the cached JSON. Binary result per finding — the string is there or it isn't.

## What to scan

- Exact equality checks: `x.get("name") == "..."`, `x["name"] == "..."`
- Set/list membership: `name in {"Foo", "Bar"}`, `name in ["Foo", "Bar"]`
- Dict key lookups used against WCL-sourced data: `d["abilityName"]`, `d.get("spellName")`
- Curated name lists: `KEY_BUFFS`, `KEY_DEBUFFS`, `PROVIDER_CHECKS`, any list of game spell/ability/class/spec names used to match against API responses

Focus on: `build_deepdive.py`, `fetch_report.py`, `fetch_worldbest.py`, and any other script that reads cached data or WCL responses.

## How to verify

For each hardcoded string found, search the cached data:

```bash
python -c "
import json, glob
name = 'THE_STRING'
for f in glob.glob('data/**/*.json', recursive=True):
    try:
        text = open(f).read()
        if name in text:
            print(f)
    except: pass
"
```

If the string appears nowhere in `data/` — it's a confirmed mismatch. Also check for semantically equivalent variants (different capitalisation, a "Greater " prefix, a parenthetical suffix, a different word order) that ARE present.

## Output

For each finding:
- **Location** — file:line
- **String assumed** — what the code looks for
- **String found** — what actually appears in the data (or "absent")
- **Failure mode** — what the code silently produces when the match fails (0%, missing row, etc.)

Group as: **Confirmed wrong** (verified absent from cache) / **Likely wrong** (variant present, exact string absent) / **Unverified** (not checkable from cache alone).
