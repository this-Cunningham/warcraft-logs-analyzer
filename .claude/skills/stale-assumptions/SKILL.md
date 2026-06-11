---
name: stale-assumptions
description: Audit the codebase for stale assumptions about external data — places where hardcoded strings, field names, structure shapes, or enumeration values are matched against WCL API responses or cached JSON, and the assumption may be wrong or incomplete. The bug signature is always silent: a wrong result (zero, None, missing row, phantom entry) instead of an error. Use when the user asks to audit for data mismatches, silent lookup misses, or representation bugs. Invoked as `/stale-assumptions`.
allowed-tools: Read, Grep, Glob, Bash
---

# stale-assumptions

You're hunting **representation mismatches** — places where the code assumes something specific about the shape, naming, or values of external data (WCL API responses, cached JSON), and the assumption is wrong or incomplete. The defining feature of this class: the code fails **silently**, producing a wrong zero, a missing row, or a phantom entry instead of raising an error. Nobody notices because the result looks plausible.

## The two forms this takes

**1. Silent lookup miss** — a hardcoded string (or constant) used as a lookup key against external data, where the data uses a different name for the same concept. The lookup returns nothing; the code shows 0% or omits the row. Examples: `"Windfury"` in the code, `"Windfury Attack"` in WCL. `"Blessing of Kings"` in the code, `"Greater Blessing of Kings"` in WCL. No error — just wrong.

**2. Stale structural assumption** — the code assumes a field exists, a list is non-empty, a value falls in a certain range, or a data structure has a certain shape, based on how WCL *used to* behave or was *assumed* to behave. The field is absent, the list is empty, the value is out of range, and the code silently produces garbage.

Both forms share the same root: **a boundary between the code and external data where the two sides disagree, and the disagreement is undetected.**

## What to look for

Scan the builder (`scripts/build_deepdive.py`), the fetch pipeline (`scripts/fetch_report.py`, `scripts/fetch_worldbest.py`), and any other scripts that read cached data or WCL responses. Look for:

- **Exact string matches against data** — `x.get("name") == "..."`, `x["name"] in {...}`, list membership checks using hardcoded strings. For each, verify the string actually appears in the cached data.
- **Hardcoded field name accesses** — `.get("someField")`, `["someKey"]` where `someField` comes from a WCL API response. Check whether the field is actually present and what it's called in real data.
- **Hardcoded enumeration values** — assumed role names, class names, spec names, dataType enums, event type strings. Check against real data.
- **Assumed list structure** — code that indexes `[0]`, slices, or iterates assuming a list is non-empty or has a specific length, where the list comes from WCL.
- **Assumed numeric ranges** — values clamped, divided, or compared against constants that assume a specific scale or unit (e.g. milliseconds vs seconds, centiradians vs degrees).
- **Hardcoded name lists** — `KEY_BUFFS`, `KEY_DEBUFFS`, `PROVIDER_CHECKS`, and any other curated lists of game names used to match against WCL data. Are all entries verified against real cached data? Are there variants or aliases not covered?

## How to verify

The cached data is the ground truth. For each assumption:

1. Find the relevant cached files: `data/<code>/boss-<enc>.json`, `data/<code>/parses.json`, `data/<code>/player-details.json`, `data/<code>/worldbest.json`, etc.
2. Check whether the assumed string/field/value actually appears. A quick `python -c "import json; ..."` one-liner over the cached files is faster than reading the raw JSON.
3. If the assumption is unverifiable from cached data (field only appears in a live API response), flag it as **unverified** rather than confirmed.

## Output format

For each finding, report:

- **Location** — file + line number
- **Assumption** — what the code assumes
- **Reality** — what the data actually contains (or "unverified" if you can't confirm from cache)
- **Failure mode** — what goes wrong silently when the assumption is wrong (zero uptime, missing row, phantom entry, wrong value, etc.)
- **Fix shape** — one line on what the fix looks like (add alias, rename constant, add fallback, etc.)

Group findings by severity:
- **Confirmed wrong** — assumption verified false against cached data right now
- **Likely wrong** — assumption looks fragile (e.g. a single hardcoded string for a concept with known variants) but not directly verified
- **Unverified** — can't confirm from cache; needs a live API check

End with a count: N confirmed, M likely, K unverified. If nothing is found, say so clearly.

## Scope

Default scope is the full builder + fetch pipeline. If the user passes an argument (e.g. `/stale-assumptions buffs`), narrow to that area. The cached data under `data/` is fair game for verification — read it freely.
