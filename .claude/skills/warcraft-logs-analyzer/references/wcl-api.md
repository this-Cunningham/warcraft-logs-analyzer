# WCL v2 public API reference

All access is the **client-credentials flow** against the **public** API
(`https://www.warcraftlogs.com/api/v2/client`) — public reports only, no user auth.
The full introspected schema is in `schema.json` (repo root) — grep it before
adding a new query.

## Rate limit

**3600 points/hour**, points-based. Check anytime:

```
query { rateLimitData { pointsSpentThisHour pointsResetIn } }
```

Batch fields into one query (use **aliases** to pull several `dataType`s at once)
rather than many small calls.

## Verified field / enum reference

- Entry point: `reportData.report(code: String!) { ... }`.
- `table`, `graph`, `rankings`, `playerDetails` all return **untyped JSON** —
  request them with no sub-selection; reason over the returned object.
- `report.table(dataType: TableDataType, fightIDs: [Int], killType: KillType, ...)`.
  Use **aliases** to pull several `dataType`s in one request (saves points).
- `report.rankings(compare: RankingCompareType, playerMetric: ReportRankingMetricType, fightIDs: [Int], encounterID: Int, ...)` → per-player percentile parses.
- `report.fights(killType: KillType, encounterID: Int, fightIDs: [Int], difficulty: Int)`.
- `report.masterData.actors(type: "Player") { id name type subType }` (subType = class for players).
- Cross-guild leaderboard: `worldData.encounter(id: Int!).characterRankings(metric: CharacterRankingMetricType, difficulty: Int, serverRegion:, serverSlug:, className:, specName:, ...)` → JSON. Each ranking carries `report{code fightID}`, `guild`, `server{name region}`, `amount`, and a raw `faction` int — so the ranked player's log (and their Casts table) is directly reachable. `className`/`specName` take the same spec strings the report data uses (`BeastMastery`, `Survival`, …) — verbatim, no spaces. Powers the Optimize tab (`fetch_worldbest.py`).
- **Faction encoding mismatch (verified live):** a guild's `GameFaction` is `{id:1 name:Alliance}` / `{id:2 name:Horde}` (via `report.guild.faction` or `guildData.guild(id).faction`), but a `characterRankings` entry's raw `faction` int is **0=Alliance, 1=Horde**. To filter rankings to your raid's faction: `entryFaction == guildFactionId - 1`.
- Find reports for a guild: `reportData.reports(guildName:, guildServerSlug:, guildServerRegion:) { data { code title } }`.

**Enums**
- `TableDataType`: Summary, Buffs, Casts, DamageDone, DamageTaken, Deaths, Debuffs,
  Dispels, Healing, Interrupts, Resources, Summons, Survivability, Threat.
- `KillType`: Kills, Wipes, Encounters, Trash.
- `RankingCompareType`: Rankings, Parses.
- `ReportRankingMetricType`: dps, bossdps, hps, playerscore, playerspeed, default.

## Query cookbook

Reusable queries live in `queries/`:
- `report-summary.graphql` — metadata, fight list, roster.
- `fight-analysis.graphql` — multiple tables + parses for given `fightIDs` in one call.

## TBC Classic data caveats (verified)

- **`rankings(compare:Parses)` defaults to the DPS metric for EVERY role** (verified:
  unset == `default` == `dps` all return identical values). So a healer's
  `rankPercent`/`amount` come back as a DPS parse of their ~0 incidental damage — a
  meaningless number (e.g. a Holy Priest reading "69" off 6 DPS) that also pollutes
  the Avg Raid Parse. **Fix:** `compare_raids.py` fetches a second
  `rankings(compare:Parses, playerMetric:hps)` and `merge_healer_hps()` overwrites
  each healer's parse+amount with the HPS values (matched by encounter id + name).
  dps/tanks stay on the DPS metric. The merged parses file is what `build_deepdive`
  reads. If you ever fetch parses by hand, pass `playerMetric:hps` for healers.
- `playerDetails.combatantInfo.potionUse`/`healthstoneUse` are NOT tracked (always
  0) — don't use that field. BUT consumables (flasks, food, elixirs, drums, **and
  combat throughput potions**) DO appear as **auras in the `Buffs` table** with a
  `totalUses` count (combat potions = Haste/Destruction/Ironshield, `POTION_IDS`).
