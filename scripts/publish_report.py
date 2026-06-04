"""
Publish a report HTML file to docs/ for GitHub Pages.

Usage:
    python scripts/publish_report.py reports/my-report.html
    python scripts/publish_report.py              # publishes the newest file in reports/
"""
import sys, os, shutil, json, subprocess, re, hashlib
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def content_hash(path):
    """8-char hash of the report bytes, used as a cache-busting AND deterministic filename suffix.
    Identical report bytes -> identical filename, so re-publishing an unchanged report is a no-op
    (nothing staged -> no commit, no push) — which means CI can republish on every PR push without
    churning the branch or looping. Any template/data change flips the hash and yields a fresh,
    immutable URL, so GitHub Pages / the browser never serve stale bytes. (Replaces the old commit-SHA
    suffix, which changed on every commit even when the report was byte-identical.)"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


# A published filename is "<base>-<hash>.html"; this strips the trailing hash back off for the title
# and to recognise prior versions of the same matchup. 5–12 hex chars (covers the 8-char content hash
# and any legacy commit-SHA / timestamp suffix from before the switch).
_SHA_SUFFIX = re.compile(r"-[0-9a-f]{5,12}$")


def rebuild_index():
    files = sorted(
        [f for f in DOCS.glob("*.html") if f.name != "index.html"],
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

    index_path = DOCS / "index.html"
    src = index_path.read_text(encoding="utf-8")
    blob = json.dumps(reports, ensure_ascii=False)
    src = re.sub(r"/\*__REPORTS__\*/\[.*?\]", f"/*__REPORTS__*/{blob}", src, flags=re.DOTALL)
    index_path.write_text(src, encoding="utf-8")
    print(f"Index updated ({len(reports)} report(s))")


def main():
    if len(sys.argv) >= 2:
        src = Path(sys.argv[1])
    else:
        candidates = sorted(REPORTS.glob("*.html"), key=lambda f: f.stat().st_mtime)
        if not candidates:
            sys.exit("No reports found in reports/. Pass a path explicitly.")
        src = candidates[-1]
        print(f"Using newest report: {src.name}")

    if not src.exists():
        sys.exit(f"File not found: {src}")

    # Cache-busting filename: "<base>-<hash>.html". Prune any prior version of THIS matchup (the bare
    # name or an older hash) so docs/ keeps one current file per matchup instead of accumulating stale
    # duplicates — each still gets a fresh URL, so caches never serve old bytes. (When the content is
    # unchanged the recreated file is byte-identical at the same path, so git stages nothing.)
    base = _SHA_SUFFIX.sub("", src.stem)
    for old in list(DOCS.glob(f"{base}.html")) + list(DOCS.glob(f"{base}-*.html")):
        if _SHA_SUFFIX.search(old.stem) or old.stem == base:
            old.unlink()
            print(f"Removed stale {old.name}")
    dest = DOCS / f"{base}-{content_hash(src)}.html"
    shutil.copy2(src, dest)
    print(f"Copied -> {dest}")

    rebuild_index()

    # Commit and push
    os.chdir(ROOT)
    subprocess.run(["git", "add", "docs/"], check=True)
    # If nothing is staged (re-publishing the identical file at the same commit, e.g. a CI re-run),
    # skip the commit/push cleanly instead of erroring on "nothing to commit".
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("No changes to publish (docs/ already up to date).")
    else:
        subprocess.run(["git", "commit", "-m", f"docs: publish {dest.name}"], check=True)
        subprocess.run(["git", "push"], check=True)

    # Links. Two facts make the bare Pages URL unreliable as the "view it now" link, and they bite every
    # publish: (1) the report builds its whole body from an inline <script>, so a sandboxed file preview
    # that blocks scripts shows a BLANK page — it must be opened where JS runs (a real browser); (2) Pages
    # builds from the default branch (main), so a report published on a feature branch is NOT on Pages
    # until merged. The fix is raw.githack pinned to the commit we just pushed: it renders the report in a
    # browser IMMEDIATELY, from any branch, no merge — and being commit-pinned it's immutable (never stale).
    owner, repo = "", "warcraft-logs-analyzer"
    try:
        remote = subprocess.run(["git", "remote", "get-url", "origin"],
                                capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
        m = re.search(r"[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", remote)
        if m:
            owner, repo = m.group(1).lower(), m.group(2)
    except (OSError, subprocess.CalledProcessError):
        pass

    def _git(*args):
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    sha, branch = _git("rev-parse", "HEAD"), _git("rev-parse", "--abbrev-ref", "HEAD")

    if owner and sha:
        # The link to actually click — works now, no merge, renders in-browser (raw.githack production CDN).
        print(f"\n▶ View now (no merge needed):\n  https://raw.githack.com/{owner}/{repo}/{sha}/docs/{dest.name}")
    pages_base = f"https://{owner}.github.io/{repo}" if owner else "(set GitHub Pages owner)"
    merged_note = "" if branch in ("main", "master", "") else f" — only after '{branch}' is merged to main"
    print(f"\nOn GitHub Pages{merged_note}:\n  {pages_base}/{dest.name}\n  index: {pages_base}/")


if __name__ == "__main__":
    main()
