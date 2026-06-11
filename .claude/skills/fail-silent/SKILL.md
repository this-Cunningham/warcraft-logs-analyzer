---
name: fail-silent
description: Full fail-silent bug sweep — runs all 8 focused sub-audits in sequence and produces a unified findings list. Each sub-audit targets a different class of bug that produces a wrong result with no error. Use when you want broad coverage across all fail-silent classes at once. Invoked as `/fail-silent`.
allowed-tools: Read, Grep, Glob, Bash
---

# fail-silent

A **fail-silent bug** produces a wrong result without raising an error — a zero, a missing row, a phantom entry, an inflated number — and the system keeps running. This skill runs all 8 focused sub-audits in sequence and reports findings unified by severity.

## The 8 sub-audits (run in order)

Run each of these fully before moving to the next. Carry all findings forward into the final summary.

### 1. `/name-mismatch`
Hardcoded string lookup keys that don't match what WCL actually produces.
→ Find: exact string equality checks and curated name lists against WCL data. Verify against `data/` cache.

### 2. `/first-match-bias`
`next()` / `[0]` taking the first match when multiple candidates exist and first isn't correct.
→ Find: `next((x for x in <wcl_list> if ...), None)` patterns. Check cached data for multiple matches.

### 3. `/null-arithmetic`
`.get()` returning None fed into arithmetic without a null guard.
→ Find: `x.get("field") * y`, `round(x.get("field") / y)` without an intervening `if x is not None`.

### 4. `/unit-mismatch`
Wrong unit assumptions — ms vs seconds, centiradians vs radians, 0–1 vs 0–100.
→ Find: `/ 1000`, `* 1000`, `/ 100`, `* 100` on WCL values. Verify scale from cached data.

### 5. `/silent-overwrite`
Dict built from a list where duplicate keys silently clobber earlier entries.
→ Find: `{x["key"]: x for x in wcl_list}` and `d[x["key"]] = x` in loops. Check cached data for duplicates.

### 6. `/aggregation-direction`
Summing when max/union is correct, or maxing when sum is correct.
→ Find: `sum(x["totalUptime"] ...)`, `max(...)` on WCL-sourced lists. Verify semantic intent.

### 7. `/filter-overreach`
Filter conditions that silently exclude more players/events than intended.
→ Find: role/spec/class filters on player data. Confirm what each actually excludes from cached data.

### 8. `/scale-confusion`
0–100 percentages treated as 0–1 fractions or vice versa.
→ Find: `* 100` / `/ 100` / comparisons against 0–1 thresholds on parse or uptime values. Verify scale.

## Output format

After all 8 sub-audits complete, produce a unified report:

**Confirmed bugs** (verified wrong against cached data) — sorted by severity (how wrong the output is)
**Likely bugs** (fragile pattern, not directly verified)
**Clean** (checked, no issue found)

For each confirmed or likely finding, one line:
`[skill] file:line — what's wrong — failure mode`

End with counts: N confirmed, M likely across all 8 classes.

If a finding appears in multiple sub-audits (e.g. a name mismatch that's also a first-match-bias), report it once under the most specific audit.
