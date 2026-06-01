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
   ```bash
   python3 .claude/skills/warcraft-logs-analyzer/scripts/introspect.py
   ```
   Browse `schema.json` to confirm exact field names before writing a new query.

## Running queries

All scripts are **Python 3 (standard library only — nothing to `pip install`)**, so
they run on macOS' system `python3` and on Windows (use `python` if `python3`
isn't on PATH). Run them from the repo root.

- **Ad-hoc / from a file:**
  ```bash
  python3 .claude/skills/warcraft-logs-analyzer/scripts/query.py \
    --query-file .claude/skills/warcraft-logs-analyzer/queries/report-summary.graphql \
    --variables '{"code":"aBcD1234"}'
  ```
- **Inline:**
  ```bash
  python3 .claude/skills/warcraft-logs-analyzer/scripts/query.py --query 'query { rateLimitData { limitPerHour pointsSpentThisHour } }'
  ```
  > **Windows/PowerShell gotcha:** PowerShell strips the inner `"` when passing inline
  > JSON to a native exe, so `--variables '{"code":"abc"}'` arrives as invalid JSON.
  > Backslash-escape the quotes: `--variables '{\"code\":\"abc\"}'`. (bash/zsh on macOS
  > need no escaping.) The main `compare_raids.py` entry point takes plain URLs and
  > avoids this entirely.
- **From your own code (import the lib):**
  ```python
  import sys; sys.path.insert(0, ".claude/skills/warcraft-logs-analyzer/scripts")
  import lib
  data = lib.invoke_query(open(".../report-summary.graphql").read(), {"code": "aBcD1234"})
  ```

The token is fetched once and cached in `.wcl-token.json` (gitignored) until
near expiry. `lib.invoke_query` raises on GraphQL errors.

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
1. Save each report's parses to a file (see `queries/` + `query.py --out-file`):
   ```bash
   python3 scripts/query.py --query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' --variables '{"code":"OURS"}'  --out-file data/ours-parses.json
   python3 scripts/query.py --query 'query P($code:String!){reportData{report(code:$code){rankings(compare:Parses)}}}' --variables '{"code":"THEIRS"}' --out-file data/demo-parses.json
   ```
2. Build the HTML (intersects on `encounterID`, computes duration/deaths/parse deltas):
   ```bash
   python3 scripts/build_comparison.py --ours-file data/ours-parses.json --theirs-file data/demo-parses.json \
     --ours-name "Our Raid" --theirs-name "Benchmark" --zone-name "SSC / TK" --out-file reports/comparison.html
   ```
   Output lands in `reports/` (gitignored). It's self-contained — the user just
   opens the file. The `rankings` JSON already carries per-player class/spec/role/
   rankPercent/amount + fight duration + deaths, so no extra table calls are needed
   for the comparison view.

**Encoding:** Python handles this natively — the builders read with `utf-8-sig`
(tolerates BOM-prefixed JSON files) and write the HTML as UTF-8 without a BOM.
`json.dumps` ascii-escapes
non-ASCII (`·`, `−`, accented player names) into the `DATA` blob, so they survive
intact regardless of how the file is opened.

**Preview:** the report needs no server, but to screenshot it use the
`report-preview` config in `.claude/launch.json` (a stdlib Python static server,
`.claude/preview-server.py`) and the preview tools. Restart the server to bust
the browser cache after regenerating.

**Deep-dive (tabbed) report — Overview + Dive Deeper:**

**Easiest path — one deterministic command (no manual params, no LLM in the loop):**
```bash
python3 scripts/compare_raids.py --ours-url "https://.../reports/OURS" --theirs-url "https://.../reports/THEIRS"
```
`compare_raids.py` resolves report codes from the URLs, intersects encounter IDs to
find the shared bosses automatically, fetches parses + heavy tables for those bosses,
builds the report, and opens it. Titles/zone default to the reports' own metadata
(override with `--ours-name`/`--theirs-name`, set `--out-file`, or pass `--no-open`).
Re-running with the same inputs produces the same report — generation is pure Python +
the static template, with no model in the path.

**Manual path (if you need to run the stages individually):**
1. Fetch everything for each report (kills, playerDetails, per-boss buffs/debuffs):
   ```bash
   python3 scripts/fetch_report.py --code OURS   --out-dir data/ours
   python3 scripts/fetch_report.py --code THEIRS --out-dir data/demo
   ```
   For the shared bosses, add `--full-encounters <id> <id> ...` to also pull the heavy
   output tables. Also save each report's parses (see above) to `data/ours-parses.json` /
   `data/demo-parses.json`.
