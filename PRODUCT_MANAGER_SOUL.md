# Product Manager Soul

The guiding principles for **warcraft-logs-analyzer**. This is not a spec or a
backlog (that's [`TODO.md`](TODO.md)) and not an architecture doc (that's the
memory + [`SKILL.md`](.claude/skills/warcraft-logs-analyzer/SKILL.md)). It's the
product judgment that every feature, metric, and word in the report must answer
to. When a decision is ambiguous, decide it the way this document would.

---

## What the product is

**The product is the report.** A raid leader opens a self-contained HTML report
and walks away knowing the highest-leverage things their raid should fix next.

That's the whole product. The skill, the scripts, the API plumbing, the
stdlib-only pipeline — that is *how the report gets generated*, and it is **not
part of the product**. Engineering choices serve report quality; they never
appear in the report's value proposition and they never earn a feature its place.

## Who it's for

**Any guild's raid leaders** — not just our own guild, and not assumed to be
technical or to share our context. The report must stand on its own to a
stranger. Labels, framings, and insights are written for a competent raid leader
who has never spoken to us.

This audience choice has consequences the soul enforces:

- **Self-explanatory.** A number with no frame ("what's good? vs what?") is a
  failure. Every insight carries enough context to be understood cold.
- **Robust to any roster/zone.** No hard-coded assumptions about who's in the
  raid or which boss is being looked at.

> Note: "runs with zero friction" is about the *generation* pipeline, not the
> product. It is a real engineering value, but it lives in the architecture
> notes — not here.

## North star

> **Surface the highest-leverage gaps versus a benchmark raid, and make each one
> actionable.**

Warcraft Logs already shows you everything. This product's job is the opposite of
breadth: it **ranks what to fix next by payoff** and says it in a way that maps
to a behavior change. "Only 4/25 ate food" beats a flawless table nobody acts on.

Two things hold this together:

1. **Gaps, ranked.** The report exists to point at the lowest-hanging fruit. If
   it doesn't help a leader decide what to fix *first*, it's missing the point.
2. **Actionable.** Every surfaced insight should translate to something the raid
   can *do differently next week*. Facts that don't imply an action are noise.

## Go one level deeper than the count

A raw aggregate answers *"how many,"* and "how many" is rarely a lever. The
number a leader can act on is almost always one decomposition down — not *that* a
thing happened, but **who** did it (class/spec), **what** caused it (mechanic,
mob, ability), or **when** it happened (phase). "23 interrupts" is a scoreboard;
*"your kicks came from Ele Shamans while the benchmark used Fire Mages"* tells a
leader what to change. Same data, one cut deeper — and only the deeper cut implies
an action.

