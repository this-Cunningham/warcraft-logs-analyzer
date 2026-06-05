"""
Publish a report HTML file to docs/ on the canonical publish branch (main), for GitHub Pages.

Every published artifact lands in the SAME absolute place — the `docs/` directory on `main` — no
matter which worktree or feature branch you invoke this from. The publish commit is built on a
throwaway DETACHED worktree pinned to a freshly-fetched `origin/main`, then pushed straight to
`origin/main`. Consequences of that design, all deliberate:
  * It never touches whatever you have checked out (a feature branch, a dirty main worktree, etc.).
  * It does not depend on your local `main` being clean or up to date — it builds off origin/main.
  * Reports go live on GitHub Pages with no merge/PR; the raw.githack link below renders immediately.

Usage:
    python scripts/publish_report.py reports/my-report.html
    python scripts/publish_report.py              # publishes the newest file in reports/
"""
import sys, shutil, json, subprocess, re, hashlib, tempfile
from pathlib import Path
from datetime import datetime

PUBLISH_BRANCH = "main"      # the single, canonical branch every published artifact goes to
DOCS_SUBDIR = "docs"         # ...and the single directory within it

SCRIPT_DIR = Path(__file__).resolve().parent

# Windows consoles default to cp1252, which can't encode the ▶ marker (or unicode in report titles).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _git(*args, cwd, check=True):
    """Run a git command. cwd is required so we are never at the mercy of the process working dir."""
    return subprocess.run(["git", *args], cwd=str(cwd), check=check, capture_output=True, text=True)


def main_repo_root():
    """Absolute path to the PRIMARY worktree (the one whose .git IS the common dir), regardless of
    which linked worktree we were invoked from. This anchors `reports/` (the default source) to one
    canonical location instead of the current worktree's."""
    common = _git("rev-parse", "--git-common-dir", cwd=SCRIPT_DIR).stdout.strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = SCRIPT_DIR / common_path
    return common_path.resolve().parent


MAIN_REPO = main_repo_root()
REPORTS = MAIN_REPO / "reports"

# A published filename is "<base>-<hash>.html"; this strips the trailing hash back off for the title
# and to recognise prior versions of the same matchup. 5–12 hex chars (covers the 8-char content hash
# and any legacy commit-SHA / timestamp suffix from before the switch).
_SHA_SUFFIX = re.compile(r"-[0-9a-f]{5,12}$")


