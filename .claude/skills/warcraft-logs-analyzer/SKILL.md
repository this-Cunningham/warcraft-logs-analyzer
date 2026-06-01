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

Analyze Warcraft Logs reports and produce sleek HTML reports. All API access
uses the **client-credentials flow** against the **public** API
(`https://www.warcraftlogs.com/api/v2/client`) — public reports only, no user
auth needed.

## Setup (once)

1. Credentials live in `.env` at the repo root (gitignored). If it's missing,
   copy `.env.example` to `.env` and have the user fill in `WCL_CLIENT_ID` /
   `WCL_CLIENT_SECRET`. Create a client at
   https://www.warcraftlogs.com/api/clients (NOT a "Public Client").
2. Confirm connectivity and dump the schema (writes `schema.json` to repo root):
   ```powershell
   .\.claude\skills\warcraft-logs-analyzer\scripts\introspect.ps1
   ```
   Browse `schema.json` to confirm exact field names before writing a new query.

## Running queries

All scripts are PowerShell (no Node/Python needed on this machine).

- **Ad-hoc / from a file:**
  ```powershell
  .\.claude\skills\warcraft-logs-analyzer\scripts\query.ps1 `
    -QueryFile .\.claude\skills\warcraft-logs-analyzer\queries\report-summary.graphql `
    -Variables '{"code":"aBcD1234"}'
  ```
- **Inline:**
  ```powershell
  .\.claude\skills\warcraft-logs-analyzer\scripts\query.ps1 -Query 'query { rateLimitData { limitPerHour pointsSpentThisHour } }'
  ```
- **From your own code (dot-source the lib):**
  ```powershell
  . .\.claude\skills\warcraft-logs-analyzer\scripts\lib.ps1
  $data = Invoke-WclQuery -Query (Get-Content -Raw .\...\report-summary.graphql) -Variables @{ code = 'aBcD1234' }
  ```

The token is fetched once and cached in `.wcl-token.json` (gitignored) until
near expiry. `Invoke-WclQuery` throws on GraphQL errors.

## Key concepts

- **Report code**: the ID in a report URL — `warcraftlogs.com/reports/aBcD1234`
  → code is `aBcD1234`. Most queries start from `reportData.report(code: ...)`.
- **Fights**: each pull/encounter in a report has a `fightID`. Filter table
  and event queries by `fightIDs`.
- **Rankings / parses**: per-player percentile rankings vs. the global pool —
  the backbone of "how good were we" and cross-guild comparison.
- **Tables**: `table(dataType: DamageDone|Healing|Deaths|...)` returns the
  aggregated breakdown you'd see on the site.
- **Rate limits**: the API is points-based per hour (`rateLimitData`). Batch
  fields into one query where possible rather than many small calls.

## Workflow for analyzing a raid

1. Resolve the report **code** from the user's URL.
2. Pull report summary (title, zone, fights, players) — see
   `queries/report-summary.graphql`.
3. Pull the data the question needs (parses, damage/healing tables, deaths).
4. Reason over the JSON to surface insights (low parses, avoidable deaths,
   downtime, comparison gaps).
5. Generate the HTML report (see below) into `reports/`.

## Workflow for comparing two raids