- **In-combat INSTANT items leave NO buff aura — they log as CASTS (verified live).**
  A health potion, mana potion, and healthstone are instant, so they do **not**
  appear in the Buffs table. They DO show in the **Casts** table under their effect
  name: a mana potion casts **"Restore Mana"**, a healthstone **"Master
  Healthstone"** (rank names contain "Healthstone"), a health potion **"Restore
  Health"**. So the in-combat consumables matrix reads MP/HS/HP from Casts
  (`MANA_POTION_NAMES`/`HEALTH_POTION_NAMES`/`_is_healthstone`), per-player by cast
  name — never from buffs. (Healthstones are warlock-dependent — flag "no warlock"
  instead of marking the whole column a gap.)
- **Cooldowns log as BUFFS, not casts, in TBC (verified).** The marquee off-GCD DPS
  cooldowns (Death Wish, Recklessness, Bestial Wrath, Rapid Fire, Arcane Power, Icy
  Veins, …) generate **no cast events** — they appear only in the `Buffs` table with
  a `totalUses` (activation) count. So Cooldown & Trinket Usage reads per-player buff
  `uses` (`COOLDOWN_NAMES`, from `consumes-<enc>.json`). **On-use trinkets are the
  inverse:** their *use* logs as a cast under the item name, but the resulting buff is
  renamed to the effect ("Haste"), so trinkets (`TRINKET_NAMES`) are read from the
  `Casts` table. The two sources are disjoint — no double-count.
- **Wipe depth** uses `ReportFight.fightPercentage` (boss HP% remaining at the wipe)
  + `lastPhase`, ridden along on the `fights(killType:Encounters)` attempts query.
  Populated and meaningful (Kael'thas 21.6%, P5), but **phase-reset bosses (e.g.
  Al'ar) can report ~0% on a non-kill wipe**, so the report shows sub-1% as "<1%"
  rather than a falsely-precise "0.0%". `wipeCalledTime` is null (Companion-app only
  — dead). `lastPhase` is 0 on short/non-phased fights — only trust it where named
  phases exist.
- **Phase NAMES exist via `report.phases` (PhaseMetadata), even in TBC** — corrects
  the earlier "TBC has no phase names" note, which was only true of `phaseTransitions`
  (id+time). Only scripted multi-phase bosses carry them; joined to phase transitions
  by id (`phase_name_map`).
- Enchant audit checks core slots only (Head, Shoulder, Chest, Legs, Feet, Wrist,
  Hands, Back, Weapon). Rings (enchanter-only) and offhand/ranged are excluded to
  avoid false "missing" flags. Empty slots (`id:0`) are skipped.
- Gem *socket count* isn't exposed (only gems-used totals), so gem prep can't be
  audited reliably — intentionally not surfaced.
- `table(Buffs/Debuffs)` uptime is **raid-aggregate**, not per-player.
- Clear-efficiency uses kills only, so "Out of Boss" time includes trash + wipes.
- Composition (from parses) and the Enchants audit (from playerDetails) share the
  same **shared-boss roster**: build_deepdive passes the composition roster names
  into `audit_report`, which skips any playerDetails entry not on a shared boss.
- `Interrupts` table is often empty for fights with no interruptible casts (e.g.
  Vashj P1) — `int_compare`/`unkicked_compare` handle the empty table gracefully.
  Don't treat empty as a bug.
- "Damage taken (ex-tanks)" is a proxy for avoidable damage, not a true
  avoidable-only figure (it includes some unavoidable raid damage). The top-sources
  list is the actionable part.
- **Trash clear time and pull counts** are a *rough* cross-guild proxy — routes,
  skips, and chain-pulling all differ; **trash deaths** are the clean signal. Trash
  pull boundaries don't align across guilds, so the benchmark comparison is done at
  the night-total and mob-*type* level (which align) plus exact-roster Same-Pack
  matches — not per-pull.
- **Trash kill priority and CC are descriptive, not better/worse.** Kill order is
  pull-dependent and CC needs differ by strategy — both framed as "here's how you
  differ from the benchmark," never scored.
- **Per-actor positions are withheld on this auth path.** WCL records per-actor
  coordinates (website replay works; `boundingBox` is populated per fight), but the
  public client-credentials API withholds the per-actor stream — all events carry
  zero `x`/`y`. Confirmed dead-end (2026-06-01). The user-OAuth flow *might* expose
  it; spike only if positioning becomes a priority.
