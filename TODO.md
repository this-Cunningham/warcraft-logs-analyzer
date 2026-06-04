# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

_(No open items — the last batch shipped. Add new ideas below.)_

---

_Last pass shipped (the whole prior TODO batch):_
_**(1) In-Combat matrix — fixed the 5-ability Casts-table cap that truncated consumables:**_
_mana-potion/healthstone usage now reads from cast EVENTS (untruncated), pre-bucketed per source in_
_`incombat-<enc>.json` by `fetch_report._incombat_casts`; dropped the unused Health Potion column._
_**(2) Optimize tab — rebuilt PER BOSS, apples-to-apples + form/role-aware:** every raider's cast mix is_
_now benchmarked against the same-faction world best on that SAME boss (3-level class→spec→boss tabs);_
_a raider only appears on a boss where they actually played that spec's role, and a Feral whose CASTS are_
_bear-dominant is excluded from the cat-DPS benchmark (no more bear-vs-cat phantom 55% gap)._
_**(3) Roster role** now follows the majority (most-frequent) role like spec does (`primary_role_map`),_
_so a one-off heal no longer mislabels a DPS — fixes the prep audit, consumable labels, and table splits._
_**(4) Leaked Interrupts** now require a REAL interrupt kick as proof (CC like Polymorph is discounted via_
_`_real_interrupt_kicks`), plus an auto-attack name block — "Shoot" kicked only by a Poly no longer leaks._
_**(5) Trash zone filter** now keeps only zones the raid actually killed a boss in (`boss_kill_zones` +_
_`gameZone` on kills), so outdoor trash WCL mis-tags (e.g. "Isle of Quel'Danas") is dropped from the hint._
_**(6) Prep matrix** no longer flags a missing guardian elixir red for a DPS with a battle elixir (battle is_
_the only throughput elixir for them); healers/tanks still need the full flask-or-pair._
_**(7) "What's Killing Us"** now: states it's KILL-PULL deaths only; names the SOURCE MOB when an add (not_
_the boss) landed the blow ("Arcing Smash (Coilfang Guardian)"); and breaks out ONE ROW PER BOSS instead_
_of pooling a cause across the tier. (Also fixed `_death_source_mob` to leave "Environment" unnamed.)_
_Earlier: removed the shaded edge-fade on scrolling tables, clarified the "Total Boss Kill Time" label,_
_converted the remaining five sections to mirrored-bar layout, and dropped the benchmark name to 8 chars._
