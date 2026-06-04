# TODO

Near-term items for the Warcraft Logs analyzer. Longer-term ideas go in [`BACKLOG.md`](BACKLOG.md). Newest ideas at the bottom of each section.

> Before adding or building anything here, route it through the product
> principles in [`PRODUCT_MANAGER_SOUL.md`](PRODUCT_MANAGER_SOUL.md) — does it
> reveal an actionable gap, honestly, at a glance?

---

## TODO: Phase markers as side notches on DPS timeline

> in this per boss breakdown Raid DPS over time -- where we have the vertical dashed lines representing phases -- can we make them just small notches at the top/bottom of the screen - color coded to match my raid, and then color coded phases for the benchmark -- since the timelines can be way different -- my phases dont line up with benchmark phases -- instead of full vertical dashed lines -- just put my raids as small notches on the bottom of the timeline, and the benchmarks as small notches on the top part of the timeline

The full-height dashed lines falsely imply the two raids' timelines are aligned — a honesty issue when a 7-minute kill and a 5-minute kill have fundamentally different phase maps. Collapsing to edge notches (ours at bottom, theirs at top, each color-matched to its raid's line) preserves the *when* dimension for each side without the misleading overlap. This directly serves the "phases" cut of the DPS-over-time story — one level deeper than the aggregate, and honest about independent timelines.
