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

## TODO: Leaked Interrupts — exclude auto-attacks ("Shoot") from interruptible abilities

> Is "Shoot" in Interrupts Leaked really interruptible? What boss is it from?

Confirmed false positive with a clear root cause. **Shoot** (guid 37770, Coilfang
Ambushers on The Lurker Below) only counts as "interruptible" because the code's
proof-of-interruptibility (`spellsInterrupted ≥ 1`) was satisfied by a **Polymorph** —
`details[].abilities[]` shows the lone "interrupt" was `Disastèr (Mage) → Polymorph`.
A Polymorph is **CC that incidentally stops a cast**, not a real interrupt kick, so it
isn't valid proof the ability is kickable. The 24 leaked "Shoot" casts are then just
Coilfang Ambusher auto-shots — noise a leader can't act on.

**Preferred fix (root cause):** when validating `spellsInterrupted`, discount interrupts
whose interrupting ability is a hard-CC — reuse `report_common.HARD_CC_NAMES` (already
contains Polymorph, Banish, Sap, …). An ability is only "proven interruptible" if at
least one interrupt came from a *real* interrupt (Counterspell, Kick, Pummel, Shield
Bash, Earth Shock, Spell Lock, …), not solely from CC. This generalizes — it catches
any cast whose only "kick" was a Poly/Banish, not just Shoot. (Backstop, if needed: a
small auto-attack name blocklist `{"Shoot", "Auto Attack", "Melee"}`.)

Per the soul, a **data-integrity** fix: the leaked-interrupts view should name
actionable mechanics, not casts that were never really kickable. Applies equally to
the per-boss Interrupts view (`unkicked_compare`), which reads the same source.

## TODO: Optimize tab — pool rotation across ALL shared bosses for both sides

> Update: use every single overlapping boss in the report — pool the rotation across
> all shared boss fights for each spec. The world-best benchmark is still one top
> same-faction player per spec (derived the same way we already do), but their casts
> should be summed across every shared boss they killed, just like our raiders' side.

**What to build** (`fetch_worldbest.py` + `build_optimize`):

- **World-best side:** currently `fetch_worldbest` finds the top same-faction player
  for a spec on ONE boss (first in encounter-ID order) and fetches their casts for
  that fight only. Instead: run `characterRankings` for **each** shared encounter,
  collect the top same-faction player's `report{code, fightID}` entry per boss, then
  fetch their Casts table for EVERY shared boss they appear in. Sum ability totals
  across all those fights — the same pooling logic `tier_rotation` already uses for
  our side. One Casts fetch per (world-player report, boss) — ~N×spec calls total, but
  the world-player for a spec may be the same person across multiple bosses (same
  report code), so many fetches may be one extra table call on an already-fetched
  report.

- **Our raiders' side:** `build_optimize` currently restricts to the one boss the
  world-best ranked on. Change `_casts_for` to accumulate across ALL shared
  `boss-<enc>.json` files — already present on disk, no extra API calls. This matches
  how `rotation_buckets` / `tier_rotation` pool our side in the existing Rotation view.

- **Benchmark label:** instead of "World #1 Horde Ret Paladin on High King Maulgar",
  show "World #1 Horde Ret Paladin — N bosses" (or list the bosses) so a reader knows
  the comparison is tier-wide, not a snapshot of one fight.

Per the soul: a single-boss sample is *falsely precise* — it reads as "your rotation
vs the world's best" when it's really one fight. Pooling across the whole tier gives
the honest, representative rotation signal, and is already how every other tier-wide
view in the report works.

## TODO: Trash zone filter — exclude incidental outdoor pulls mislabeled as wrong zones

> Bug: the Trash hint says "Restricted to Isle of Quel'Danas, Serpentshrine Cavern,
> Gruul's Lair" but we only raided SSC + Gruul. We didn't set foot in Quel'Danas.

Confirmed in data: both reports have 5 trash pulls tagged `gameZone {id:530, name:"Isle
of Quel'Danas"}` — but these are outdoor Zangarmarsh trash right outside the SSC
entrance (Umbrafen Oracle, Withered Bog Lord, etc.) that WCL assigns to zone 530
instead of 548 (SSC). Because both sides have zone 530, it passes the shared-zone
intersection (`_trash_zones` + `_filter_to_zones` in `build_deepdive.py`) and appears
in the hint as if it's a real zone the raid cleared. Per the soul, labeling a zone the
raid didn't actually enter is *falsely precise* — a leader reads "Quel'Danas" and
wonders why Sun's Reach is in their SSC report.

**Preferred fix — match trash zones against the zones our boss kills came from.** We
already have boss-kill zone data (`fights.json` carries the kills; we could add
`gameZone` to the kills query). Only include a trash zone in the hint and filter if it
also appears as a boss-kill zone on at least one side. Outdoor trash in a zone with no
boss kills is incidental and should be silently dropped. This is more principled than a
min-pull threshold and doesn't require hardcoding zone IDs.

**Alternative fix — min-pull threshold.** Drop any zone with fewer than N trash pulls
(e.g. N=10) from the shared-zone intersection. Simple but picks an arbitrary cutoff.

Either way: the Trash section should only name zones that represent real raid content
both guilds cleared, not WCL's outdoor-area zone tags bleeding in.

## TODO: Prep matrix — don't flag missing guardian elixir as red for DPS specs

