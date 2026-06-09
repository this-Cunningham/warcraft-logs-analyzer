---
name: null-arithmetic
description: Audit for .get() / dict lookups returning None that are fed directly into arithmetic (multiply, divide, round, sum) without a null guard — silently producing None, 0, or NaN instead of flagging missing data. Invoked as `/null-arithmetic`.
allowed-tools: Read, Grep, Glob, Bash
---

# null-arithmetic

`x.get("totalUptime")` returns `None` when the field is absent. If that None flows directly into `round(None / dur)` or `None * 100`, Python raises a TypeError — but if there's an `or 0` somewhere upstream that masks it, or if the None propagates through an `if not x` check that isn't tight enough, the result is silently 0 or None in the output. The report shows a blank or a zero; nobody notices.

## What to scan

Patterns where a value from external data (WCL API response or cached JSON) is used in arithmetic without an explicit None/absent guard:

- `x.get("field") * something` — no guard between get and multiply
- `round(x.get("field") / y)` — division with potentially-None numerator
- `sum(x.get("field") for x in list)` — sum over fields that may be absent
- `float(x.get("field"))` — float() of None raises TypeError; with a prior `or 0` it silently zeroes
- `(x.get("a") or 0) / (x.get("b") or 0)` — the denominator `or 0` masks a missing field but also creates a divide-by-zero that returns 0 without warning

Also look for None propagating through conditional chains where the guard is too loose:
- `if x:` treats `0` as falsy — a legitimate 0 value gets treated as absent
- `if x is not None:` is the correct guard; `if x:` is not

Focus on: `build_deepdive.py` — the builder does most of the arithmetic on WCL data.

## How to verify

For each pattern found, check the cached data to confirm whether the field can actually be absent:

```bash
python -c "
import json, glob
field = 'totalUptime'
missing = 0
present = 0
for f in glob.glob('data/**/*.json', recursive=True):
    try:
        text = open(f).read()
        d = json.loads(text)
        # spot check: search for aura entries missing the field
    except: pass
"
```

More practically: read the function, trace where the value comes from, and ask — can WCL ever omit this field? If the answer is "yes, when the aura was never applied" or "yes, when the fight was too short", it's a real risk.

## Output

For each finding:
- **Location** — file:line
- **Expression** — the arithmetic expression
- **Field at risk** — which `.get()` can return None
- **Guard present?** — what guard (if any) exists and whether it's correct
- **Failure mode** — what the code silently produces (0, None, wrong value)
- **Can field be absent?** — confirmed yes/no/unknown from cached data
