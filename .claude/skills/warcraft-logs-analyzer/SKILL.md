---
name: warcraft-logs-analyzer
description: >-
  Query the Warcraft Logs v2 GraphQL API to analyze a raid's encounters and
  performance, compare one raid/report against another guild (e.g. a top
  world guild), and generate a modern self-contained HTML report. Use whenever
  the user shares a Warcraft Logs report URL or code, asks to dig into raid
  parses/damage/healing/deaths, compare their raid to another, or wants a raid
  performance report generated.
---

# Warcraft Logs Analyzer

Analyze Warcraft Logs reports and produce a self-contained HTML comparison report.
All API access uses the **client-credentials flow** against the **public** API
(`https://www.warcraftlogs.com/api/v2/client`) — public reports only, no user auth.

> **Product north star:** the report exists to surface the highest-leverage,
> actionable gaps vs a benchmark raid — not to dump data. Read
> [`PRODUCT_MANAGER_SOUL.md`](../../../PRODUCT_MANAGER_SOUL.md) (repo root) before
> deciding what a report should or shouldn't include.

## Setup (once)

1. Credentials live in `.env` at the repo root (gitignored). If missing, copy
   `.env.example` to `.env` and have the user fill in `WCL_CLIENT_ID` /
   `WCL_CLIENT_SECRET`. Create a client at
   https://www.warcraftlogs.com/api/clients (NOT a "Public Client").
2. Optional: confirm connectivity + dump the schema to `schema.json` at repo root:
   ```bash
   python3 .claude/skills/warcraft-logs-analyzer/scripts/introspect.py
   ```

All scripts are **Python 3, stdlib only** (nothing to `pip install`). Run from the
repo root. On Windows use `python` if `python3` isn't on PATH.

## The one command (headline mode)

To compare a raid against a benchmark guild — the main use case — the whole flow is
**one deterministic command, no model in the loop**:

```bash
python3 .claude/skills/warcraft-logs-analyzer/scripts/compare_raids.py \
  --ours-url "https://.../reports/OURS" --theirs-url "https://.../reports/THEIRS"
```

It resolves report codes from the URLs, intersects encounter IDs to find the shared
bosses, fetches parses + heavy tables, builds the report, and opens it. **Each side
is named after its GUILD** (from the parses data; yours shows the guild name,
theirs is framed `"Benchmark (Guildname)"`). Output lands in `reports/` (gitignored),
named after the guilds (`imminent-vs-squawk.html`, slugified). Re-running the same
inputs produces the same report.

Flags: `--ours-name` / `--theirs-name` (override guild names), `--zone-name`,
`--out-file`, `--no-open`.

## The report IS the deliverable — don't analyze in chat

When the user shares report URL(s), your job is to **generate the report and
open/serve it**, then stop — not to summarize findings in chat. The insight lives in
the report (the Biggest Gaps scorecard, the per-boss tabs); re-stating it in a
bullet list is redundant and implicitly frames the chat as the deliverable. The
normal flow is just: run `compare_raids.py`, confirm it opened, report that it's
ready. **Analysis on demand only** — if the user then asks a specific follow-up,
answer it; otherwise the report speaks for itself.

## Key concepts

- **Report code**: the ID in a report URL — `warcraftlogs.com/reports/aBcD1234` →
  `aBcD1234`. Most queries start from `reportData.report(code: ...)`.
- **Fights**: each pull/encounter has a `fightID`. Filter table/event queries by it.
- **Rankings / parses**: per-player percentile rankings vs the global pool — the
  backbone of "how good were we" and cross-guild comparison.
- **Tables**: `table(dataType: DamageDone|Healing|Deaths|...)` returns the
  aggregated breakdown you'd see on the site.
- **Rate limits**: points-based, **3600/hour**. Batch fields into one query (use
  aliases) rather than many small calls.

## Going deeper (load on demand)

The detail lives in `references/` — read the relevant one when the task calls for it:

- **Modifying or understanding a report view** (what every tab/metric is, how it's
  computed, why it exists, the function names): [`references/report-anatomy.md`](references/report-anatomy.md).
- **Writing a new query / API gotchas** (field & enum reference, query cookbook, and
  the verified TBC Classic data caveats — parse-metric, consumables-as-buffs,
  cooldowns-as-buffs, wipe depth, etc.): [`references/wcl-api.md`](references/wcl-api.md).
- **Running the pipeline by hand** (ad-hoc queries, manual fetch→build stages,
  encoding, preview server, single-raid reports): [`references/pipeline.md`](references/pipeline.md).

Roadmap and product backlog: [`TODO.md`](../../../TODO.md) and
[`BACKLOG.md`](../../../BACKLOG.md) at the repo root.
