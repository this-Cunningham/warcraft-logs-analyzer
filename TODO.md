# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: Interrupts — refactor to ability-first with specs nested

> In the Abilities Interrupted section, nest the kicking specs under each ability, ours vs benchmark —
> "benchmark used Fire Mages to kick X, we used Ele Shaman."

Under each interrupted ability in the Abilities Interrupted list, show which specs handled it and how
many kicks (counts preserved), ours vs benchmark side by side. Descriptive (like
Dispels — a different spec assignment isn't inherently better/worse, but reveals strategy differences).
Data already fetched: Interrupts table `details[]` has per-player kick counts per ability; join with
`primary_spec_map` to bucket by spec. No new fetch needed.

---

## TODO: Enemy Targets — Engagement & Survival — find better insights or cut

> The current insights from this data are not useful or interesting. Find more useful insights to derive
> from this data, or remove the section.

The underlying data (per-enemy first-appearance time, survival duration, ours vs benchmark) may have
something in it — but the current view doesn't surface it. What meaningful gap can actually be read from
enemy engagement timelines that a raid leader would act on?

---

## TODO: Trash tab — next-pass ideas

> Pending ideas surfaced while building the (shipped) Trash tab.

- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
  Needs a new Casts-on-trash fetch + view; research-flavored, deferred.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier. Conditional, not needed yet.

---

## TODO: per-actor positioning (dead-end until OAuth)

> Spread-vs-stack, boss-facing, "where does the melee stand" — the classic positioning gap.

WCL records per-actor coordinates (the website replay works; `boundingBox` is populated per fight), but
the **public client-credentials API withholds the per-actor stream** — all 17k events on a Hydross kill
carried zero `x`/`y`. Confirmed dead-end on the current auth path (2026-06-01).

**One unopened door:** the user-OAuth flow (authorization-code, needs a one-time browser login) *might*
expose the stream. Spike only if positioning becomes a real priority — don't re-investigate the
client-credentials path.

---

## TODO: Rotation — Ability Mix: DPS / Healer tab + all overlapping specs + collapse-on-match

> Split Rotation — Ability Mix into a DPS tab and a Healer tab; show every spec both raids fielded;
> collapse specs where the cast mix barely differs and show a green success label instead.

Same data source (Casts table) and same descriptive framing — cast share per ability, ours vs benchmark,
biggest divergence first. Healer spell priority is a real coaching lever (e.g. Holy Priest over-relying
on Flash Heal vs Greater Heal). Tab toggle keeps the view lean (same pattern as Kill Order / Crowd
Control in the Trash tab). `rotation_buckets` already pulls the full Casts table — needs healer-role
filter unlocked and a second spec-bucketing pass.

For specs where `maxDiff` is below a threshold (TBD — maybe ≤5pp), collapse the panel and render a green
chip ("Rotation matches benchmark") so a leader can see at a glance which specs are fine and focus on the
ones that aren't. Expanded panels stay as-is for specs with real divergence.

---

## TODO: in-combat consumables matrix (second matrix, below the existing prep one)

> Add a second per-player matrix underneath the existing prep matrix — same shape, focused on in-combat
> consumables: combat potion, health potion, mana potion, healthstone. Don't touch the existing matrix.

Same structure as the existing prep matrix (rows = players sorted worst-first, columns = bosses, sub-columns
per consumable type, ✓/✗ cells). The "P" combat potion sub-column should move out of the existing matrix
into this new one (so the prep matrix becomes F · B · G · Fd only). Sub-columns in the new matrix:
**P** (combat potion) · **HP** (health potion) · **MP** (mana potion) · **HS** (healthstone).

Data source is the same Buffs aura table scoped by `sourceID` (`consumes-<enc>.json`) — health/mana pots
and healthstones should appear as buff auras with `totalUses`; spell IDs need confirming from live data.
Healthstone availability is warlock-dependent — flag "no warlock in raid" rather than marking every player
red when none were present.

---

## TODO: throughput consumable choices — potion count gap + type breakdown by spec

> More comprehensive breakdown on throughput potions — "you popped 17 less potions on boss fights";
> per-spec breakdown ("rogues used 21 more potions than your rogues"); surface which types top guilds use.

Two angles:

1. **Potion count gap (ours vs benchmark, per spec):** total combat potion activations across shared
   bosses, bucketed by spec, ours vs benchmark. "Rogues: 21 more pots" is a concrete, actionable gap at
   the spec grain — raid-level coaching, not per-player. The benchmark is the discovery mechanism for
   which throughput potions matter (no hardcoded assumptions) — mine spell IDs from the benchmark's buff
   auras, the same way `FLASK_IDS` etc. were built. Data already fetched (`consumes-<enc>.json` per-player
   buff auras + the Casts table for in-fight pot casts).

2. **Which throughput potions (flask + battle elixir choices):** surface WHICH specific buff players are
   using, so a leader can see DPS on survival flasks vs throughput ones. The existing matrix classifies by
   category; this extends to the specific buff name within each category. Benchmark-first: the top guild's
   buff auras reveal the meta choices without us having to hardcode them.

---

## BUG: Clear Efficiency — wall-clock not scoped to shared zone

> Clear Efficiency is not comparing apples to apples — the benchmark may have run 3 raids in the time
> we ran one; wall-clock and out-of-boss time need to be scoped to the shared encounters only.

Currently uses the full report wall-clock (first pull to last kill across the entire night). If the
benchmark guild's report covers SSC + TK + Gruul but ours covers only TK, the comparison is meaningless.
Fix: scope wall-clock and derived values (out-of-boss time, clear efficiency) to the time window
spanning only the shared bosses — from the first pull of a shared encounter to the last kill of a shared
encounter, on each side independently. Audit all other night-total or report-wide metrics nearby for the
same issue — any value computed from the full report window rather than the shared-boss window is suspect
when the two reports cover different raid zones.

---

## BUG: Consumables Coverage — elixir pair not counted as "flasked"

> The Flask coverage card doesn't count a battle + guardian elixir combo as equivalent to a flask.

The per-player matrix already handles this correctly (`_elixir_type` + route-aware cell rendering treats a
flask OR a battle+guardian pair as "prepared"). The Coverage card at the top of Prep counts flask auras
only, so a player on a full elixir pair reads as un-flasked there — understating true coverage and
contradicting the matrix below it. Fix: apply the same "flask OR elixir pair" logic to the coverage
denominator/count that the per-player matrix already uses.
