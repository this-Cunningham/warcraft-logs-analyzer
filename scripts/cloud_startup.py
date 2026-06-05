"""cloud_startup.py — pre-generate a benchmark comparison report from two PINNED report codes.

Meant to run when a Claude Code cloud container starts: it fetches both reports and produces a fresh
self-contained HTML report (our raid + a top-world benchmark), so a developer has real data and a real
artifact to inspect and verify changes against from the first moment of the session.

    python scripts/cloud_startup.py             # fetch both reports and build the report
    python scripts/cloud_startup.py --no-open   # don't launch a browser (headless containers)

The two report URLs below are pinned — swap them to retarget at a different raid / benchmark pair.
This is the pipeline/convenience layer only; nothing in the *report* changes here. It just runs the
same deterministic `compare_raids` flow the skill uses, with the codes filled in.
"""

import argparse
import os
import sys

# The skill's scripts live under .claude/skills/...; add that dir so we can import the pipeline.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".claude", "skills", "warcraft-logs-analyzer", "scripts"))

# Run from the repo root regardless of the caller's cwd. The cloud setup script invokes us from
# the environment's working_dir (e.g. /home/user, the repo's *parent*), and the pipeline resolves
# both its inputs and its output dir relative to cwd (lib.find_repo_root walks up for a .git). Without
# this, output silently lands outside the repo. Anchoring to ROOT makes invocation cwd-independent.
os.chdir(ROOT)

import compare_raids  # noqa: E402

# --- PINNED REPORTS (swap these to retarget) ---------------------------------------------------------
# These two reports' fetched data is committed under data/ (via an allow-list in .gitignore) so a fresh
# clone / new worktree / cloud session starts with a WARM cache and /startup reads it off disk instead of
# cold-fetching it. If you retarget these URLs, keep that allow-list in sync with the new report codes and
# drop the old data/<code>/ folders + data/<code>-parses.json — otherwise the stale cache lingers in git.
OURS_URL = "https://fresh.warcraftlogs.com/reports/pkHqfrBbhQK9GP1a"      # our raid
THEIRS_URL = "https://fresh.warcraftlogs.com/reports/BxZPrhXYDfL1VKm8"    # top-world benchmark


def main(argv=None):
    p = argparse.ArgumentParser(description="Pre-generate a report from two pinned report codes.")
    p.add_argument("--no-open", action="store_true", help="don't launch a browser (headless containers)")
    args = p.parse_args(argv)

    # Just run the deterministic fetch+build pipeline with the pinned codes — same as:
    #   python compare_raids.py --ours-url OURS_URL --theirs-url THEIRS_URL
    cr_args = ["--ours-url", OURS_URL, "--theirs-url", THEIRS_URL]
    if args.no_open:
        cr_args.append("--no-open")
    compare_raids.main(cr_args)


if __name__ == "__main__":
    main()
