# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: Optimize tab — form/role-aware rotation benchmarking

> The Optimize tab compares each raider's cast mix to a world-best player of their
> spec, but a hybrid who played the spec in a *different form/role* on the benchmark
> boss reads a huge, meaningless gap — e.g. a Feral who bear-tanked Al'ar gets
> compared to a cat-DPS world best, so the "rotation gap" is really just bear-vs-cat.
> The comparison is only honest when our raider played the same role/form as the
> benchmark. Detect the form/role the player actually used (their casts already
> reveal it — bear abilities vs cat) and either skip the comparison, benchmark them
> on a boss where they played the DPS form, or match the benchmark to their form.

A data-integrity fix, not a feature: per the soul, an apparent gap that's really a
role mismatch is *falsely precise* — it reads as "your rotation is 55% off" when the
player simply wasn't doing that rotation that fight. Right now it's covered only by
the "descriptive, not scored" framing; the sharper move is to make the comparison
like-for-like (or drop it) so every gap the tab shows is a real rotational one.
Inherited from the same blind spot in the existing Rotation — Ability Mix view.

## TODO: In-Combat matrix — mana potion name coverage + WCL logging gap

> i used a bunch of mana potions in this raid (madslippery) and i am not seeing it
> in Per-Player Consumables — In Combat

Two separate issues uncovered by investigation:

1. **Code bug — `"Replenish Mana"` not matched.** The code only recognises
   `"Restore Mana"` as a mana potion cast (`MANA_POTION_NAMES`). But at least one
   player on this raid (Byrdman) had their Super Mana Potions log as
   `"Replenish Mana"` instead — a different cast name WCL uses for some mana
   potion variants. Fix: add `"Replenish Mana"` to `MANA_POTION_NAMES` in
   `build_deepdive.py`. May be worth checking what other variants exist (Super
   Mana Potion, Fel Mana Potion, Major Mana Potion all could differ).

2. **WCL data gap — madslippery's pots never logged.** Madslippery (Holy Priest,
   sourceID 23) has zero mana potion events of any kind in the Casts table, buff
   events, or resource events across all 7 boss kills — WCL simply didn't record
   the item usage for this player. The In-Combat matrix correctly shows nothing
   because there's nothing to show; the gap is upstream, not in our code. Worth a
   note in the UI ("missing doesn't always mean didn't use — WCL occasionally
   misses instant-item casts") but not a code fix.

## TODO: "What's Killing Us" hint should state it's kill-pull deaths only

> Is the "What's Killing Us" section counting deaths from fights we kill, or wipes too?

Confirmed in code: the Deaths table is fetched with the **kill-fight IDs only**
(`fights(killType:Kills)` → `fightIDs` → `table(dataType:Deaths, fightIDs:$f)`).
Deaths on wipe pulls are intentionally excluded — they'd swamp the list with
progression noise. This is the right call, but the current hint text doesn't say it,
which leaves a leader wondering why their wipe-pull deaths don't appear. Fix: append
"kill pulls only — wipe deaths excluded" (or equivalent) to the hint so the scope
is honest at a glance. Per the soul: *never falsely precise* — scoped data must be
labeled as exactly what it is.

## TODO: Roster role should follow the majority spec, not first-seen

> In the Prep tab's per-player preparation audit, Papparadeli is labelled "healer"
> but he only healed 1 boss fight in the raid — he played a different role for the
> majority of bosses. Label players by whatever spec/role was the majority of the
> boss fights they played, not a one-off.

Confirmed bug: `get_roster` (build_deepdive.py) already sets **spec** to the
player's primary (most-frequent) via `primary_spec_map`, but sets **role** with
"first-seen role wins" (`"role": p["role"]` from the first encounter iterated). So
a player who healed the first-iterated boss but DPS'd the rest reads as "healer" —
spec and role disagree. Fix: derive role from the majority too (a `primary_role_map`,
or take the role implied by the primary spec), so role is consistent with spec and
order-independent. Per the soul, this is a **data-integrity / honesty** fix — a
mislabeled role makes the prep audit (and any role-split table) quietly wrong, and a
leader can't trust "is this healer under-enchanted?" if the player isn't really a
healer. Note: the roster role feeds more than the enchant audit (per-player
consumables labels, healer/DPS table splits), so the fix lands in one place but
ripples usefully across the report.

---

_Last pass shipped: removed the shaded edge-fade on scrolling
tables, clarified the "Total Boss Kill Time" label (+ verified Clear Efficiency is
scoped to shared bosses), converted the remaining five sections (Buff & Debuff
Coverage Gaps, Early Aggro — Threat Pulls, Add Control — Kill Speed, What's Killing
Us on Trash, Melee deaths — by mob) to mirrored-bar layout with the delta centered
and context columns held on the right, fixed the per-spec timeline tab-title font,
tightened the beefiest table/section descriptions, and dropped the benchmark guild
name truncation to 8 chars._
