---
name: audit
description: Audit existing report features (a tab, a section, or all of them) for whether each earns its place — whether it helps a raid leader lead, and whether it's honest. Returns a KEEP / SHARPEN / CUT verdict per feature with a short why and a leverage tier. Use when the user asks "is this tab actually useful?", "are these insights helpful?", "what should we cut?", or "audit the ___ tab". Invoked as `/audit <tab | section | all>`.
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# audit

You're judging the report's features against one question: **does this help a raid
leader lead their raid?** That's the bar. Everything below is just how to apply it
without fooling yourself, in either direction.

Two things to hold onto, because they're the easy mistakes:

- **The reader is an expert, not a helpless reader.** A good raid leader brings their own
  judgment. The report does **not** have to pre-chew every number into a no-brainer
  action to be worth its space. It earns its place by handing them something useful — and
  "useful" has several shapes (below), not just "here is the exact move." Cutting a
  feature because it's *only* awareness, *only* context, or an *obvious* tally is the
  mistake this skill exists to avoid making.
- **Accuracy is the floor, not a lever.** Everything that ships must be accurate — correct
  numbers, no false precision, every caveat stated. That's table stakes for the whole
  report, assumed of every feature; you never trade it away for a nicer-looking one. So it
  isn't a *factor* in "does this earn its place" — it's the ground that question stands on.
  *Whether* a feature earns its place is the real call, and it's a multi-factor judgment,
  not a single test. (See *Accuracy — the floor*.)

