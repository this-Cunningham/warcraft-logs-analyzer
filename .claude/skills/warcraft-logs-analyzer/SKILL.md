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

> **Product north star:** the report exists to surface the highest-leverage,
> actionable gaps vs a benchmark raid — not to dump data. Read
> [`PRODUCT_MANAGER_SOUL.md`](../../../PRODUCT_MANAGER_SOUL.md) (repo root)
> before deciding what a report should or shouldn't include.

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
   The report has five top-level tabs: **Overview | Composition | Prep | Execution | Trash**.
   The structure is a funnel: **Overview** = where's the gap at a glance; **Composition** = roster
   makeup & buffs; **Prep** = did we show up ready; **Execution** = raid-wide gap analysis + per-boss
   drill-down; **Trash** = how the raid handles trash packs. Every section compares ours vs the
   benchmark with a delta — the report exists to point at the highest-leverage gaps, so weak/ambiguous
   metrics are deliberately omitted.
   - **Overview**: leads with a **"Biggest Gaps vs Benchmark" scorecard** (`biggest_gaps` in
     build_deepdive.py → `gapsScorecard()`) — a single ranking pass over every tracked dimension
     (parse, kill time, raid DPS, deaths, overheal, activity, avoidable dmg/s, flask, food, enchants,
     missing buff/debuff providers, **wipes**, **worst tier-wide spec DPS gap**, **worst buff/debuff
     uptime gap**). Each candidate gets a hand-tuned severity in [0,1] and an actionable sentence;
     only dimensions where we trail are kept, top 7 render as severity-colored cards (high/med/low).
     Then the Raid Summary cards (incl. **Total Wipes** when attempt data is present), then a
     **Boss-by-Boss** section with one **sub-tab per boss** (`mountOverview()` wires the
     `.btab[data-otab]` / `.bsub[data-otab]` toggle) — each boss panel shows kill time, **Raid DPS** /
     **Raid HPS** comparison bars (per-boss total dmg/heal ÷ duration), avg parse, deaths, **wipes
     before the kill** (shown only when either raid wiped), and both rosters side by side.
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
   - **Prep — Enchants & Weapon Oils audit**: per-player missing enchants from
     `combatantInfo.gear.permanentEnchant`, plus weapon-oil presence. Restricted to the
     **shared-boss roster** (same player set as Composition) — `audit_report` takes the roster names
     and filters playerDetails, which is otherwise fetched across all kills. (Gem *count* was dropped
     — without socket counts it can't flag empty sockets, so the raw number wasn't an actionable gap.)
   - **Prep** also carries raid **avg item level** (from `fights.averageItemLevel` over the
     shared bosses), plus **Item Level by Role** (`role_ilvl`) — average equipped ilvl split into
     dps / healer / tank (from the dd/heal/dt tables), so an under-geared role stands out instead of
     hiding inside the single raid-wide average.
   - **Execution** (raid-wide gaps first, then per-boss drill-down):
     - **What's Killing Us** (`death_cause_compare` → `deathCausesView`) — killing-blow names
       aggregated across every shared boss into a ranked ours-vs-theirs table (worst-for-us first,
       each row listing the bosses it occurred on). A recurring blow = a mechanic the raid keeps failing.
     - **Lowest-Hanging DPS — Spec Gaps** (`tier_spec_gap` → `tierSpecGapView`) — every DPS player's
       per-boss DPS pooled by (class, primary spec) across ALL shared bosses, ranked by the per-player
       deficit to the benchmark's same spec. Mirrored bars, biggest deficit (red) first; specs only one
       raid fielded are noted below. The comprehensive companion to the per-boss **DPS by Spec** sub-tab.
     - **Buff & Debuff Coverage Gaps** (`tier_uptime_gap` → `tierUptimeGapView`) — each aura's average
       uptime across the shared bosses, ours vs benchmark, listing only where we trail (biggest deficit
       first). The tier-wide companion to the per-boss Buff Uptime sub-tab.
     - **Output Quality** — time-weighted **Raid DPS / Raid HPS**, avg DPS activity (`dd.activeTime`/
       duration), damage taken ex-tanks (`dt`, with an in-report **Per second / Overall** toggle that
       also switches the per-boss damage breakdowns), healer overheal (`heal.overheal`). (The old raw
       "Dispels / Interrupts" count card was dropped — raw counts aren't a clean better/worse signal;
       the meaningful interrupt data lives in the per-boss kicked-vs-leaked view.)
     - **Clear Efficiency** — first-pull-to-last-kill wall-clock vs in-combat time (downtime = trash/wipes).
     - **Per-Boss Execution** — each boss is a card with an output strip (Raid DPS, activity, overheal,
       dmg taken/s) plus seven sub-tabs:
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
   - **Trash** (a whole-night view of how the raid handles trash — `build_trash()` →
     `renderTrash()`): WCL already splits trash into discrete pull **segments** (`fights(killType:Trash)`),
     each auto-named after its notable mob, with `enemyNPCs` (mob ids + counts) and `masterData.actors`
     resolving ids→names. The tab follows the **hybrid** comparison rule: benchmark-compare only what
     aligns across guilds (pull boundaries don't), keep per-pull detail single-raid (ours).
     **Scoped to the shared zone(s):** the two reports can cover different content (ours SSC+TK, theirs
     SSC+Gruul), so trash is restricted to the `gameZone`s present in **both** reports' trash
     (`_trash_zones` intersection → `_filter_to_zones` drops every off-zone fight's deaths/kills/CC),
     mirroring how the boss tab only compares shared encounters. Each trash fight carries `gameZone{id name}`
     (added to the fetch query); the shared zone name(s) show in the Glance hint (`trash.zones`). Older data
     folders without `gameZone` skip filtering gracefully. Five sections:
     - **Trash at a Glance** (`_trash_glance`) — total trash pulls, clear time, and deaths, ours vs
       benchmark. Clear time is a **rough proxy** (routes/skips differ between guilds — labeled as such);
       deaths are the clean signal.
     - **What's Killing Us on Trash** (`trash_death_causes`) — player trash deaths aggregated by killing
       blow, ranked worst-for-us, ours vs benchmark. Mob/ability killing blows align across guilds. Same
       idea as the boss "What's Killing Us." (Source: the **friendly Deaths table** over all trash fights
       — entries carry the killing-blow *name* and a `fight` id; events only carry the ability's game id.)
     - **Kill Order vs Benchmark** — two complementary lenses behind a **sub-tab toggle** (`.btab[data-ktab]`,
       wired by `mountTrash()`); **Same-Pack Matches is the default** (primary), **Pairwise Priority** is the
       secondary tab:
       - **Same-Pack Matches** (`trash_identical_packs` → `sameMatchesBody`/`killSeq`) — kill order **only for
         packs both raids pulled with the EXACT same roster** (same mob types AND counts; `_roster_sig` =
         sorted `(name, count)` tuples from `enemyNPCs`). The high-confidence "same pack" test: identical
         roster ⇒ genuinely the same pack, and a merged/chain-pull won't match a clean pack's roster, so
         messy pulls drop out automatically. `_typical_order` gives each side's typical order (median death
         time per type, averaged over that roster's pulls); shown as your sequence over the benchmark's, chips
         with arrows, **flagging any mob killed in a different slot**. ~6 multi-mob matches on the test pair
         (vs 8 names-only — requiring counts costs ~nothing, adds certainty). This is the trustworthy 1:1 view.
       - **Pairwise Priority** (`trash_pairwise_priority` + `trash_kill_priority` → `pairwiseBody`/`killLadder`)
         — the broad view that needs **no** pack identity: a ranking **ladder (SVG slopegraph)** of every mob's
         kill-priority pooled across all pulls (`trash_kill_priority`, your order vs benchmark, steep
         highlighted lines = big gaps), plus a **per-pair head-to-head table** (`trash_pairwise_priority`:
         "when A and B are both up, who dies first?", ranked by divergence, reversals flagged). Kill priority
         is fundamentally pairwise and a pair's order survives the merge/split that breaks pack identity, so it
         covers ~35 pairs / 94 obs vs the 6 exact packs. Descriptive, never scored.
       **Why both:** you can't reliably identify "the same pack" across guilds in general (WCL has no pack
       object, no position in TBC, segment names are a single notable mob). Same-Pack gives a few rock-solid
       1:1 comparisons; Pairwise gives broad coverage. (Earlier name-matching wrongly paired a 6-mob pull with
       a 2-mob pull; composition-by-type-set ignored counts.)
     - **Crowd Control on Trash** (`trash_cc_compare` + `trash_cc_by_mob`) — first a by-type summary
       (Polymorph, Banish, Sap, Shackle, Freezing Trap, Repentance, …) ours vs benchmark, then a **by-mob
       breakdown** (`trash_cc_by_mob` → one row per (mob, CC type): which mob gets CC'd, by which CC, how
       often, ours vs benchmark — grouped per mob, most-CC'd first). The by-mob view is the actionable one:
       e.g. benchmark Polymorphs the Greyheart Nether-Mage 73× and you 2×, pinpointing a caster you should
       be CCing. All **descriptive** (more CC isn't better — a raid that safely AoEs trash may need little).
       Count = landed `applydebuff` events. **CC is classified by NAME, not spell id** — unlike consumable
       *buffs* (which WCL renames to their effect, so those are id-classified), CC *debuffs* keep their real
       spell name, so a curated name allowlist (`report_common.HARD_CC_NAMES` / `cc_label()`) is reliable and
       rank-proof, and it correctly excludes look-alikes (Ice Trap/Explosive Trap are AoE slow/damage; Kidney
       Shot/Cheap Shot/Gouge/Bash/Hammer of Justice are rotational stuns, not a lockout).
     - **Pack-by-Pack** (`trash_packs`) — **single-raid (ours)** drill-down: every pack grouped by pull
       name, sorted worst-first by deaths, each expandable (`<details>`) to per-pull mobs, **exact kill-order
       timeline**, deaths (player + killing blow + time), and **which mob got CC'd, by whom**. No benchmark
       comparison here (that's the Matched Packs section) — pull boundaries don't align, so this is your
       raid's detail. The TODO's "per-pack panels + intra-pack kill order" ask. (Raid markers dropped — not needed.)

   Heavy tables (dd/heal/dt/intr/disp/**deaths**) are fetched only for the shared bosses via
   `fetch_report.py --full-encounters <ids>` since the responses are large. `phaseTransitions`
   ride along on the cheap `fights` query (all kills), so they're always present. **Wipe/attempt
   counts** come from one extra cheap query per report (`fights(killType:Encounters){encounterID kill}`
   → `attempts.json`); `attempt_map` in build_deepdive tallies kills vs wipes per boss (graceful — an
   older data folder without `attempts.json` just builds without the wipe views).

   **Trash data** is fetched **on by default** by `fetch_report.fetch()` (also runnable alone via
   `fetch_report.py --trash-only`) and is cheap (~7–9 calls): trash is split into pull segments, and
   all enemy deaths, player deaths, and CC events come back in **single paginated `events` calls**
   keyed by `fight` (not one call per pull). Writes `trash.json` (pulls + NPC/player name actors),
   `trash-deaths.json` (enemy kill-order events + friendly death-table entries), and `trash-cc.json`
   (hard-CC aura table + per-CC-id apply events). `build_trash()` is graceful — a data folder predating
   the Trash tab (no `trash.json`) just renders a "no trash data" note and the rest of the report builds.

**TBC Classic data caveats (verified):**
- `playerDetails.combatantInfo.potionUse`/`healthstoneUse` are NOT tracked (always 0) — don't use
  that field. BUT consumables (flasks, food, elixirs, drums, **and combat potions**) DO appear as
  **auras in the `Buffs` table** with a `totalUses` count, which is how the Consumables Coverage
  panel surfaces them. Potion buff names ("Destruction", "Haste", etc.) are matched via a curated
  `POTION_NAMES` set and are approximate (a few names can come from non-potion sources).
- Enchant audit checks core slots only (Head, Shoulder, Chest, Legs, Feet, Wrist,
  Hands, Back, Weapon). Rings (enchanter-only) and offhand/ranged are excluded to
  avoid false "missing" flags. Empty slots (`id:0`) are skipped.
- Gem *socket count* isn't exposed (only gems-used totals), so gem prep can't be audited reliably —
  it's intentionally not surfaced (a low count can't be distinguished from a low socket count).
- `table(Buffs/Debuffs)` uptime is **raid-aggregate**, not per-player.
- Clear-efficiency uses kills only, so "Out of Boss" time includes trash + wipes.
- Composition (from parses) and the Enchants audit (from playerDetails) now share the
  same **shared-boss roster**: build_deepdive passes the composition roster names into
  `audit_report`, which skips any playerDetails entry not on a shared boss. The two player
  counts line up. (The raw playerDetails JSON still spans all kills; the audit just ignores
  off-shared-boss players.)
- `Interrupts` table is often empty for fights with no interruptible casts (e.g. Vashj
  P1) — `int_compare`/`unkicked_compare` handle the empty table gracefully. Don't treat empty as a bug.
- "Damage taken (ex-tanks)" is a proxy for avoidable damage, not a true avoidable-only
  figure (it includes some unavoidable raid damage). Top-sources list is the actionable part.
- **Trash clear time and pull counts** are a *rough* cross-guild proxy — routes, skips, and how a
  guild chain-pulls all differ, so don't over-read a clear-time delta; **trash deaths** are the clean
  signal. **Trash pull boundaries don't align across guilds**, which is why the benchmark comparison
  is done at the night-total and mob-*type* level (which align) and the per-pull Pack-by-Pack view is
  single-raid (ours) only.
- **Trash kill priority and CC are descriptive, not better/worse.** Kill order is pull-dependent and
  CC needs differ by strategy (an AoE-zerg comp uses little CC) — both are framed as "here's how you
  differ from the benchmark," never scored, per the product soul.

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
