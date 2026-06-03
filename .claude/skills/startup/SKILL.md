---
name: startup
description: Pre-generate the pinned benchmark comparison report by running scripts/cloud_startup.py, then surface the resulting HTML artifact. Use at the start of a session to get real data + an inspectable report ready, or whenever the user types `/startup`.
model: sonnet
allowed-tools: Bash, SendUserFile
---

# startup

Run the deterministic benchmark pipeline and hand back the artifact. This is the
on-demand equivalent of the cloud environment's setup script — reliable because
it runs inside the interactive session, where the `WCL_CLIENT_ID` /
`WCL_CLIENT_SECRET` credentials are present and the repo is fully checked out.

## Steps

1. **Run the pipeline from the repo root** (the script anchors its own cwd, but
   running from root keeps output predictable). Capture output to a log:

   ```bash
   python3 scripts/cloud_startup.py --no-open 2>&1 | tee /tmp/cloud_startup.log
   ```

2. **Check the exit status.** The pinned reports are fetched live from the
   Warcraft Logs API, so this takes ~30-60s.
   - On success the log ends with `Report: .../reports/<slug>.html`.
   - If it fails with `Missing credentials`, the `WCL_CLIENT_ID` /
     `WCL_CLIENT_SECRET` env vars aren't set in this session — report that and
     stop; there's nothing to generate without them.
   - For any other failure, surface the last ~15 lines of the log.

3. **Surface the artifact.** Locate the generated file under `reports/`
   (`ls -t reports/*.html | head -1`) and send it with `SendUserFile` so the
   user can open it directly. Mention the matchup and shared-boss count from the
   log.

## Notes

- The two report codes are pinned inside `scripts/cloud_startup.py`. To retarget
  a different raid/benchmark pair, edit the `OURS_URL` / `THEIRS_URL` constants
  there (or run `compare_raids.py --ours-url ... --theirs-url ...` directly).
- `reports/` and `data/` are gitignored — the artifact lives only in the current
  container and is regenerated each run.
