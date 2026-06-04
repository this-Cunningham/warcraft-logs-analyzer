---
name: audit
description: Ruthlessly audit existing report features (a tab, a section, or all of them) for whether each is ACTUALLY actionable and worth its space — not merely true, clean, or "fun." Returns a KEEP / SHARPEN / CUT verdict per feature with the one-line action it implies (or "none → cut") and a leverage tier. Use when the user asks "is this tab actually useful?", "are these insights actually helpful?", "what should we cut?", or "audit the ___ tab". Invoked as `/audit <tab | section | all>`.
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# audit

You are grading the report's own features against one bar: **does each one change a
decision, or is it just true?** This is the discipline behind every cut in
`PRODUCT_MANAGER_SOUL.md`, applied as a ruthless per-feature checklist. The product
is the report; the report's job is to point a raid leader at the highest-leverage
thing to fix next. A feature that doesn't serve that is dead weight, however clever.

**Read first, every run:** `PRODUCT_MANAGER_SOUL.md` (the philosophy you're enforcing)
and `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` (the canonical
list of what each tab ships, so you audit what's actually there — not what you imagine).

## The one question that settles most of it

> **"What does the raid leader (or raider) DO differently next week because of this —
> in one verb-first sentence — and would they actually do it?"**

If you cannot write that sentence, the feature is **fun, not helpful.** Write the
sentence for every feature you keep; the absence of one is the loudest signal to cut.

## The 4 gates — a feature must pass ALL of them

1. **Action.** There is a real, verb-first thing someone does because of it (the
   question above). Not "now I know X" — "now I *do* X."
2. **Lever / grain — *and the moment*.** It names the **who / what / when / where**
   (spec, mechanic, mob, phase, pull-type) — the level where a leader makes an
   assignment or a callout. A top-level tally that counts without naming the lever is a
   **scoreboard**. And a gap that only says **"do more / less"** (use cooldowns more,
   take less damage) is only half-built: it must attach the **WHEN or WHERE** (which
   phase, which pull-type, on the pull) or it isn't actionable. ("Go one level deeper
   than the count" — *and one level deeper than "more.")*
3. **Honesty + decompose the cause.** The direction is a clean better/worse signal AND
   it's labeled for exactly what it is. Run the skeptic: **"Could a smart, hostile
   reader say 'higher isn't actually better here, because ___'?"** If yes, the signal is
   confounded — cut it unless it's clean. Where the data allows, go past *"you're behind
   on X"* to *"behind on X **because** Y"* (the cause one rung down). Where the data
   genuinely **can't** see the cause, say so plainly — never imply a cause you can't show.
4. **Frame.** The number carries its own *"good vs what?"* — a benchmark Δ, an absolute
   standard (a cap, "wrong vs correct"), **or self-vs-past-self** (week-over-week
   progress is a first-class frame, especially for first-party/pacing metrics where the
   benchmark is on farm and absent). A naked number with no frame is trivia.
5. **Clarity = trust; an unaddressed confound is disqualifying.** A metric must
   **pre-empt the "wait, is this skewed by ___?" question inline** — state what's
   included/excluded (boss vs adds, in-combat vs between-pull breaks, fight-length- or
   roster-normalized, tanks excluded, etc.). A *plausible* skew left unaddressed makes
   the number untrustworthy, which makes it useless — treat "I'm not sure what this
   measures or whether it's confounded" as a failing grade, not a docs nit. (Most
   "needs clarity" feedback is really *"I won't trust this until I know it's not
   skewed."*)

## The value ladder — does the reader ever have to ask "so what?"

Passing the gates makes a feature *legitimate*; this ladder is how **good** it is. The
apex is **meaning that moves someone to act** — an insight that closes the loop
**data → meaning → move** so the reader never does the "so what do I do, and why should
I care?" homework themselves. The apex is **NOT a particular form** (see the warning).

- **Rung 0 — Tally.** A raw count ("23 interrupts"). No meaning. Cut or climb.
- **Rung 1 — Located gap.** True and decomposed (who/what vs a frame) — but the reader
  still has to supply the "so what do I do." *Useful, not yet the bar.* ("Shadow Word:
  Death 95/s vs 0", "Rogues idle 8% more" — located, but now what?)
- **Rung 2 — The move is obvious.** It names the specific lever AND the action is
  instant — no translation needed. **This is the bar.** ("CC that mob on that boss",
  "kick that cast", "land CoE sooner.")
- **Rung 3 — The move is obvious *and* the stakes are felt.** It also makes the reader
  *care* — the cost lands in a currency they feel, so they actually change the behavior.
  The **form varies with the data** — pick whichever fits:
  - a **counterfactual cost** ("these deaths cost you the kill by ~1:34") — fits deaths;
  - **proof it's solvable** ("the benchmark takes *zero* of this cast — it's LoS-able");
  - a **cause diagnosis** that links two facts ("low rogue activity *and* 4× the melee
    damage → it's positioning, not skill");
  - **quantified waste + when** ("~5 unused Arcane Powers per Kael — pop it on pull");
  - a **progress frame** ("you reset 20s slower than last week").

> ⚠️ **Do not overfit on form.** A clever derivation (a counterfactual, a fancy stat) is
> NOT automatically valuable — if the reader still asks "so what do I do?", it's a Rung-1
> number wearing a costume. And a plain, un-derived line — *"they sheep the Legionnaire
> every pull; you never do"* — can be **Rung 3** because the move and the stakes are both
> instantly clear. **Fancy ≠ valuable; plain ≠ trivial.** The only test is the loop:
> *data → meaning → move, with no "so what?" left for the reader.*

> When auditing, name the rung each feature sits on and the rung it *could* reach — and
> the **form** the upgrade should take (it is rarely "add a counterfactual"). A "SHARPEN"
> is usually "this is a located gap at Rung 1; here's the move/stakes that gets it to 2–3."

## Then rank the survivors by leverage

> **"If the raid fixed only this, how much would it move a real outcome — a kill, a
> wipe avoided, throughput gained?"**

High-leverage actionable insights lead the tab. Clean-but-low-stakes ones get demoted
(behind a drill-down) or cut. Payoff is how the report decides what to surface *first*;
a true, clean, but trivial insight still loses its place to a higher-leverage one.

## 3 auto-cuts — don't even bother ranking these

- **Redundant** — the same signal already lives a click away (another tab/section).
- **Blame** — it names-and-shames a person instead of coaching the raid. (Per-player
  views are allowed ONLY to coach; the grain is otherwise spec/mechanic/phase.)
- **Dump** — it re-implements a Warcraft Logs table without interpreting it.

## The "fun vs helpful" failure modes — name them out loud

When you flag a feature, say *which* failure it is — it makes the verdict legible:

- **Scoreboard** — a true tally with no lever ("23 interrupts"). → go a level deeper, or cut.
- **Trivia** — true, clean, even pretty, but implies no action ("focus concentration
  78%"). The hardest case, because it's *honest* — it just isn't *useful*. Features
  already labeled "descriptive, not scored" are the prime suspects: make each one
  justify its page space or demote/cut it.
- **Vanity** — flatters without helping ("you out-geared them on 14/15 slots").

## Process

1. **Scope it.** `$ARGUMENTS` is a tab name, a section, or `all`. Map it to the real
   features from `report-anatomy.md` (and, when you need ground truth, `grep` the
   builder in `scripts/build_deepdive.py` and the renderer in `templates/report.html`).
2. **Audit each feature adversarially.** Be a hostile skeptic, not a fan. For each:
   write its one-line action (or "—"), run the 4 gates, call the failure mode if it
   trips one, then a verdict + leverage tier. When a metric's *cleanliness* is in doubt
   (Gate 3), **probe the actual data** with `python3` over `data/<code>/…` rather than
   guessing — the real distribution settles "is higher actually better."
3. **Fan out for breadth.** If scope is a whole tab or `all`, consider launching one
   `Agent` per tab/section (each reads the soul + anatomy, audits its slice, returns a
   verdict list) and synthesize — it keeps each pass deep and prevents a rushed sweep.
   For a single section, audit it inline.
4. **Don't only cut.** A SHARPEN verdict (the feature has a real action but ships the
   shallow version) is often higher-value than a cut — name the deeper cut it should be.

## Output format

A ranked table, worst-offenders and highest-leverage first:

| Feature | Verdict | Action it implies | Leverage | Failure mode / why |
|---|---|---|---|---|
| … | KEEP / SHARPEN / CUT | one verb-first sentence, or "—" | High/Med/Low | e.g. "Trivia — clean but no action" |

Then a 2–4 line **bottom line**: what to cut first, what to sharpen first, and (if you
found one) the single biggest missing insight this tab *should* have but doesn't.

Verdicts:
- **KEEP** — passes all 4 gates and earns its leverage tier. Leave it.
- **SHARPEN** — has a real action but ships a shallower cut than it should (a tally
  where a who/what/when breakdown is available). Name the deeper version.
- **CUT** — fails a gate (usually Action or Honesty) or trips an auto-cut. Say which.

## Calibration — two worked verdicts

- **What's Killing Us** (death causes by killing-blow + boss). Action: *"assign a
  kick / CC / reposition around the named mechanic on the named boss."* Gates: all
  pass — it's the mechanic grain (lever), ranked by improvable Δ vs benchmark (frame),
  clean direction. Leverage: High. → **KEEP.**
- A hypothetical *"Total damage dealt by class %"*. Action: *"—"* (none — fewer of a
  class looks identical to that class underperforming). Gate 3 fails (confounded),
  Gate 1 fails (no action). Failure mode: **Vanity/Scoreboard.** → **CUT** (and indeed
  the soul already cut it; the per-player DPS-by-spec gap is the honest version).

> The bar, in one line: *Would this help an unfamiliar raid leader decide what to fix
> next — honestly, and at a glance?* If it's a scoreboard, trivia, a vanity stat, a
> guess dressed as a fact, or a thing a click away, it doesn't earn its place.
