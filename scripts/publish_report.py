"""
Publish a report HTML file to docs/ for GitHub Pages.

Usage:
    python scripts/publish_report.py reports/my-report.html
    python scripts/publish_report.py              # publishes the newest file in reports/
"""
import sys, os, shutil, json, subprocess, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def rebuild_index():
    files = sorted(
        [f for f in DOCS.glob("*.html") if f.name != "index.html"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    reports = []
    for f in files:
        # Try to extract a human title from the filename
        title = f.stem.replace("-", " ").title()
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

    dest = DOCS / src.name
    shutil.copy2(src, dest)
    print(f"Copied -> {dest}")

    rebuild_index()

    # Commit and push
    os.chdir(ROOT)
    subprocess.run(["git", "add", "docs/"], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"docs: publish {src.name}"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)

    # Print the Pages URL
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "url", "-q", ".url"],
        capture_output=True, text=True,
    )
    repo_url = result.stdout.strip().rstrip("/")
    owner_repo = repo_url.replace("https://github.com/", "")
    owner = owner_repo.split("/")[0].lower()
    pages_base = f"https://{owner}.github.io/warcraft-logs-analyzer"
    print(f"\nReport live at:\n  {pages_base}/{src.name}")
    print(f"\nIndex:\n  {pages_base}/")


if __name__ == "__main__":
    main()