**Read first, every run:** `PRODUCT_MANAGER_SOUL.md` (the product judgment) and
`.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (the map of what each
tab ships). The anatomy doc is a *map, not ground truth* — it drifts from the code. Before
grading a feature, confirm it still ships by checking the builder
(`scripts/build_deepdive.py`) and renderer (`templates/report.html`); flag anything the
doc lists but the code dropped (or vice-versa) as its own finding.

## The shapes of "useful" — all legitimate

A feature earns its place if it does any of these for a raid leader. Don't downgrade one
just because it's the second, third, or fourth kind instead of the first.

- **Hands them an action** — a gap that maps to something the raid does differently next
  week ("gem hit on the Ele Shaman", "CC that mob", "prepot on the pull"). The best of
  these resolve an either/or the leader was unsure about — is the low number gear or play?
  is the leaked kick unassigned or just failing? — and so point at *which* fix. That
  disambiguation is the **ceiling to aim for when the data allows**, not a bar every
  feature must clear.
- **Gives at-a-glance awareness** — "how do we stack up?" is a real question a leader
  asks, *including where we're ahead*. Seeing item level by role, or that the raid is
  strong on flasks, is legitimate situational awareness even with no single action
  attached. Being ahead of the benchmark is information, not vanity.
- **Is a diagnostic breadcrumb** — a number the leader interprets with their own expertise
  to decide where to look next ("rogues look low — oh, they have no expertise → check
  their gear"). It doesn't have to close the loop itself; the leader closes it.
- **Tallies a behavior the leader tracks** — a plain count of something the raid should be
  doing (combat potions, healthstones) is useful even when the "should" is obvious and
  even with no benchmark. The leader already knows people should pot; the value is *seeing
  whether they did*. A tally like this is not a "scoreboard" to cut.

The throughline: **respect the leader's judgment.** Information that helps them lead
counts — whether it hands them the answer or just the right thing to look at.

## Accuracy — the floor

Not one of the things you weigh — the prerequisite underneath all of them, and the
soul's "line we don't cross." Everything that ships must be accurate; you never trade it
away to keep a feature. A metric must:

- **Be a clean signal, or honestly framed.** If a number implies "higher is better" but a
  smart, hostile reader could say "higher isn't actually better here, because ___", it's
  confounded — either it carries an honest frame for what it really is, or it doesn't ship.
- **Never be falsely precise.** A proxy or aggregate is labeled as exactly what it is
  ("raid-aggregate, not per-player"). Approximate-presented-as-exact is the cardinal sin.
- **Pre-empt "wait, is this skewed by ___?" inline.** State what's included/excluded
  (boss vs adds, tanks excluded, fight-length-normalized, …). A plausible skew left
  unaddressed makes the number inaccurate — and an inaccurate number is worthless,
  however useful its shape would otherwise be.

When accuracy is genuinely in doubt, **probe the real data** (`python3` over
`data/<code>/…`, or the generated report's `DATA` blob) rather than guessing — the actual
distribution settles whether the signal holds.

## What to actually cut

Accuracy is the floor (fixed, not weighed); cut decisions are about everything *above* it.
Reserve CUT for features that are genuinely dead weight, not merely un-fancy:

- **Helps with nothing** — accurate, but serves none of the shapes above: no action, no
  awareness, no breadcrumb, no tracked behavior. Real but inert.
- **An unfixable confound** — can't be made into a clean signal, so it can't be made
  accurate; the floor it would stand on isn't there. (See *Accuracy*.)
- **Truly redundant** — the *same* signal already shown a click away. (Not "related"; the
  same. Two views of one dataset from different angles can both earn their place.)
- **A raw dump** — re-implements a Warcraft Logs table with no framing or interpretation,
  giving the leader nothing they couldn't get from the log itself.
- **Blame** — names-and-shames a person with no coaching purpose. (Per-player views are
  fine when they exist to *fix* something — enchants, hit, consumables; the absolute
  "wrong vs correct" prep checks the soul blesses are not blame.)

Being ahead of the benchmark, implying an "obvious" action, or being a simple tally are
**not** cut reasons. If you catch yourself cutting for one of those, stop and re-read
*The shapes of "useful"*.

## SHARPEN before you CUT

Most weak-but-accurate features want a sharper cut of the same idea, not removal. Default to
SHARPEN and name the upgrade. The usual upgrades:

- **Add a frame** — a benchmark column, an absolute standard, or a week-over-week compare,
  so a bare number gets a "good vs what?".
- **Go one level deeper** — from a raid total to the spec / mechanic / phase that names
  the lever (the total can ride along as context). But a plain tally the leader tracks can
  also stand on its own — depth is an option here, not an obligation.
- **Name the moment** — attach the *when/where* to a "do more/less" so it's pinpointed.

A SHARPEN says "this is useful; here's how it'd be *more* useful." Reach for it before CUT.

## Ordering: lead with leverage

Passing the bar earns a feature its place; leverage decides *where* it sits. Ask: **if the
raid fixed only this, how much would it move a real outcome — a kill, a wipe avoided,
throughput gained?** High-leverage actionable gaps lead the tab; awareness and context
features are welcome but sit lower or behind a drill-down (lean on top, deep on demand).
This is ordering, never a cut criterion.

## Process

1. **Scope it.** `$ARGUMENTS` is a tab name, a section, or `all`. Map it to the real,
   *shipping* features by reconciling the anatomy doc against the builder and renderer.
2. **Judge each feature fairly — not as a fan, not as a hatchet.** For each: confirm it's
   accurate (probe the data when in doubt — see *Accuracy*), note what it does for a
   leader (which useful shape), then a verdict + leverage tier.
3. **Fan out for breadth.** For a whole tab or `all`, consider one `Agent` per
   tab/section (each reads soul + anatomy, audits its slice, returns verdicts) and
   synthesize. Audit a single section inline.
4. **Don't only cut.** SHARPEN is usually the higher-value verdict — name the deeper or
   better-framed version the feature should be.

## Output format

A ranked table, highest-leverage and clearest verdicts first:

| Feature | Verdict | Why | Leverage |
|---|---|---|---|
| … | KEEP / SHARPEN / CUT | what it does for a leader, or the upgrade / cut reason | High/Med/Low |

Then a 2–4 line **bottom line**: what to sharpen first, what (if anything) to cut, and —
if you spot one — the biggest *missing* thing this tab should show but doesn't.

Verdicts:
- **KEEP** — accurate, and earns its place via any useful shape.
- **SHARPEN** — useful but ships a shallower or less-framed cut than it could; name the
  better version.
- **CUT** — helps with nothing, an unfixable confound, truly redundant, a raw dump, or
  blame. Say which.

## Calibration

- **What's Killing Us** (death causes by killing-blow + boss). Hands the leader an action
  at the mechanic grain, framed by Δ vs benchmark, clean direction. High leverage. → KEEP.
- **In-combat consumable usage** (per-player potion / healthstone tally, no benchmark). No
  single "do X", and the should-pot rule is obvious — but it lets a leader *see whether
  the raid actually potted*, which they can't get at a glance elsewhere: a plain tally of
  a tracked behavior. → KEEP. (A benchmark column would SHARPEN it, not rescue it.)
- **Item level by role** (we're ahead on every role). No direct next-week action, but it's
  real at-a-glance awareness of how the raid stacks up. → KEEP (low leverage, sits low on
  the tab). Being ahead doesn't make it vanity.
- **A confounded "damage by class %"** (more of a class looks identical to that class
  doing more). No honest frame makes it a clean signal, so it can't be made accurate. → CUT.

> The bar, in one line: *it's accurate (always) — does it help a raid leader lead?* Cut
> it only if it helps with nothing, can't be made a clean signal, duplicates, dumps, or
> blames. Otherwise it's a question of how much it helps and where it belongs — not
> whether it's allowed to exist.
