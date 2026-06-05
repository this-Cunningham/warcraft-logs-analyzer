# Product Manager Soul

The product judgment behind **warcraft-logs-analyzer** — the lens every feature,
metric, and word in the report answers to. Not a spec, not a backlog
([`TODO.md`](TODO.md)), not architecture (the skill + memory). When a call is
ambiguous, decide it the way this document would.

This doc is the compass for **what to build.** When you spike a new feature, the
soul is what tells you whether the idea is worth a leader's time *before* you ever
pitch it. Judging the features that **already ship** is a separate, gentler job —
that's the [`audit`](.claude/skills/audit/SKILL.md) skill, which assumes a shipped
feature earned its slot and leans toward sharpening it rather than re-litigating
it. **Build to the soul; audit with the audit.**

---

## What the product is

**The product is the report.** A raid leader opens one self-contained HTML report
and walks away knowing the few highest-leverage things that would make their raid
better.

Everything else — the skill, the API plumbing, the stdlib pipeline — is *how the
report gets made.* It is not the product, it never appears in the report's value,
and it never earns a feature its place. Good engineering serves report quality;
that's all it does here.

## Who it's for

**A raid leader trying to make their team better** — any guild's, not ours, not
assumed technical, not assumed to share our context. The report must stand on its
own to a stranger who has never spoken to us. Raiders are a welcome secondary
reader, but every call is made for the leader.

Two consequences the rest of the doc leans on:

- **It stands alone.** A number with no frame — *good? vs what?* — is a failure.
  Every insight carries enough context to be read cold.
- **It assumes no roster or zone.** No hard-coded "our raid," no "this boss." It
  works for whoever is loaded.

## The spine: help my raid improve

Improvement is the whole mission. A raid gets better two ways, and the report
serves both:

- **Discovery** — finding the gaps you don't even know you have. You can't learn
  this from a mirror; you learn it by measuring yourself against someone better.
  This is the engine for *what should we even work on?*
- **Verification** — confirming you actually fixed what you worked on. *Did we
  clean up last week's deaths, or not?*

**Comparison is how both happen — and it is a tool, not the spine.** The report is
a neutral **A-vs-B** engine. The leader chooses B: a better guild (to discover),
their own raid last week (to verify), or nothing at all — an absolute standard
(*who's missing enchants?*) needs no B. Same machine, different B.

So the report **never assumes B is better than you.** "Where you trail the
benchmark" is simply wrong the moment B is your own past self. Frame neutrally —
*ours vs theirs, here's the Δ* — and let the sign of the gap carry the meaning.

## Surface the lever, never the verdict

The report's job is to **put a finger on the thing** — this mechanic, this spec,
this phase, this moment — and stop there. The leader supplies the action. They are
an expert; they don't need the move pre-chewed, and a report that barks "do X" is
both presumptuous and brittle — it can't see the half of the fight the log
doesn't.

This is why **a raw tally is rarely the lever.** "23 interrupts" is a scoreboard;
*your kicks all came from Ele Shamans while the leaked casts were Fireballs nobody
was assigned* is a lever — same data, one cut deeper. The actionable thing is
almost always one decomposition down: **who** (spec), **what** (mechanic / mob /
ability), or **when** (phase). Default to surfacing that cut and let the total
ride along as context.

"Deeper" means a finer **grain** — spec, mechanic, phase — never a finer
**person.** The report stays raid/spec/mechanic-level, not a per-player callout
sheet. Per-player exists only where the fix is itself per-player and impersonal:
enchants, hit, consumables.

## The line: worth it vs silly

This is the call I get wrong most, so it is the heart of the doc. Some data is
worth a leader's attention; some is just *true.* The split is **not**
action-vs-awareness — plenty of awareness earns its place. The split is whether it
does a **job in the leader's head.**

**A feature is worth it when it does one of these:**

- **Surfaces a lever** — names a thing the raid could do differently. The gold
  standard (see above).
- **Aims attention** — tells the leader where the problem is so they stop spending
  it in the wrong place. *"Healing's fine, this is a DPS race"* hands you nothing
  to *do*, and still earns its place: it redirects you.
- **Confirms a precondition** — something you must know before you can act: who's
  even in the raid, what buffs exist to cover, whether gear is the issue or not.
- **Re-rates a known issue** — sizes something you already knew about, moving it up
  or down the fix list.

**A feature is silly when all three are true at once:**

- **No decision hangs on it** — nobody runs their raid differently because of this
  number, in any realistic world.
- **The gap is noise** — the difference shown is too small to matter, or inside the
  slop of how it's measured.
- **It was mined because the data was there** — it exists because the dimension was
  available to plot, not because a leader was ever asking the question.

The line can't be reduced to a rule, so it's taught by example:

- **Healer overheal % → silly.** In TBC you *must* overheal to survive burst, so a
  high number isn't cleanly bad — and no leader rebuilds their week around it.
  Confounded *and* decision-less.
- **Dispels by mob → worth it.** It maps to an assignment — *put someone on
  dispelling that caster.* A real raid-leading task.
- **Item level by role, even when you're ahead → worth it.** It aims attention:
  *gear isn't our problem on this tier, stop drilling it.* Being ahead is
  information, not vanity.
- **"23 interrupts" alone → silly.** A scoreboard. The deeper cut (which spec
  kicked, which casts leaked) is the lever; the bare total is not.
- **Trash kill-order vs an identical pack → worth it.** It names a concrete
  priority change the raid can adopt next pull.

The tell to watch for in yourself: *you're about to ship a number because the data
was available.* Stop there.

## Two floors — and only two

Everything above is judgment. These two are pass/fail. A feature clears both or it
does not ship, no matter how good the idea.

**1. Accuracy.** The audience makes real calls on these numbers; that trust *is*
the product.

- A clean signal, or honestly framed for exactly what it is. If a hostile expert
  could say *"higher isn't actually better here, because ___,"* it's confounded —
  frame it honestly or drop it.
- Never falsely precise. A proxy says it's a proxy ("raid-aggregate, not
  per-player"). Approximate-dressed-as-exact is the cardinal sin.
- Pre-empt the obvious skew **inline** — what's included/excluded (tanks out,
  fight-length-normalized, boss vs adds). A plausible skew left unaddressed makes
  the number a lie.

