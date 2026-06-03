# Pipeline — running queries & building reports by hand

The headline flow is one command (`compare_raids.py`, see `SKILL.md`). Everything
here is for when you need to run a stage individually, answer an ad-hoc data
question the report doesn't cover, or build a single-raid report.

All scripts are **Python 3 (standard library only — nothing to `pip install`)**, so
they run on macOS' system `python3` and on Windows (use `python` if `python3` isn't
on PATH). Run them **from the repo root**.

## Running queries ad-hoc

- **From a file:**
  ```bash
  python3 .claude/skills/warcraft-logs-analyzer/scripts/query.py \
    --query-file .claude/skills/warcraft-logs-analyzer/queries/report-summary.graphql \
    --variables '{"code":"aBcD1234"}'
  ```
- **Inline:**
  ```bash
  python3 .claude/skills/warcraft-logs-analyzer/scripts/query.py --query 'query { rateLimitData { limitPerHour pointsSpentThisHour } }'
  ```
  > **Windows/PowerShell gotcha:** PowerShell strips the inner `"` when passing
  > inline JSON to a native exe, so `--variables '{"code":"abc"}'` arrives as invalid
  > JSON. Backslash-escape the quotes: `--variables '{\"code\":\"abc\"}'`. (bash/zsh
  > on macOS need no escaping.) The `compare_raids.py` entry point takes plain URLs
  > and avoids this entirely.
- **From your own code (import the lib):**
  ```python
  import sys; sys.path.insert(0, ".claude/skills/warcraft-logs-analyzer/scripts")
  import lib
  data = lib.invoke_query(open(".../report-summary.graphql").read(), {"code": "aBcD1234"})
  ```

The token is fetched once and cached in `.wcl-token.json` (gitignored) until near
expiry. `lib.invoke_query` raises on GraphQL errors. `query.py` supports
`--out-file` to save the raw JSON.

## Ad-hoc analysis workflow

Only when you genuinely need to answer a data question the report doesn't cover:

1. Resolve the report **code** from the user's URL
   (`warcraftlogs.com/reports/aBcD1234` → `aBcD1234`).
2. Pull report summary (title, zone, fights, players) — `queries/report-summary.graphql`.
3. Pull the data the question needs (parses, damage/healing tables, deaths).
4. Reason over the raw JSON to answer the specific follow-up — not as a routine chat
   summary. (Routine output belongs in the report; see the "report is the
   deliverable" rule in `SKILL.md`.)

## Manual deep-dive build (running the stages individually)

`compare_raids.py` does all of this for you. Run the stages by hand only when
debugging or customizing.

1. Fetch everything for each report (kills, playerDetails, per-boss buffs/debuffs):
   ```bash
   python3 scripts/fetch_report.py --code OURS   --out-dir data/ours
   python3 scripts/fetch_report.py --code THEIRS --out-dir data/demo
   ```
   For the shared bosses, add `--full-encounters <id> <id> ...` to also pull the
   heavy output tables (dd/heal/dt/intr/disp/casts/threat/deaths). Trash is fetched
   on by default (or `--trash-only`). Also save each report's parses to
   `data/ours-parses.json` / `data/demo-parses.json`:
   ```bash
   python3 scripts/query.py --query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' --variables '{"code":"OURS"}'  --out-file data/ours-parses.json
   python3 scripts/query.py --query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' --variables '{"code":"THEIRS"}' --out-file data/demo-parses.json
   ```
   (Remember the healer-HPS merge — see the parse-metric caveat in `wcl-api.md`.
   `compare_raids.py` does this automatically via `merge_healer_hps()`.)
2. Build the tabbed report:
   ```bash
   python3 scripts/build_deepdive.py --ours-dir data/ours --theirs-dir data/demo \
     --ours-parses data/ours-parses.json --theirs-parses data/demo-parses.json \
     --ours-name "Our Raid" --theirs-name "Benchmark" --zone-name "SSC / TK" --out-file reports/deepdive.html
   ```

## Simple comparison build (parses only, no deep-dive)

`build_comparison.py` builds a lean parses-only comparison — intersects on
`encounterID`, computes duration/deaths/parse deltas. The `rankings` JSON already
carries per-player class/spec/role/rankPercent/amount + fight duration + deaths, so
no extra table calls are needed.

```bash
python3 scripts/build_comparison.py --ours-file data/ours-parses.json --theirs-file data/demo-parses.json \
  --ours-name "Our Raid" --theirs-name "Benchmark" --zone-name "SSC / TK" --out-file reports/comparison.html
```

## Encoding

Python handles this natively — the builders read with `utf-8-sig` (tolerates
BOM-prefixed JSON) and write the HTML as UTF-8 without a BOM. `json.dumps`
ascii-escapes non-ASCII (`·`, `−`, accented player names) into the `DATA` blob, so
they survive intact regardless of how the file is opened.

## Preview / screenshot

The report needs no server to open, but to screenshot it use the `report-preview`
config in `.claude/launch.json` (a stdlib Python static server,
`.claude/preview-server.py`) and the preview tools. Restart the server to bust the
browser cache after regenerating.

## Single-raid (non-comparison) report

The product supports a single report with no benchmark. Reuse the same template/JS
by emitting one "team" or extend the template — the data shape is documented inline
in `templates/report.html`.