2. Build the tabbed report:
   ```bash
   python3 scripts/build_deepdive.py --ours-dir data/ours --theirs-dir data/demo \
     --ours-parses data/ours-parses.json --theirs-parses data/demo-parses.json \
     --ours-name "Our Raid" --theirs-name "Benchmark" --zone-name "SSC / TK" --out-file reports/deepdive.html
   ```
   The report has four top-level tabs: **Overview | Composition | Prep | Bosses**.
   - **Overview**: leads with a **"Biggest Gaps vs Benchmark" scorecard** (`biggest_gaps` in
     build_deepdive.py → `gapsScorecard()`) — a single ranking pass over every tracked dimension
     (parse, kill time, raid DPS, deaths, overheal, activity, avoidable dmg/s, flask, food, enchants,
     missing buff/debuff providers). Each candidate gets a hand-tuned severity in [0,1] and an
     actionable sentence; only dimensions where we trail are kept, top 7 render as severity-colored
     cards (high/med/low). Then the Raid Summary cards and per-boss cards — each boss card now also
     shows **Raid DPS** and **Raid HPS** comparison bars (per-boss total dmg/heal ÷ duration).
   - **Composition**: Raid Composition & buff-provider gap analysis (class/spec → raid buff
     it brings; provider table is `PROVIDER_CHECKS` in build_deepdive.py). Each player's
     spec is their **primary (most-frequent) spec across the shared bosses** (`primary_spec_map`),
     not whatever the first-iterated fight showed — so a Feral druid who bear-tanks one fight
     as "Guardian" still reads as Feral (and still counts as a Leader-of-the-Pack provider).
     This keeps the spec counts and the provider-gap status order-independent and consistent.
     Also carries **Damage Contribution by Class** (`class_dmg_share`) — each class's % share of
     total raid damage across the shared bosses, ours vs benchmark, as class-tinted mirrored bars.
   - **Prep**: leads with **Consumables Coverage** (`consumable_report` in build_deepdive.py),
     then the Enchants & Gems audit. Consumables come from the per-boss **Buffs** tables we already
     fetch — auras are bucketed by `_consumable_cat` into flask / food (Well Fed) / battle elixir /
     drums / combat potion, and `totalUses` is averaged across the shared bosses (≈ one application
     per player for flask/food, so it's a raid-aggregate coverage proxy, **not** per-player exact;
     it also can't tell flask-vs-elixir apart for the same player, so flask is the headline). Drums
     is shown as fight **uptime %** rather than a user count. Cards show ours/theirs/Δ.
     `ELIXIR_EXCLUDE` drops junk "…Elixir" names (Noggenfogger etc.).
   - **Consumables are classified by SPELL ID, not buff name.** WCL renames most consumable buffs to
     their *effect* — Flask of Supreme Power → "Supreme Power", Elixir of Major Shadow Power → "Major
     Shadow Power", Ironshield Potion → "Ironshield" — none containing "Flask"/"Elixir"/"Potion", so
     name-matching silently misses them (and same-named non-consumables — "Strength"/"Agility" scrolls,
     a +125 "Spell Power" proc — would be false positives). The id sets (`FLASK_IDS`, `ELIXIR_BATTLE_IDS`,
     `ELIXIR_GUARDIAN_IDS`, `POTION_IDS` in build_deepdive.py) are **mined from the report data** (every
     buff carries its `guid`; the benchmark — a top guild — carries the full consumable set) and the
     battle/guardian label verified once against Wowhead (WCL has no category field). A "Flask of …"/
     "Elixir of …" name fallback covers any id not yet listed. Extend the id sets when a new tier's
     data surfaces a consumable buff not yet mapped.
   - **Prep — Per-Player Consumables** (ours only): a **matrix** — one row per raider (sorted
     **worst-prepared first**), the shared bosses across the top, and under each boss five
     sub-columns **F · B · G · Fd · P** (flask / battle elixir / guardian elixir / food / combat
     potion). A leading **Prep** column shows consumed-bosses / bosses-played, so a red streak across
     a row is a chronic offender. "Consumed" = a **flask OR a battle + guardian elixir pair**
     (`_elixir_type` types each elixir by spell id; a lone elixir is *not* enough). Built by
     `per_player_consumables` (matrix shape: `bosses[]` + `players[].cells`).
     Cell rendering is **route-aware**: a cell is red-tinted (`cmiss`) only if it's a real gap — a
     flasked player's empty B/G cells render *faint* (the flask covers them), but a player with only a
     guardian elixir gets a **red** battle-elixir cell (the missing half of the pair). Legend:
     ✓=had it, red ✗=missing & needed, faint ✗=not needed via that route, ·=didn't attend that boss.
     **Data source matters:** per-player consumables come from the Buffs *table scoped by `sourceID`*
     (`_fetch_per_player_buffs` → `consumes-<enc>.json`), NOT events — flask/food/elixir are applied
     pre-pull and generate no in-fight events, and `combatantInfo.auras` is empty in TBC. Fetched only
     for the shared (`--full-encounters`) bosses.
   - **Prep — Enchants & Gems audit**: per-player missing enchants from
     `combatantInfo.gear.permanentEnchant`. Restricted to the **shared-boss roster** (same
     player set as Composition) — `audit_report` takes the roster names and filters
     playerDetails, which is otherwise fetched across all kills.
   - **Prep** also carries raid **avg item level** (from `fights.averageItemLevel` over the
     shared bosses) alongside the gem/enchant stats, plus **Item Level by Role** (`role_ilvl`) —
     average equipped ilvl split into dps / healer / tank (from the dd/heal/dt tables), so an
     under-geared role stands out instead of hiding inside the single raid-wide average.
   - **Bosses**: Clear Efficiency; **What's Killing Us** (`death_cause_compare` → `deathCausesView`)
     — killing-blow names aggregated across every shared boss into a ranked ours-vs-theirs table
     (worst-for-us first, each row listing the bosses it occurred on); Output Quality (avg DPS
     activity from `dd.activeTime`/duration, healer overheal from `heal.overheal`, damage taken
     ex-tanks from `dt`, interrupt/dispel counts, plus time-weighted **Raid DPS / Raid HPS** cards)
     — the damage-taken metric has an in-report **Per second / Overall** toggle (client-side; the
     DATA blob carries raw totals + per-boss durations, so both modes render without a rebuild, and
     the toggle also switches the per-boss damage breakdowns); and Per-Boss Execution — each boss is
     a card with an output strip plus seven sub-tabs:
     - **Buff Uptime** — boss debuffs + raid buffs, laid out value←bar—name—bar→value with a
       delta, sorted by delta (most-improvable / biggest deficit first).
     - **DPS by Spec** (`spec_gap` → `specDpsView`) — the DamageDone table bucketed by (class,
       primary spec) for DPS-role players, ranked by the **per-player DPS deficit** to the
       benchmark's same spec (avg DPS per player, so 3-mages-vs-2 stays fair; specs only one raid
       brought fall to the bottom as a comp note). Each row expands (`<details>`) to the individual
       players + their DPS on both sides.
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
   `fetch_report.py --full-encounters <ids>` since the responses are large. `phaseTransitions`
   ride along on the cheap `fights` query (all kills), so they're always present.