def content_hash(path):
    """8-char hash of the report bytes, used as a cache-busting AND deterministic filename suffix.
    Identical report bytes -> identical filename, so re-publishing an unchanged report is a no-op
    (nothing staged -> no commit, no push). Any template/data change flips the hash and yields a
    fresh, immutable URL, so GitHub Pages / the browser never serve stale bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


def rebuild_index(docs_dir):
    files = sorted(
        [f for f in docs_dir.glob("*.html") if f.name != "index.html"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    reports = []
    for f in files:
        # Human title from the filename, with the cache-busting SHA suffix stripped off.
        base = _SHA_SUFFIX.sub("", f.stem)
        title = base.replace("-", " ").title()
        date = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        reports.append({"file": f.name, "title": title, "date": date})

    index_path = docs_dir / "index.html"
    src = index_path.read_text(encoding="utf-8")
    blob = json.dumps(reports, ensure_ascii=False)
    src = re.sub(r"/\*__REPORTS__\*/\[.*?\]", f"/*__REPORTS__*/{blob}", src, flags=re.DOTALL)
    index_path.write_text(src, encoding="utf-8")
    print(f"Index updated ({len(reports)} report(s))")


def resolve_source():
    if len(sys.argv) >= 2:
        src = Path(sys.argv[1]).resolve()
    else:
        candidates = sorted(REPORTS.glob("*.html"), key=lambda f: f.stat().st_mtime)
        if not candidates:
            sys.exit(f"No reports found in {REPORTS}. Pass a path explicitly.")
        src = candidates[-1]
        print(f"Using newest report: {src.name}")
    if not src.exists():
        sys.exit(f"File not found: {src}")
    return src


def _remove_worktree(path):
    """Best-effort teardown of the ephemeral publish worktree, so a crashed run never wedges a later
    one. `worktree remove` unregisters it; the rmtree + prune mop up if the dir lingered."""
    _git("worktree", "remove", "--force", str(path), cwd=MAIN_REPO, check=False)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    _git("worktree", "prune", cwd=MAIN_REPO, check=False)


def publish(src):
    """Build the publish commit on a detached worktree pinned to origin/PUBLISH_BRANCH and push it.
    Returns (dest_filename, commit_sha, pushed)."""
    print(f"Fetching origin/{PUBLISH_BRANCH}...")
    _git("fetch", "origin", PUBLISH_BRANCH, cwd=MAIN_REPO)

    tmp = Path(tempfile.mkdtemp(prefix="wcl-publish-"))
    wt = tmp / "wt"   # git worktree add wants a non-existent path
    try:
        # Detached (a commit, not the branch) so this works even though `main` is checked out in the
        # primary worktree — git refuses to check the same branch out twice, but a detached commit is fine.
        _git("worktree", "add", "--detach", str(wt), f"origin/{PUBLISH_BRANCH}", cwd=MAIN_REPO)
        docs = wt / DOCS_SUBDIR
        docs.mkdir(exist_ok=True)

        # Cache-busting filename "<base>-<hash>.html". Prune any prior version of THIS matchup (bare
        # name or an older hash) so docs/ keeps one current file per matchup instead of accumulating
        # stale duplicates. Unchanged content -> byte-identical file at the same path -> nothing staged.
        base = _SHA_SUFFIX.sub("", src.stem)
        for old in list(docs.glob(f"{base}.html")) + list(docs.glob(f"{base}-*.html")):
            if _SHA_SUFFIX.search(old.stem) or old.stem == base:
                old.unlink()
                print(f"Removed stale {old.name}")
        dest = docs / f"{base}-{content_hash(src)}.html"
        shutil.copy2(src, dest)
        print(f"Copied -> docs/{dest.name}")

        rebuild_index(docs)

        _git("add", "docs", cwd=wt)
        if _git("diff", "--cached", "--quiet", cwd=wt, check=False).returncode == 0:
            print(f"No changes to publish (docs/ already current on {PUBLISH_BRANCH}).")
            sha = _git("rev-parse", "HEAD", cwd=wt).stdout.strip()
            return dest.name, sha, False

        _git("commit", "-m", f"docs: publish {dest.name}", cwd=wt)
        _git("push", "origin", f"HEAD:{PUBLISH_BRANCH}", cwd=wt)
        sha = _git("rev-parse", "HEAD", cwd=wt).stdout.strip()
        print(f"Pushed to origin/{PUBLISH_BRANCH} ({sha[:7]})")
        return dest.name, sha, True
    finally:
        _remove_worktree(wt)
        shutil.rmtree(tmp, ignore_errors=True)


def print_links(filename, sha, pushed):
    owner, repo = "", "warcraft-logs-analyzer"
    out = _git("remote", "get-url", "origin", cwd=MAIN_REPO, check=False).stdout.strip()
    m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", out)
    if m:
        owner, repo = m.group(1).lower(), m.group(2)

    if owner and sha:
        # Commit-pinned to the main commit we just pushed: renders in a browser IMMEDIATELY (no wait
        # for the Pages build), and being commit-pinned it is immutable / never serves stale bytes.
        print(f"\n▶ View now (commit-pinned, renders in-browser):\n"
              f"  https://raw.githack.com/{owner}/{repo}/{sha}/docs/{filename}")
    pages = f"https://{owner}.github.io/{repo}" if owner else "(set GitHub Pages owner)"
    note = "" if pushed else "  (unchanged — already published)"
    print(f"\nOn GitHub Pages (live after the next Pages build):{note}\n"
          f"  {pages}/{filename}\n  index: {pages}/")


def main():
    src = resolve_source()
    filename, sha, pushed = publish(src)
    print_links(filename, sha, pushed)


if __name__ == "__main__":
    main()
