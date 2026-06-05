# Backlog

Longer-term ideas for the Warcraft Logs analyzer. Items here are bigger, need more
research/design, or are lower priority than [`TODO.md`](TODO.md).

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> change how a raid leader runs next week — and can they read it and trust it in seconds?

---

## BACKLOG: Trash tab — next-pass ideas

> Pending ideas surfaced while building the (shipped) Trash tab.

- **Lust/cooldowns on trash** as a *descriptive* (not "waste") comparison — the benchmark sets the bar.
  Needs a new Casts-on-trash fetch + view; research-flavored, deferred.
- **Time-gap clustering** of consecutive pulls into player-perceived "packs," if WCL's per-pull
  segmentation ever proves too granular for a given tier. Conditional, not needed yet.

---

## BACKLOG: per-actor positioning (dead-end until OAuth)

> Spread-vs-stack, boss-facing, "where does the melee stand" — the classic positioning gap.

WCL records per-actor coordinates (the website replay works; `boundingBox` is populated per fight), but
the **public client-credentials API withholds the per-actor stream** — all 17k events on a Hydross kill
carried zero `x`/`y`. Confirmed dead-end on the current auth path (2026-06-01).

**One unopened door:** the user-OAuth flow (authorization-code, needs a one-time browser login) *might*
expose the stream. Spike only if positioning becomes a real priority — don't re-investigate the
client-credentials path.

---

## BACKLOG: Layout audit — Overview tab

> Go through the Overview tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Composition tab

> Go through the Composition tab and audit layout/organization. Does it make sense? Should things be
> moved around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Prep tab

> Go through the Prep tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Execution tab

> Go through the Execution tab and audit layout/organization. Does it make sense? Should things be
> moved around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Layout audit — Trash tab

> Go through the Trash tab and audit layout/organization. Does it make sense? Should things be moved
> around? Should explanations be simplified or trimmed? Are there things that aren't clear enough?

---

## BACKLOG: Output format — static HTML vs React/Next vs something else

> Do we need to refactor this from a static HTML generated report to a React/Next app? Is it too
> complicated as a static HTML doc? I like the portability of the HTML doc. If not HTML and not
> React/Next then what?

The soul defines the product as the **report** — self-contained, portable, openable cold by any raid
leader. Static HTML is a direct expression of that value: zero dependencies, zero deploys, works offline,
shareable as a single file. React/Next would add complexity and a hosting dependency without adding
insight. The question worth flagging: is there a *capability ceiling* the current static approach
actually can't clear — something a leader needs that pure HTML+JS can't deliver? If not, portability
wins. The right moment to revisit is when a specific planned feature genuinely can't be built cleanly
in the current format — not before.

---

## SHIPPED: Optimize tab — per-raider rotation vs. world-best player for that spec

Built as the top-level **Optimize** tab (next to Trash): class sub-tabs → spec sub-tabs → each of our
raiders' cast mix vs a **same-faction world-best player** of that exact class/spec. The benchmark frame
is "the ceiling player for your spec" instead of a better guild. Raiders within 5pp on every ability
collapse to a green "matches world best ✓" chip; the rest get the mirrored-bar cast-share table.

How the open questions resolved:
- `worldData.encounter(id).characterRankings(metric, className, specName)` returns the global top 100
  with each entry's `report{code,fightID}`, `guild`, `server`, and a raw `faction` int — so the
  ranked player's log IS reachable, and we fetch their Casts table directly. No new auth path.
- Faction encoding: a guild's `GameFaction` is id 1=Alliance/2=Horde, but a ranking entry's `faction`
  int is 0=Alliance/1=Horde — so the same-faction filter is `entryFaction == guildFactionId - 1`.
- Our roster's spec strings (e.g. `BeastMastery`, `Survival`) match the API's `specName` verbatim — no
  mapping needed. Healers benchmark on `metric:hps`, DPS on `dps`; tanks excluded (no clean metric).
- API budget: ~1 rankings call + 1 casts call per distinct DPS/healer spec (~30 calls for a full raid),
  well under the 3600/hr cap. Cached to `worldbest.json` in our data dir, refreshed with `--refresh`.
- Same-boss integrity: each spec benchmarks on the first shared boss with a same-faction ranking (our
  raiders killed it too), so our-player and world-best cast shares are measured on the SAME encounter.

Known wrinkle (inherited from the Rotation view): a hybrid who played the spec in a different
role/form on the benchmark boss (e.g. a Feral who bear-tanked) reads a large, role-driven "gap" — the
"descriptive, not scored" framing covers it, but form-aware spec detection would sharpen it later.

---

## BACKLOG: Wipes tab — dissect wipe-pull data per boss

> setup data for our "wipes" — add a new main tab called Wipes where we dissect wipe data

The current report already surfaces **wipe counts + wipe depth** (best attempt's boss-HP% and phase)
on each boss card, but that's the ceiling — the raw wipe pulls aren't fetched in full. A dedicated
Wipes tab would answer the question a leader asks after a progression wall: *where exactly are we
dying, and at what point in the fight does it go wrong?* Per the soul, the actionable signal is the
decomposition: not "we wiped 8 times" but "5 of those wipes were P3 deaths to Gravity Lapse, 2 were
P2 cascade deaths within 10s of each other" — that names the drill.

**What this would unlock:**
- Per-boss wipe-pull death list (killing blows + phase/timing) vs the benchmark's wipe pulls — are
  they dying to the same mechanic, and does the benchmark wipe less or get further?
- Wipe-depth progression over attempts (did the raid get closer over the night, or stay stuck at the
  same wall?) — a pure first-party view, no benchmark needed.
- Death cascade detection on wipes (≥4 deaths in 15s — already exists for kill pulls; extend to wipes
  to pinpoint the single event that collapses the raid).

**Open questions / research needed:**
- `attempts.json` currently fetches `fights(killType:Encounters){encounterID kill fightPercentage
  lastPhase}` — cheap, no tables. A full wipe dissection needs the Deaths table per wipe-fight ID,
  which is N more `table(dataType:Deaths, fightIDs:$f)` calls (one per wipe per boss). For a 10-wipe
  night that's manageable; for a 60-wipe progression night it's significant API cost — need a
  cost-cap strategy (e.g. fetch only the N deepest wipes per boss, or cap at last M wipes).
- Are the benchmark's wipe-pull deaths meaningful to compare? A guild on farm has few wipes;
  comparing our 8-wipe Vashj vs their 0-wipe Vashj is one-sided. May be more honest as a
  **first-party-only** view (how OUR raid improves over the night) than an ours-vs-benchmark table.
- Tension with the soul's "honest about scope" rule: the hint text should clearly state
  wipe-pull deaths are separate from the kill-pull "What's Killing Us" view.
