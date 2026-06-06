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