So the default is: **never ship the top-level tally alone.** Surface the
breakdown that names the lever; let the total ride along as *context* for it ("23
total — here's the split"), not as the headline. When a metric resists this — when
there's no honest dimension to decompose it by — treat that as a warning sign that
it may be a scoreboard rather than an insight, and let the data-integrity bar
decide whether it ships at all.

Two clarifications keep this from being misread:

- **"Deeper" means a finer *grain*, not a finer *person*.** The actionable cut is
  almost always the spec, the mechanic, the mob, or the phase — the level where a
  leader makes an assignment or a callout. It is **not** a license for per-player
  tables; the report stays raid/spec/mechanic-level by design.
- **"Deeper" is about meaning, not volume.** Going a level deeper *sharpens* the
  signal — it doesn't clutter the page. The lean Overview headline should itself
  be the decomposed insight ("worst avoidable killing blow: Fragmentation Bomb"),
  not a shallower number. How *much* shows at once is still governed by *Layout:
  lean on top, deep on demand* below; this principle governs *what the thing you
  surface actually says.*

## The benchmark is the spine — but not a cage

The main idea is **comparison to a benchmark raid** (typically a better guild).
Most numbers are far more meaningful as a delta ("Raid DPS on Kael: 18.2k vs
31.4k") than alone. Default to framing things as "ours vs theirs, with a Δ."

**But some checks are valuable in the absolute, with no comparison needed** —
"who in my raid is missing enchants" is actionable on its own; nobody needs a
benchmark to know an empty enchant slot is wrong. These first-class absolute
checks are welcome.

And the product should still **work on a single report with no benchmark** — that
path is valid and supported. The benchmark is the headline mode, not a hard
dependency.

## Data integrity — the line we don't cross

The audience trusts these numbers to make calls. That trust is the product.

- **Cut it unless it's clean.** If a metric isn't a clear better/worse signal, it
  does not ship. We have already dropped raw gem counts (can't distinguish a low
  count from few sockets) and raw interrupt/dispel counts (raw totals aren't
  better-or-worse). When in doubt, **silence over noise.**
- **Never falsely precise.** A proxy or aggregate is labeled as exactly what it
  is ("raid-aggregate, not per-player exact"). Presenting approximate data as
  exact is the cardinal sin — an honest gap beats a confident lie.
- **Honest about limits.** Where the data has a known caveat, state it plainly
  rather than letting the reader over-read the number.

## Voice

**Neutral analyst.** Factual, measured, let the numbers carry the weight. State
the gap; don't moralize about it and don't soften it. Not a drill sergeant, not a
cheerleader — the report respects the leader enough to just show them the truth
and trust them to act.

## Layout: lean on top, deep on demand

When a clean metric would still clutter the page, **layer it**: lead lean (the
Biggest Gaps scorecard, the top deltas), and hide depth behind drill-downs and
sub-tabs the leader opens only if they want it. A leader should get the headline
gaps in seconds and be able to descend into any one of them — never be forced to
wade through everything to find the signal.

## What earns a feature its place

A candidate feature must pass the first test; the second is a bonus weight:

1. **Does it reveal a gap to fix?** It must point at something the raid is doing
   worse — a lever, not just a fact. (Absolute prep checks like enchants count:
   the gap is "wrong vs correct," not "us vs them.")
2. **Bonus: does it mine a new modality of data?** Extra weight for surfacing a
   *kind* of data we haven't looked at yet. Keep asking the meta-question every
   pass: *what nook of the data haven't we leveraged?*

Practical considerations (payoff-per-effort, cheap on API points, reuse of
already-fetched data) are real and shape *ordering* — but they're prioritization,
not soul. A high-effort feature that reveals a real gap still belongs; a cheap one
that doesn't reveal a gap does not.

## Anti-goals — reject a feature on sight if it makes the product any of these

- **A raw data dump.** If it doesn't *interpret*, it doesn't ship. A wall of
  tables that re-implements Warcraft Logs has negative value.
- **A scoreboard.** A bare aggregate that counts something without naming the
  who/what/when behind it. It reads as information but implies no action — and
  zoomed out, an unexplained total is often just confusing. See *Go one level
  deeper than the count.*
- **A blame machine.** Even per-player views exist to *coach*, not to name-and-
  shame. The aim is "here's how the raid improves," never "here's who to punish."
- **A Warcraft Logs replacement.** We are a focused gap-analyzer, not a log
  browser. We don't compete on breadth; we win on judgment.
- **Dishonest or falsely precise.** See *Data integrity*. This one is
  non-negotiable.

## Scope

**TBC Classic raiding, and we lean into it.** Tier-specific knowledge —
consumable rules (battle + guardian elixir pairing), spec definitions, the
encounter set — is a feature, not a liability. We do **not** dilute the product
chasing generality across expansions or other games. Depth in this game beats
shallow breadth across many.

---

## The one-line test

> *Would this help an unfamiliar raid leader decide what to fix next — honestly,
> and at a glance?*

If yes, it might belong. If it's a data dump, a scoreboard a leader can't act on,
a guess dressed as a fact, a way to blame someone, or breadth for its own sake —
it doesn't.

And a sharpening follow-up for anything that passes: *Is this the deepest honest
cut, or just the easiest tally?* If there's a level deeper that names the lever,
that's the one to ship.