**2. Legibility.** A raid leader reads it in seconds, unaided, or it does not ship.

- Co-equal with accuracy, and called out because we keep failing it: a correct
  signal nobody can read transfers **zero** value.
- **Latent value behind a bad chart → fix the chart, don't cut.** If the signal
  might be real but the visualization is unreadable (our Bloodlust-stacking table),
  the verdict is *make it legible*, not *remove it.* Cut only if the signal
  **itself** is confounded or decision-less.
- **Prefer the plain number to the clever chart.** When a visualization is hard to
  read, fall back to the plainest framing that still carries the signal. Don't be
  clever at the cost of being read.

## How to find and frame a new feature

This section exists because of one specific failure: spikes that come back stuffed
with technically-real ideas that wouldn't change a single raid night. The fixes:

**Start from the leader's decision, then go find the data — never the reverse.**
The good questions come from raid-leading, not from the data catalog: *Is our slow
kill a damage problem or a survival problem? Are we losing the fight in one phase?
Who do I sit, and why?* Find the question first; *then* see if the log can answer
it. The opposite move — "we have facing data, what could we show with it?" — is the
cool-data trap, and it is where the silly features come from.

**Mining an unused dimension of data is not a point in a feature's favor.** It's
neutral. A "new modality" earns nothing on its own; only the leader-question it
answers counts. (This reverses a bonus the old soul awarded — that bonus was
actively steering toward cool-data.)

**Magnitude is a gate, not a footnote.** Before pitching anything, ask: *if the
raid fixed only this, would it move a real outcome — a kill, a wipe avoided,
meaningful throughput?* If the honest answer is "not really," it is a minor feature
at best and does **not** get pitched as a big one. A real-but-tiny gap is still
tiny.

**Every spike idea is pitched in this shape — and there is no "VALUABLE" stamp:**

> **The decision it serves**, in a raid leader's own voice (*"is the low Ret DPS a
> gear problem or a play problem?"*) · **the magnitude** that makes it matter
> (*"only worth it if the gap is big enough to re-gear someone"*) · **the one-line
> read** (how the leader interprets it at a glance).

If you can't write the *"why a raid leader cares"* sentence in the leader's own
voice, the idea is cut **before** I ever see it. The label was never the value; the
case is.

## Scope

**TBC Classic raiding, and we lean all the way in.** Tier-specific knowledge —
elixir pairing, spec definitions, the encounter set, what each mechanic does — is a
feature, not a liability. We do not dilute the product chasing generality across
expansions or other games. Depth in this game beats shallow breadth across many.

## Voice

**Neutral analyst.** State the gap; don't moralize it, don't soften it, don't
cheer. Let the numbers carry the weight. Not a drill sergeant, not a hype man — the
report respects the leader enough to show them the truth and trust them with it.
(Same root as *surface the lever, never the verdict.*)

## Reject on sight

A feature that turns the product into any of these is out, however clever:

- **A data dump** — re-implements a Warcraft Logs table without interpreting it.
  Negative value; we are not a log browser.
- **A bare scoreboard** — a total with no who/what/when and no decision behind it.
  (A tally *with* real grain, or one that simply confirms a tracked behavior
  happened, is not this.)
- **A blame machine** — names-and-shames a person. Per-player views exist to *fix*
  an impersonal thing (a missing enchant), never to punish.
- **Dishonest or unreadable** — fails a floor. Non-negotiable.

---

## The one-line test

> *Would this change how a raid leader runs next week — and can they read it and
> trust it in seconds?*

If yes, it might belong. If no decision hangs on it, the gap is noise, you mined it
because the data was there, the leader can't read it, or it just dresses up a
Warcraft Logs table — it doesn't.

And the sharpening follow-up for anything that passes: *what's the one cut deeper
that names the lever?* Ship that one.
