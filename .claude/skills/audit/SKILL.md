---
name: audit
description: Audit existing report features (a tab, a section, or all of them) for whether each earns its place — whether it helps a raid leader make their team better, whether it's accurate, and whether it's legible. Returns a KEEP / SHARPEN / CUT verdict per feature with a short why and a leverage tier. Use when the user asks "is this tab actually useful?", "are these insights helpful?", "what should we cut?", or "audit the ___ tab". Invoked as `/audit <tab | section | all>`.
allowed-tools: Read, Grep, Glob, Bash
---

# audit

You're judging the report's **shipped** features against one question: **does this
help a raid leader make their team better?** That's the bar.

This skill judges what already ships — a *gentler* job than the soul's. The soul
([`PRODUCT_MANAGER_SOUL.md`](../../../PRODUCT_MANAGER_SOUL.md)) is the compass for
what to *build*, and it's deliberately sharp so weak ideas never get made. Here the
feature already exists: assume it earned its slot, and lean toward **sharpening**
it, not re-litigating whether it should have been born. Build to the soul; audit
with the audit.

**Read first, every run:** `PRODUCT_MANAGER_SOUL.md` (the product judgment — this
skill applies its line, it doesn't reinvent it) and
`.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (the map of
what each tab ships). The anatomy doc is a *map, not ground truth* — it drifts from
the code. Before grading a feature, confirm it still ships by checking the builder
(`scripts/build_deepdive.py`) and renderer (`templates/report.html`); flag anything
the doc lists but the code dropped (or vice-versa) as its own finding.

## The line you're applying: worth it vs silly

This is the soul's discriminator — read it there in full; here's the working form.
A feature is **worth it** when it does a job in the leader's head:

- **Surfaces a lever** — names a thing the raid could do differently. The gold
  standard.
- **Aims attention** — tells the leader where the problem is, so they stop spending
  it in the wrong place ("healing's fine, this is a DPS race"). No action attached,
  still earns its place.
- **Confirms a precondition** — something you must know before you act (roster,
  available buffs, whether gear is the issue).
- **Re-rates a known issue** — sizes something already known, moving it up or down
  the fix list.

A feature is **silly** only when *all three* are true at once: **no decision hangs
on it**, **the gap is noise**, and **it was mined because the data was there.** One
or two of those isn't enough — being merely un-fancy is not a cut reason.

The throughline: **respect the leader's judgment.** Information that helps them lead
counts — whether it hands them the answer or just the right place to look.

## The two floors — fixed, not weighed

Everything above is a judgment call. These two are pass/fail, and they sit *under*
the worth-it question, not beside it. You never trade them away to keep a feature.

**1. Accuracy.** Must be a clean signal or honestly framed for exactly what it is.

- If a smart, hostile reader could say *"higher isn't actually better here, because
  ___,"* it's confounded — it carries an honest frame or it doesn't ship.
- Never falsely precise — a proxy is labeled a proxy ("raid-aggregate, not
  per-player"). Approximate-as-exact is the cardinal sin.
- Pre-empts the obvious "wait, is this skewed by ___?" **inline** (tanks excluded,
  fight-length-normalized, boss vs adds). A plausible skew left unaddressed makes
  the number inaccurate, and inaccurate is worthless however useful its shape.

When accuracy is genuinely in doubt, **probe the real data** (`python3` over
`data/<code>/…`, or the report's `DATA` blob) rather than guessing — the actual
distribution settles whether the signal holds.

**2. Legibility.** A raid leader reads it in seconds, unaided, or it doesn't ship.

- A correct signal nobody can read transfers **zero** value, so this is co-equal
  with accuracy — not a nicety.
- **But unreadable rarely means CUT.** If the signal might be real and only the
  presentation fails, that's a **SHARPEN** — make it legible. You only fail a
  feature on legibility when the signal *itself* can't be made readable without
  becoming dishonest.
- A clever chart that's hard to parse should fall back to the plain number that
  still carries it.

## What to actually cut

Cut decisions are about everything *above* the floors. Reserve CUT for features that
are genuinely dead weight, not merely un-fancy:

- **Helps with nothing** — accurate and legible, but serves none of the worth-it
  jobs: no lever, no attention-aiming, no precondition, no re-rating, and all three
  silly-tells are true. Real but inert.
- **An unfixable confound** — can't be made a clean signal, so it can't be made
  accurate; the floor isn't there.
- **Truly redundant** — the *same* signal already shown a click away. (Not
  "related"; the same. Two angles on one dataset can both earn their place.)
- **A raw dump** — re-implements a Warcraft Logs table with no interpretation;
  gives the leader nothing they couldn't get from the log itself.
- **Blame** — names-and-shames a person with no coaching purpose. (Per-player views
  are fine when they exist to *fix* something impersonal — enchants, hit,
  consumables.)

Being ahead of the comparison, implying an "obvious" action, or being a simple
tally are **not** cut reasons. If you catch yourself cutting for one of those, stop
and re-read *the line you're applying*.

## SHARPEN before you CUT

Most weak-but-accurate features want a sharper cut of the same idea, not removal.
Default to SHARPEN and name the upgrade:

- **Make it legible** — the signal's there but the viz buries it; name the plainer
  read. (Now a first-class upgrade, not an afterthought.)
- **Add a frame** — a comparison column, an absolute standard, or a week-over-week
  delta, so a bare number gets a "good vs what?".
- **Go one cut deeper** — from a raid total to the spec / mechanic / phase that
  names the lever (the total rides along as context). A plain tracked-behavior tally
  can also stand on its own — depth is an option here, not an obligation.
- **Name the moment** — attach the *when/where* to a "do more/less" so it's
  pinpointed.

A SHARPEN says "this is useful; here's how it'd be *more* useful." Reach for it
before CUT.

## Ordering: lead with leverage

Passing the bar earns a feature its place; **leverage** decides *where* it sits.
Ask: **if the raid fixed only this, how much would it move a real outcome — a kill,
a wipe avoided, throughput gained?** High-leverage levers lead the tab;
attention-aiming and context features are welcome but sit lower or behind a
drill-down (lean on top, deep on demand). This is ordering, never a cut criterion.

## Process

1. **Scope it.** `$ARGUMENTS` is a tab name, a section, or `all`. Map it to the
   real, *shipping* features by reconciling the anatomy doc against the builder and
   renderer.
2. **Judge each feature fairly — not as a fan, not as a hatchet.** For each: confirm
   it clears both floors (accurate — probe the data when in doubt; legible — could a
   stranger read it in seconds), note which worth-it job it does for a leader, then a
   verdict + leverage tier.
3. **Don't only cut.** SHARPEN is usually the higher-value verdict — name the deeper,
   better-framed, or more-legible version the feature should be.

## Output format

**Default: a scalpel, not a wall.** Lead with only what's worth acting on — what to
**CUT** and the highest-value **SHARPEN**s, one line each, plus the single biggest
*missing* thing. Don't list features that just KEEP as-is; if nothing's wrong, say so
in a sentence.

Only if the user asks for the full picture, add the ranked table below (every feature):

| Feature | Verdict | Why | Leverage |
|---|---|---|---|
| … | KEEP / SHARPEN / CUT | what it does for a leader, or the upgrade / cut reason | High/Med/Low |

Then a 2–4 line **bottom line**: what to sharpen first, what (if anything) to cut,
and — if you spot one — the biggest *missing* thing this tab should show but
doesn't.

Verdicts:
- **KEEP** — clears both floors, and does a worth-it job for a leader.
- **SHARPEN** — useful but ships a shallower, less-framed, or less-legible cut than
  it could; name the better version.
- **CUT** — helps with nothing, an unfixable confound, truly redundant, a raw dump,
  or blame. Say which.

## Calibration

- **What's Killing Us** (death causes by killing-blow + boss). Surfaces a lever at
  the mechanic grain, framed by Δ, clean direction, legible. High leverage. → KEEP.
- **Dispels by mob** (which enemy auras you remove, how often). Maps to an
  assignment — *put someone on dispelling that caster.* A real raid-leading task,
  even framed "descriptive." → KEEP.
- **Item level by role** (ahead on every role). No next-week action, but it aims
  attention — *gear isn't the problem here, stop drilling it.* → KEEP (low leverage,
  sits low). Being ahead doesn't make it vanity.
- **Bloodlust CD-stacking** (signal may be real, but the table is hard to read).
  Don't reach for CUT — this is a **legibility** miss. → SHARPEN: name the plainest
  read that carries it, or fall back to a single number.
- **Healer overheal %** (high overheal flagged as "wasted"). In TBC you *must*
  overheal against burst, so high isn't cleanly bad — confounded *and* no decision
  hangs on it. → CUT (or honest-reframe if a clean cut exists).
- **A confounded "damage by class %"** (more of a class looks identical to that
  class doing more). No honest frame makes it a clean signal → fails the accuracy
  floor. → CUT.

> The bar, in one line: *it's accurate and legible (always) — does it help a raid
> leader make their team better?* Cut it only if it helps with nothing, can't be
> made a clean signal, duplicates, dumps, or blames. Otherwise it's a question of
> how much it helps and where it belongs — not whether it's allowed to exist.
