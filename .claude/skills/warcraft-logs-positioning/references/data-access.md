# Data access — pulling positions from `events`

All verified 2026-06-05 on TBC report `pkHqfrBbhQK9GP1a` (Void Reaver fight 17).

## The flag

`report.events(..., includeResources: true)` — **default is `false`**. With it off,
events carry no `x`/`y` (this single omission caused the earlier wrong "positions are
a dead-end" conclusion). With it on, every *resourced* event gains:

| field | meaning |
|---|---|
| `x`, `y` | world position (WCL units — not raw yards; see coordinate-system.md) |
| `facing` | heading (integer; unit unconfirmed) |
| `mapID` | the Blizzard UiMap id (e.g. 334 = Tempest Keep) |
| `hitPoints`/`maxHitPoints` | **NPCs absolute; players reported as a 0–100 %** |
| `resourceActor` | **which actor the above describe**: `1`=source, `2`=target |
| `classResources` | mana/energy — **garbled in TBC, do not trust** (`type` is not a clean power enum) |

## The attribution rule (critical)

Blizzard logs resources for **exactly one actor per event**:

- `cast` / melee swing → `resourceActor: 1` → coords are the **source** (caster).
- `damage` / `heal` → `resourceActor: 2` → coords are the **target**.

So for any event, the positioned actor is:

```python
aid = e["sourceID"] if e["resourceActor"] == 1 else e["targetID"]  # when resourceActor in (1,2)
```

Apply this uniformly across dataTypes and bucket `(aid, x, y)`.

## Reconstructing paths

- **A player's path** = their `Casts` (source) ∪ the `DamageTaken`/`Healing` events
  landing on them (target). Covers everyone; casters are denser in `Casts`, others in
  `DamageTaken`.
- **The boss's path** = `DamageDone` events *targeting* it (`targetID:<bossID>` →
  target → boss) ∪ the boss's own `Casts` (source). `DamageDone` to the boss is dense
  (whole raid hitting it), so it's the cleanest boss anchor.

## Coverage & gaps

Positions are sampled **per resourced event**, not on a fixed clock — dense for active
actors, sparse during downtime. **Miss/dodge events (`hitType 10`, `amount 0`) carry no
resources** (skip them: guard `if "x" not in e`).

## Pagination

`events` returns `{data, nextPageTimestamp}`; pass `startTime:<nextPageTimestamp>` to
continue. `limit:10000` is accepted and usually covers a whole fight in one page for
`DamageTaken`/`Casts` (see api-cost.md).

```python
def page_events(code, fight, dataType, extra=""):  # extra e.g. ",targetID:164"
    q = ("query($c:String!,$s:Float){reportData{report(code:$c){"
         "events(fightIDs:[%d],dataType:%s,includeResources:true,startTime:$s,limit:10000%s)"
         "{data nextPageTimestamp}}}}" % (fight, dataType, extra))
    start = None
    while True:
        ev = invoke_query(q, {"c": code, "s": start})["reportData"]["report"]["events"]
        for e in ev["data"]:
            if "x" not in e:        # misses/dodges have no resources
                continue
            ra = e.get("resourceActor")
            aid = e.get("sourceID") if ra == 1 else e.get("targetID") if ra == 2 else None
            if aid is not None:
                yield aid, e["x"], e["y"], e.get("facing")
        if not ev.get("nextPageTimestamp"):
            break
        start = ev["nextPageTimestamp"]
```

## Resolving ids → names & roles

- `masterData.actors(type:"NPC")` / `(type:"Player")` → `{id, name, subType}`. **Actor
  ids are per-report** — the boss NPC id (Void Reaver = 164 in one report, 210 in
  another) must be looked up by name each time. Filter stale `zzOLD…` actors.
- `playerDetails(fightIDs:[N])` → nested at `data.playerDetails.{tanks, healers, dps}`.
  WCL splits only tank/healer/dps — **melee vs ranged is not given**; classify `dps` by
  class/spec (Warrior/Rogue = melee; Mage/Warlock/Hunter/Priest = ranged;
  Druid/Shaman/Paladin are spec-dependent).