1. Pull both reports (yours + the comparison guild's) for the same encounter(s).
2. Align on encounter `encounterID` so you compare like-for-like fights.
3. Compute deltas: per-boss parse percentiles, fight duration, deaths, key
   ability uptime/usage, item-level-adjusted DPS where relevant.
4. Frame findings as actionable gaps ("Boss X: their melee uptime 94% vs your
   81%; your raid took 3 avoidable hits to <ability>").

## Generating the HTML report

`templates/report.html` is a single self-contained file — inline CSS + JS, dark
modern theme, no CDN (works offline). Its inline JS reads a `const DATA = ...`
blob; the build script injects it by replacing the literal `/*__DATA__*/null`.

**Comparison report (two reports, shared bosses):**
1. Save each report's parses to a file (see `queries/` + `query.ps1 -OutFile`):
   ```powershell
   .\scripts\query.ps1 -Query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' -Variables '{"code":"OURS"}'  -OutFile .\data\ours-parses.json
   .\scripts\query.ps1 -Query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' -Variables '{"code":"THEIRS"}' -OutFile .\data\demo-parses.json
   ```
2. Build the HTML (intersects on `encounterID`, computes duration/deaths/parse deltas):
   ```powershell
   .\scripts\build-comparison.ps1 -OursFile .\data\ours-parses.json -TheirsFile .\data\demo-parses.json `
     -OursName "Our Raid" -TheirsName "Benchmark" -ZoneName "SSC / TK" -OutFile .\reports\comparison.html
   ```
   Output lands in `reports/` (gitignored). It's self-contained — the user just
   opens the file. The `rankings` JSON already carries per-player class/spec/role/
   rankPercent/amount + fight duration + deaths, so no extra table calls are needed
   for the comparison view.

**Encoding (PS 5.1 gotcha):** read templates with
`[IO.File]::ReadAllText($p,[Text.Encoding]::UTF8)` and write output with
`[IO.File]::WriteAllText($p,$html,(New-Object Text.UTF8Encoding $false))`.
`Get-Content`/`Set-Content -Encoding utf8` mangle `·`, `−`, and accented names.

**Preview:** the report needs no server, but to screenshot it use the
`report-preview` config in `.claude/launch.json` (a PowerShell static server,
`.claude/preview-server.ps1`) and the preview tools. Restart the server to bust
the browser cache after regenerating.

**Deep-dive (tabbed) report — Overview + Dive Deeper:**

**Easiest path — one deterministic command (no manual params, no LLM in the loop):**
```powershell
.\scripts\Compare-Raids.ps1 -OursUrl "https://.../reports/OURS" -TheirsUrl "https://.../reports/THEIRS"
```
`Compare-Raids.ps1` resolves report codes from the URLs, intersects encounter IDs to
find the shared bosses automatically, fetches parses + heavy tables for those bosses,
builds the report, and opens it. Titles/zone default to the reports' own metadata
(override with `-OursName`/`-TheirsName`, set `-OutFile`, or `-NoOpen`). Re-running with
the same inputs produces the same report — generation is pure PowerShell + the static
template, with no model in the path.

**Manual path (if you need to run the stages individually):**
1. Fetch everything for each report (kills, playerDetails, per-boss buffs/debuffs):
   ```powershell
   .\scripts\fetch-report.ps1 -Code OURS   -OutDir .\data\ours
   .\scripts\fetch-report.ps1 -Code THEIRS -OutDir .\data\demo
   ```
   Also save each report's parses (see above) to `.\data\ours-parses.json` / `demo-parses.json`.
2. Build the tabbed report:
   ```powershell
   .\scripts\build-deepdive.ps1 -OursDir .\data\ours -TheirsDir .\data\demo `
     -OursParses .\data\ours-parses.json -TheirsParses .\data\demo-parses.json `
     -OursName "Our Raid" -TheirsName "Benchmark" -ZoneName "SSC / TK" -OutFile .\reports\deepdive.html
   ```
   The report has four top-level tabs: **Overview | Composition | Enchants | Bosses**.
   - **Composition**: Raid Composition & buff-provider gap analysis (class/spec → raid buff
     it brings; provider table is in build-deepdive.ps1).
   - **Enchants**: Enchants & Gems audit (per-player missing enchants from
     `combatantInfo.gear.permanentEnchant`). Restricted to the **shared-boss roster** (same
     player set as Composition) — `Audit-Report` takes the roster names and filters
     playerDetails, which is otherwise fetched across all kills.
   - **Enchants** also carries raid **avg item level** (from `fights.averageItemLevel` over the
     shared bosses) alongside the gem/enchant stats.
   - **Bosses**: Clear Efficiency; Output Quality (avg DPS activity from
     `dd.activeTime`/duration, healer overheal from `heal.overheal`, damage taken ex-tanks
     from `dt`, interrupt/dispel counts) — the damage-taken metric has an in-report
     **Per second / Overall** toggle (client-side; the DATA blob carries raw totals +
     per-boss durations, so both modes render without a rebuild, and the toggle also switches
     the per-boss damage breakdowns); and Per-Boss Execution — each boss is a card with an
     output strip plus six sub-tabs:
     - **Buff Uptime** — boss debuffs + raid buffs, laid out value←bar—name—bar→value with a
       delta, sorted by delta (most-improvable / biggest deficit first).
     - **Damage Taken** — top damage-taken sources (honors the per-sec/overall toggle).
     - **Deaths** — who died, their spec (parsed from the death `icon`, e.g. `Hunter-Survival`),
       the killing blow, and when (sec into fight). "Clean kill" when nobody died.
     - **Interrupts** — abilities interrupted + interrupters by spec, plus a **Casts That Went
       Off Un-kicked** section (kicked / went-off per ability). Un-kicked = `intr` entries'
       `missedCasts[]` filtered to hostile casters (`type` NPC/Boss) so friendly-ability noise
       is excluded.
     - **Dispels** — which enemy auras each raid removed, with counts (`disp` entries'
       `details[].total`).
     - **Phases** — per-phase duration + share of kill with a delta, from `fight.phaseTransitions`
       (single-phase fights show a graceful note). TBC has no phase *names*, so phases are
       numbered.

   Heavy tables (dd/heal/dt/intr/disp/**deaths**) are fetched only for the shared bosses via
   `fetch-report.ps1 -FullEncounters <ids>` since the responses are large. `phaseTransitions`
   ride along on the cheap `fights` query (all kills), so they're always present.

**TBC Classic data caveats (verified):**
- `potionUse`/`healthstoneUse` are NOT tracked (always 0) — don't surface them.
- Enchant audit checks core slots only (Head, Shoulder, Chest, Legs, Feet, Wrist,
  Hands, Back, Weapon). Rings (enchanter-only) and offhand/ranged are excluded to
  avoid false "missing" flags. Empty slots (`id:0`) are skipped.
- Gem *socket count* isn't exposed, so we report gems-used totals, not "missing gems".
- `table(Buffs/Debuffs)` uptime is **raid-aggregate**, not per-player.
- Clear-efficiency uses kills only, so "Out of Boss" time includes trash + wipes.
- Composition (from parses) and the Enchants audit (from playerDetails) now share the
  same **shared-boss roster**: build-deepdive passes the composition roster names into
  `Audit-Report`, which skips any playerDetails entry not on a shared boss. The two player
  counts line up. (The raw playerDetails JSON still spans all kills; the audit just ignores
  off-shared-boss players.)
- `Interrupts` table is often empty for fights with no interruptible casts (e.g. Vashj
  P1) — `CountActions` returns 0 gracefully. Don't treat 0 as a bug.
- "Damage taken (ex-tanks)" is a proxy for avoidable damage, not a true avoidable-only
  figure (it includes some unavoidable raid damage). Top-sources list is the actionable part.

**Next-pass ideas (proven data pattern, not yet built):** DPS/healer cooldown usage
(`Casts` filtered to CD ability IDs — Combustion, Recklessness, Death Wish, trinkets,
Power Infusion, racials), per-class rotation / ability-mix comparison (`dd.abilities[]`
already fetched — compare a player to the benchmark's best same-spec player), death
timeline & cause (`Deaths` table timestamps + killing blow).

For a single-raid (non-comparison) report, reuse the same template/JS by
emitting one "team" or extend the template — the data shape is documented inline.

## Query cookbook

Reusable queries live in `queries/`:
- `report-summary.graphql` — metadata, fight list, roster.
- `fight-analysis.graphql` — multiple tables + parses for given `fightIDs` in one call.

Full introspected schema is in `schema.json` (repo root) — grep it before
adding a new query.

### Verified field/enum reference (WCL v2 public API)

- Entry point: `reportData.report(code: String!) { ... }`.
- `table`, `graph`, `rankings`, `playerDetails` all return **untyped JSON** —
  request them with no sub-selection; reason over the returned object.
- `report.table(dataType: TableDataType, fightIDs: [Int], killType: KillType, ...)`.
  Use **aliases** to pull several `dataType`s in one request (saves points).
- `report.rankings(compare: RankingCompareType, playerMetric: ReportRankingMetricType, fightIDs: [Int], encounterID: Int, ...)` → per-player percentile parses.
- `report.fights(killType: KillType, encounterID: Int, fightIDs: [Int], difficulty: Int)`.
- `report.masterData.actors(type: "Player") { id name type subType }` (subType = class for players).
- Cross-guild leaderboard: `worldData.encounter(id: Int!).characterRankings(metric: CharacterRankingMetricType, difficulty: Int, serverRegion:, serverSlug:, className:, specName:, ...)` → JSON.
- Find reports for a guild: `reportData.reports(guildName:, guildServerSlug:, guildServerRegion:) { data { code title } }`.

**Enums** — `TableDataType`: Summary, Buffs, Casts, DamageDone, DamageTaken,
Deaths, Debuffs, Dispels, Healing, Interrupts, Resources, Summons,
Survivability, Threat. `KillType`: Kills, Wipes, Encounters, Trash.
`RankingCompareType`: Rankings, Parses. `ReportRankingMetricType`: dps, bossdps,
hps, playerscore, playerspeed, default.

**Rate limit:** 3600 points/hour. Check anytime with
`query { rateLimitData { pointsSpentThisHour pointsResetIn } }`. Batch via
aliases; avoid many tiny calls.
