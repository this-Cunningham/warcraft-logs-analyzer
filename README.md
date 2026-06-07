# warcraft-logs-analyzer

Query the Warcraft Logs v2 API and generate a self-contained, offline HTML
**deep-dive comparison report** that benchmarks one raid against another — a better
guild or your own past raid. Eight tabs (Overview, Composition, Prep, Execution,
Bosses, Wipes, Optimize, Trash) turn raw parses, damage/healing/deaths, cooldowns,
buff/debuff uptime, rotations, and per-actor positioning into the few things a raid
leader can actually act on.

## Quick start

```
python3 .claude/skills/warcraft-logs-analyzer/scripts/compare_raids.py \
  --ours-url   https://www.warcraftlogs.com/reports/<OURS> \
  --theirs-url https://www.warcraftlogs.com/reports/<THEIRS>
```

Needs `WCL_CLIENT_ID` / `WCL_CLIENT_SECRET` (a public WCL API client; see
`.env.example`). Python 3, standard library only — nothing to `pip install`. The
report is the deliverable; it opens in any browser with no server or network.

See `.claude/skills/warcraft-logs-analyzer/SKILL.md` and `references/` for the
pipeline, the report anatomy, and the WCL API notes.
