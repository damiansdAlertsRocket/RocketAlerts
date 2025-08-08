# scripts/archive_orphans.py
from __future__ import annotations
from pathlib import Path
import re, argparse, shutil

def parse_orphans(report: Path) -> list[Path]:
    txt = report.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"## Orphans.*?$", txt, flags=re.S | re.M)
    if not m:
        return []
    block = m.group(0)
    paths = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("- "):
            p = line[2:].strip()
            if p.endswith(".py"):
                paths.append(Path(p))
    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="audit_report.md")
    ap.add_argument("--root", default=".")
    ap.add_argument("--dest", default="archive")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    report = Path(args.report).resolve()
    dest = (root / args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)

    orphans = parse_orphans(report)
    moved = 0
    for p in orphans:
        src = Path(p)
        if not src.is_absolute():
            src = root / src
        if src.exists():
            rel = src.relative_to(root)
            target = dest / rel.name
            if args.dry_run:
                print(f"[DRY] move {rel} -> {target.relative_to(root)}")
            else:
                shutil.move(str(src), str(target))
                print(f"[OK]  move {rel} -> {target.relative_to(root)}")
                moved += 1
    print(f"\nOsierocone wykryte: {len(orphans)}, przeniesione: {moved}")

if __name__ == "__main__":
    main()
