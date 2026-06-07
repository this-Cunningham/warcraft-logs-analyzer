# CLAUDE.md

Project guidance for Claude Code working in this repo.

## Always keep the live report current

**Whenever a change affects the report (the analyzer pipeline, the builder, the
template, the positioning code, or the cached data), rebuild and PUBLISH it so the
live URL reflects the change — don't leave the published report stale.**

After the change is on `main`, run:

```
# 1. rebuild the pinned comparison report from cached data
python3 .claude/skills/warcraft-logs-analyzer/scripts/compare_raids.py \
  --ours-url   https://fresh.warcraftlogs.com/reports/pkHqfrBbhQK9GP1a \
  --theirs-url https://fresh.warcraftlogs.com/reports/BxZPrhXYDfL1VKm8 \
  --no-open

# 2. publish the freshly built HTML to docs/ on main (self-contained; pushes itself)
python3 scripts/publish_report.py reports/imminent-vs-pneumonoultramicroscopic.html
```

`publish_report.py` builds the publish commit off a freshly-fetched `origin/main`
in a throwaway detached worktree and pushes straight to `origin/main`, so the
published artifact is the exact HTML you just built. It prints the live
`raw.githack` (immediate) and GitHub Pages (after the next Pages build) URLs —
share the URL after publishing. Re-publishing identical bytes is a no-op.

If a change altered the fetch pipeline or the cached report data, re-fetch first
(`fetch_report.py --positions-only ...` for the per-boss extras, or a full fetch)
and regenerate the cached `data/<code>/` artifacts before rebuilding.