**TBC Classic data caveats (verified):**
- `playerDetails.combatantInfo.potionUse`/`healthstoneUse` are NOT tracked (always 0) — don't use
  that field. BUT consumables (flasks, food, elixirs, drums, **and combat potions**) DO appear as
  **auras in the `Buffs` table** with a `totalUses` count, which is how the Consumables Coverage
  panel surfaces them. Potion buff names ("Destruction", "Haste", etc.) are matched via a curated
  `POTION_NAMES` set and are approximate (a few names can come from non-potion sources).
- Enchant audit checks core slots only (Head, Shoulder, Chest, Legs, Feet, Wrist,
  Hands, Back, Weapon). Rings (enchanter-only) and offhand/ranged are excluded to
  avoid false "missing" flags. Empty slots (`id:0`) are skipped.
- Gem *socket count* isn't exposed, so we report gems-used totals, not "missing gems".
- `table(Buffs/Debuffs)` uptime is **raid-aggregate**, not per-player.
- Clear-efficiency uses kills only, so "Out of Boss" time includes trash + wipes.
- Composition (from parses) and the Enchants audit (from playerDetails) now share the
  same **shared-boss roster**: build_deepdive passes the composition roster names into
  `audit_report`, which skips any playerDetails entry not on a shared boss. The two player
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
