---
name: scale-confusion
description: Audit for 0–100 percentage values treated as 0–1 fractions (or vice versa), producing results that are silently off by 100×. Invoked as `/scale-confusion`.
allowed-tools: Read, Grep, Glob, Bash
---

# scale-confusion

WCL parse percentiles are 0–100 integers. Uptime computed from `totalUptime / totalTime` is a 0–1 fraction. If code multiplies a 0–1 fraction by 100 to get a percentage but the input was already 0–100, the result is 0–10000. If code compares a 0–100 parse against a 0–1 threshold (e.g. `if parse > 0.5`), every parse passes. No error — just a number that's off by exactly 100×.

## What to scan

- Expressions that multiply or divide by `100` on values derived from WCL — confirm the input scale before the operation
- Comparisons like `if value > 0.5` or `if value < 1` on values that might be 0–100 integers
- Comparisons like `if value > 50` on values that might be 0–1 fractions
- `round(x * 100)` — is `x` already a percentage (making the result 0–10000)?
- `x / 100` — is `x` already a fraction (making the result 0–0.01)?
- Any place parse percentile values flow into arithmetic: parses from WCL rankings are 0–100

Known scales in this codebase:
- **Parse percentiles** (`rankPercent`, parse fields from rankings queries) — **0–100**
- **`totalUptime / totalTime`** — **0–1 fraction** (multiply by 100 to get %)
- **`uptime_pct()`** return value — **0–100** (already multiplied inside the function)
- **HP percent** in position events — **0–100**

## How to verify

Spot-check actual values from cached data against what the code assumes:

```bash
python -c "
import json, glob
for f in glob.glob('data/**/parses*.json', recursive=True):
    d = json.load(open(f))
    # find first parse percentile value in the data
    text = json.dumps(d)
    import re
    # look for rankPercent or similar
    matches = re.findall(r'\"rankPercent\"\s*:\s*([0-9.]+)', text)
    if matches:
        print(f, 'rankPercent samples:', matches[:5])
    break
"
```

If `rankPercent` values are 75.3, 82.1, 91.0 — they're 0–100. If they're 0.753, 0.821 — they're 0–1.

## Output

For each finding:
- **Location** — file:line
- **Expression** — the multiplication/division/comparison
- **Assumed scale** — what the code treats the value as
- **Actual scale** — what WCL produces (confirmed from cached data)
- **Error magnitude** — off by 100×, off by 0.01×, always-true/always-false comparison
- **Failure mode** — what the report silently shows (parse of 7500%, threshold that always passes, etc.)
