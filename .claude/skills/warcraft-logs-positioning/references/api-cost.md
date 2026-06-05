# API point cost

Measured 2026-06-05 on `pkHqfrBbhQK9GP1a` by diffing
`rateLimitData { pointsSpentThisHour }` around real queries. Budget is **3600
points/hour**.

## The cost model

- **An `events` request costs ~2 points, flat** — independent of how many events
  come back (1,052 vs 7,095 both cost 2.0), of fight length, and of
  `includeResources` (**resources are free** — 2.0 either way). WCL prices by the
  **shape of the query**, not response bytes or rows. Cost = **request count**, not
  data volume.
- **Aliasing batches cheaply**: 3 event types in one request ≈ **4 pts**, not 6. So
  bundle the types you need per boss into one request.
- A `table` query also ≈ 2 pts (same order).

## What a positioning feature costs

Per-boss bundle (`DamageTaken` + `Casts`, resources on, ~1 page each):

| scope | points | % of 3600/hr |
|---|---|---|
| 1 boss | ~2.25 | 0.06% |
| 8-boss report, one side | ~18 | 0.5% |
| 8-boss × 2 (ours + benchmark) | ~36 | 1.0% |

**Points are not the constraint.** A 4-boss fetch pulled ~24k events; the real cost
is **payload + parse** (each event is a full resource object → a few MB to download
and bin), which matters for a pipeline that values speed/determinism.

## Pagination (the only point inflator)

Each page **beyond** `limit:10000` is another request ≈ +2 pts. The types used for
positions stay single-page even on long fights (Kael'thas: `Casts` 7,095,
`DamageTaken` 1,379). All-player `DamageDone` *would* paginate — but you don't need
it for positions (`Casts` already carries the boss's own position as source; use
`DamageDone, targetID:<boss>` if you want denser boss samples).

## Levers

- `filterExpression` (server-side, accepted on `events`/`graph`/`table`) and
  `targetID`/`sourceID` cut payload volume before it leaves WCL. They don't lower the
  ~2-pt request cost but shrink the bytes you parse.
- Prefer one aliased request per boss over many small ones.
