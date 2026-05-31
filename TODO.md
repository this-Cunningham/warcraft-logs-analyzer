# TODO / Backlog

Living backlog for the Warcraft Logs analyzer. Newest ideas at the bottom of each section.

---

## Open question: language / runtime — Node or Python instead of PowerShell?

> Should this be written in Node/Python instead of PowerShell? Can it be written in
> those and still work? Are those better than PowerShell (my guess is probably)?

Notes / context to evaluate:
- **Can it work in Node/Python?** Yes, cleanly. The whole pipeline is just: OAuth token →
  GraphQL POST → shape JSON → inject into a static HTML template. None of that is
  PowerShell-specific. The **report itself wouldn't change at all** — it's already a
  self-contained HTML file with vanilla JS; only the fetch/build scripts would be rewritten.
- **Why PowerShell today:** it was the zero-install path — this Windows box has no Node or
  working Python, but PowerShell + `curl` are built in. Good for "just works," less good for
  ergonomics (the UTF-8/encoding gotchas, verbose JSON handling, `ConvertTo-Json` single-element
  array unwrapping we had to defend against).
- **Likely better in Node/Python because:** nicer JSON handling, real package ecosystem (a GraphQL
  client, a templating lib), easier testing, and a clearer path *if* this ever becomes a hosted
  web app (see the tab-restructure note + the original "do we need Next.js" discussion).
- **Cost of switching:** requires installing a runtime (and for Node, `npm install`). Decide based
  on where the project is headed (static report generator → PowerShell is fine; interactive/hosted
  app → Node/Next).
- Decision criteria mirror the earlier architecture chat: stay simple while it's a "generate a
  shareable report" tool; switch when it becomes an "interactive product."

---

## TODO: more / better insights — what other data can we leverage?

> What else can we do to give better insights and ability to improve our raid? What other
> data is available? What little nooks and crannies of data can we leverage to find
> gaps / areas for improvement?

Concrete candidates already identified from API exploration (not yet built):
- **Cooldown usage** (`Casts` table, filter to CD ability IDs): did players actually fire
  Combustion / Recklessness / Death Wish / trinkets / Power Infusion / racials — counts vs benchmark.
- **Per-class rotation / ability-mix** (`dd.abilities[]` — already fetched): compare one of our
  mages to the benchmark's best mage, ability by ability. Deepest *individual* coaching tool.
- **Death timeline & cause** (`Deaths` table): what killed each raider and *when* (pull vs execute).
- **Interrupts: kicks landed vs missed** (`intr.missedCasts[]`): we currently only count successful
  interrupts; show interruptible casts that went off un-kicked. Also a per-*player* interrupter view.
- **Flask / consumable coverage per player**: raid-aggregate flask presence is visible, but
  per-player needs a per-source buff query or event scan.
- **Healer mana / OOM + resource usage** (`Resources` table).
- **Phase timing** (`phaseTransitions` on fights): time spent per phase on multi-phase fights
  (Vashj P1/P2/P3, etc.) — where does the time actually go.
- **Gear / item-level gaps**: per-player ilvl vs the benchmark's same-role players; biggest BiS gaps.
- **Positioning** (x/y from events): advanced/heavy to render, but possible (spread/stack mechanics).
- Keep asking the meta-question every pass: *what modality of data haven't we looked at yet?*

---

## TODO: restructure top-level tabs (Composition + Bosses)

> Break the top level of "Dive Deeper" into other tabs. Raid comp all the way down to
> per-player inspection should be a separate whole tab next to Dive Deeper. We can probably
> rename Dive Deeper to be about composition, then create a tab next to it that's like "Bosses".

Plan:
- Promote the per-boss content (buff/debuff uptime, damage taken, interrupts — currently the
  "Per-Boss Execution" section with its sub-tabs) into its own top-level **"Bosses"** tab.
- Rename **"Dive Deeper" → "Composition"** (or "Raid"), holding raid composition + buff coverage,
  the enchant/gem audit, and **per-player inspection** (drill into a single raider's gear/enchants/
  parses/activity — a new capability implied by "all the way down to per-player inspection").
- Resulting top-level tabs: **Overview | Composition | Bosses** (names TBD).
- Open questions to resolve while doing this:
  - Where do **Clear Efficiency** and **Output Quality** (cross-boss summaries) live? Options: a
    small section on Bosses, or their own summary area on Overview.
  - The enchant/gem **Audit** is per-player → fits naturally under Composition.
  - This is also the point where the growing client-side JS (tabs within tabs, re-render + state
    preservation) may justify inlining a tiny view lib (Preact + htm) — see the earlier
    "should this be React" discussion. Still keep single-file output.