> Don't count it against a DPS if they are missing a guardian elixir — Per-Player
> Consumables — Prep.

Confirmed over-flagging. The prep matrix currently marks the **G** (Guardian Elixir)
cell red for any player who brought a battle elixir but no guardian, regardless of role
(JS line ~317 in report.html: `gS=c.guardian?"good":"miss"`). For DPS specs a guardian
elixir is a defensive/utility choice (HP, stamina, spell crit) — not a throughput
requirement. Only the **battle** elixir directly affects DPS output. Flagging a DPS's
missing guardian red implies a gap that isn't there, which muddies the signal for
leaders scanning for real prep failures.

**Fix (two places):**
1. `_cell_for` in `build_deepdive.py`: expose the player's **role** in the cell so the
   matrix can distinguish DPS from healers/tanks. Or pass role separately.
2. JS `consumeMatrix` in `report.html`: when computing `gS` for the cell, if the
   player's role is `dps` and they have a battle elixir, render `gS="na"` (faint,
   not needed) instead of `gS="miss"` (red). Healers and tanks still require the full
   pair — a healer's guardian elixir (e.g. Elixir of Draenic Wisdom) is throughput.
   Also: the `consumed` definition in `_cell_for` should count a DPS with a battle
   elixir as prepared (not require guardian to pass the threshold).

Per the soul: a false red is *falsely precise* — it reads as a prep failure when it
isn't one, crowding out real failures. The actionable Prep gap for a DPS is missing a
battle elixir or flask, not a missing guardian.

## TODO: "What's Killing Us" — show source mob when the killing blow came from an add

> Bug? "Arcing Smash — High King Maulgar, The Lurker Below." Do both bosses have
> Arcing Smash?

Data confirmed correct, but confusing without context. Arcing Smash appears on both
bosses because:
- **Maulgar (enc 50649):** 3 deaths — Maulgar's own cleave ability.
- **Lurker Below (enc 100624):** 1 death (ßyrdman) — killed by a **Coilfang Guardian
  add**, not by The Lurker. Same ability name, completely different mechanic and fix.

The current `death_list` records the killing blow's **ability name** only, not its
source NPC (`killingBlow.name` = "Arcing Smash" but `death.damage.sources[0].name` =
"Coilfang Guardian" is already in the data). So the tier-wide "What's Killing Us" row
groups them together as "Arcing Smash" with no way to distinguish boss-cleave from
add-melee — a leader reading the table can't tell which fight to fix or who to kill
first.

**Fix:** record the source NPC alongside the killing blow in `death_list`, then
display it in parens in the "What's Killing Us" row when the source differs from the
boss name — identical to what the Trash "What's Killing Us" already does
(`_death_source_mob` + "Fragmentation Bomb (Tempest-Smith)"). For the boss view:
"Arcing Smash (Coilfang Guardian)" on Lurker, "Arcing Smash" on Maulgar. This turns
an ambiguous ability name into an actionable assignment ("kill the Coilfang Guardians
before they cleave"). Source NPC name is in `death.damage.sources[0].name` — already
fetched, no extra API call needed.

## TODO: "What's Killing Us" — break out one row per boss instead of grouping all bosses

> In the "What's Killing Us" table, have one row per boss with the count instead of
> grouping all bosses together for the same ability. E.g. "Melee | 11 | 2 | +9 |
> Fathom-Lord, Maulgar, Vashj, Leotheras" should split into four separate rows,
> one per boss.

Per the soul's "go one level deeper than the count" rule: the current table surfaces
the *what* (Melee) but buries the *where* (Vashj vs Maulgar). A pooled total of 11
Melee deaths across 4 bosses could mean 9 deaths on one boss (fixable, focus here)
or 2–3 scattered evenly (a different kind of problem). Splitting into per-boss rows
makes the delta immediately actionable — a leader sees "Melee on Vashj: 7 vs
benchmark's 0" and knows where to put the assignment call, not just "Melee is bad
across the tier."

**Implementation:** `death_causes` in `build_deepdive.py` already iterates per boss;
instead of accumulating into a single count across all bosses, emit one `(cause, boss)`
pair per boss. `death_cause_compare` then sorts these (ability, boss) pairs by
improvable delta — same ranking logic, just finer grain. The display key becomes
`cause + bossName` instead of `cause` alone. No extra data fetch; all per-boss death
counts are already in `per_boss[].deaths`.

**Design note:** this overlaps with the per-boss Deaths sub-tab (which already shows
individual deaths per boss). The tier-wide view earns its place by ranking the
*relative* gap vs benchmark per (ability, boss) — that cross-guild comparison doesn't
exist in the per-boss tab. Keep the sort by improvable delta (ours−theirs), just at
the (ability, boss) grain, so the highest-leverage fix floats to the top.

---

_Last pass shipped: removed the shaded edge-fade on scrolling
tables, clarified the "Total Boss Kill Time" label (+ verified Clear Efficiency is
scoped to shared bosses), converted the remaining five sections (Buff & Debuff
Coverage Gaps, Early Aggro — Threat Pulls, Add Control — Kill Speed, What's Killing
Us on Trash, Melee deaths — by mob) to mirrored-bar layout with the delta centered
and context columns held on the right, fixed the per-spec timeline tab-title font,
tightened the beefiest table/section descriptions, and dropped the benchmark guild
name truncation to 8 chars._
