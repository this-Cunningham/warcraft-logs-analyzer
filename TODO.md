# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> change how a raid leader runs next week — and can they read it and trust it in seconds?

---

## TODO: Parse Spread — remove

> remove parse spread

**Cut reason:** *Silly* — all three conditions met. No decision hangs on it: the floor-spec breakdown ("which specs are anchors?") is already answered, more precisely, by **DPS by Spec** in Execution — a leader who wants to know which specs to coach goes there. The gap shown is noise: median vs floor parse repackages the same `rankPercent` signal the Avg Raid Parse headline already carries. And it was mined because `rankPercent` was already in the parses file, not because a leader was asking for a parse distribution. An EXPERIMENTAL label on a feature that doesn't survive the worth-it test is still a dead-weight block in the Overview.

**Cleanup checklist:**

- `scripts/build_deepdive.py:3215` — delete `def parse_spread(...)` builder function and its docstring
- `scripts/build_deepdive.py:3610` — delete the `parse_spread_payload = parse_spread(...)` call site
- `scripts/build_deepdive.py:4036` — delete the `"parseSpread": parse_spread_payload` key from the DATA dict
- `templates/report.html:490` — remove the `+parseSpreadView(d)` call from the Overview renderer
- `templates/report.html:494–~530` — delete the full `function parseSpreadView(d){...}` block (and any scoped CSS inside it)
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — delete the **Parse Spread** bullet under the Overview section

---

## TODO: Provider Count & Coverage — Bloodlust scope bug (TBC Anniversary)

> bug PROVIDER COUNT & COVERAGE — shaman lust is raidwide in tbc anniversary, not party wide

Accuracy floor violation. The Composition tab's Provider Count & Coverage section currently classifies Bloodlust as `group`-scoped, meaning it treats more Shaman providers as "more groups covered" — a leader reading this could think a second Shaman is needed when one already covers the whole raid. In TBC Anniversary, Bloodlust/Heroism is raid-wide, so the right classification is `raid`-scoped: one provider delivers it in full, and count >1 is a single-point-of-failure note, not a coverage gap. Fix the scope entry for Bloodlust (and verify Heroism) in `PROVIDER_CHECKS` to match Anniversary reality.

---

## TODO: Drums Uptime — remove from Consumables Coverage

> DRUMS UPTIME remove from consumables coverage

**Cut reason:** *Silly / redundant.* No prep decision hangs on it — a leader can’t "fix" drums uptime the way they fix missing flasks; Drums coverage depends on group composition and fight length, not an individual raider showing up ready. It’s already visible in the per-boss **Buff Uptime** sub-tab via `KEY_BUFFS` ("Drums of Battle"), so it’s also *redundant* in Consumables. The hint text on the Coverage section already hedges it as an uptime %, not a prep signal — which is the tell that it doesn’t belong here.

**Cleanup checklist:**

- `scripts/build_deepdive.py:483` — delete `DRUM_NAMES` constant (only used by the drums uptime path)
- `scripts/build_deepdive.py:555–556` — remove `if name in DRUM_NAMES: return "drums"` branch from `_consumable_cat`
- `scripts/build_deepdive.py:582` — delete `drum_upt = []` initialization
- `scripts/build_deepdive.py:595–600` — delete the drums uptime computation block (the `# Drums uptime` comment + loop)
- `scripts/build_deepdive.py:647` — delete `"drumsUptime": iavg(drum_upt)` from the consumable_report DATA dict
- `templates/report.html:628` — remove "Drums shown as uptime" clause from the Consumables Coverage `<span class="hint">`
- `templates/report.html:632` — delete the `acard("Drums Uptime", ...)` render line
- `.claude/skills/warcraft-logs-analyzer/references/report-anatomy.md` — remove the "Drums uptime % = fight-uptime from aggregate Buffs" clause from the Consumables Coverage bullet

---

## TODO: Hit & Expertise — verify accuracy for Feral/Guardian bear tanks

> confirm no bug in Imminent — hit & expertise by raider for calculating beartreebear hit for standard tanking feral/guardian in tbc

Accuracy floor check. The Hit & Expertise view is the one per-player gear fix in Prep — a false flag or a silent miss on a tank directly misleads the leader about what to gem/enchant. The code path for bears looks correct on a read: `_hit_kind("Druid", "Guardian"/"Feral", "tank")` returns "melee" — right, since bears use melee attacks; `SPEC_TALENT_HIT` deliberately omits Feral/Guardian (0 talent hit — correct, bears gear to the 9% cap through gear alone, no standard hit talent); `HIT_CAP["melee"]` = 9% — correct vs a +3 raid boss; and `stat_audit` iterates the "tanks" bucket in `playerdetails.json` so Beartreebear is included.

**The one thing to verify in the live report:** whether `spec_map` resolves Beartreebear to "Guardian" or "Feral" (both miss `SPEC_TALENT_HIT`, giving 0 talent hit — the correct answer either way), and whether their effective hit reads plausibly against the 9% cap. Open the rendered Hit & Expertise table in the Imminent report and spot-check Beartreebear's gear/talent/effective columns.
