---
name: filter-overreach
description: Audit for filter conditions on WCL data that silently exclude more players, bosses, or events than intended — tighter than the logic requires, dropping valid data with no warning. Invoked as `/filter-overreach`.
allowed-tools: Read, Grep, Glob, Bash
---

# filter-overreach

A filter that's too tight silently shrinks the dataset. `if role == "dps"` excludes healers and tanks from a calculation that should include everyone. `if spec not in ("Unknown", "")` is correct, but `if spec` would also exclude specs whose name is a falsy value (unlikely but worth checking). The report shows a result based on fewer players than it should, with no indication anything was dropped.

## What to scan

Filter conditions applied to WCL-sourced player, event, or fight lists:

- **Role filters**: `role == "dps"`, `role in ("dps", "healer")` — is this the intended set? Are tanks excluded intentionally?
- **Spec filters**: `if spec`, `if spec and spec != "Unknown"` — does this exclude any valid spec values?
- **Class filters**: hardcoded class lists — do they cover all classes present in the raid?
- **Fight/encounter filters**: `if enc in shared_ids` — what happens to bosses killed by one side but not the other?
- **Player filters**: `if name not in exclusion_set` — is the exclusion set current and correct?
- **Threshold filters**: `if value > N` — is N the right cutoff, or does it silently drop edge cases?

Also look for **implicit filters** — operations that only work on certain data shapes and silently skip rows that don't fit:

- `dict.get("field")` followed by `if result:` — skips rows where the field is 0 (a legitimate value)
- List comprehensions with conditions that are subtly broader or narrower than the comment says

Focus on: `build_deepdive.py` — roster processing, spec/role derivation, boss iteration, parse filtering.

## How to verify

For each filter found, check the cached data to confirm what it actually excludes:

```bash
python -c "
import json, glob
for f in glob.glob('data/**/player-details*.json', recursive=True):
    d = json.load(open(f))
    roles = set()
    for role, players in d.items():
        if isinstance(players, list):
            for p in players:
                if isinstance(p, dict):
                    roles.add(p.get('role', '?'))
    print(f, sorted(roles))
    break
"
```

Ask for each filter: **what valid data does this exclude?** If the answer is "nothing" — it's fine. If the answer is "tanks on healer-parse calculations" or "players with 0 deaths" — it may be a bug.

## Output

For each finding:
- **Location** — file:line
- **Filter condition** — the exact expression
- **Intended exclusion** — what it's supposed to exclude
- **Actual exclusion** — what it actually excludes (confirmed from cached data)
- **Overreach?** — yes/no — is it excluding more than intended?
- **Failure mode** — which players/events/rows are silently dropped, and what metric is wrong as a result
