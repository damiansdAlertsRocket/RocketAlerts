# rocket_audit_all.py
# Audit tool for RocketAlerts — ignores data/__quarantine__ by default,
# supports --exclude patterns, emits a Markdown report, and prints a PL summary.

from __future__ import annotations
import argparse
import sys
import re
import traceback
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Set

# --- Optional CSV checks use pandas if available ---
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

DEFAULT_EXCLUDES = {
    "data/__quarantine__",  # ← always ignored
    "__pycache__",
    ".venv",
    "venv",
    ".git",
}

WARNINGS: List[str] = []
ERRORS: List[str] = []
INFO: List[str] = []

def norm(p: Path) -> str:
    return str(p).replace("\\", "/")

def path_is_excluded(p: Path, extra_excludes: Set[str]) -> bool:
    s = norm(p).lower()
    for pat in (DEFAULT_EXCLUDES | extra_excludes):
        pat = pat.replace("\\", "/").lower()
        # match by substring or glob on filename
        if pat and (pat in s or Path(s).match(pat) or Path(s).name == pat):
            return True
    return False

def iter_py_files(root: Path, extra_excludes: Set[str]) -> List[Path]:
    files = []
    for f in root.rglob("*.py"):
        if path_is_excluded(f, extra_excludes):
            continue
        files.append(f)
    return files

PRINT_RE = re.compile(r'(^|\s)print\s*\(', re.M)

def scan_prints(py: Path):
    try:
        text = py.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    for m in PRINT_RE.finditer(text):
        # try to get line number
        ln = text.count("\n", 0, m.start()) + 1
        WARNINGS.append(f"- [WARNING] {norm(py)}:{ln}: print() w kodzie bibliotecznym – rozważ logging.")

IMPORT_RE = re.compile(r'^\s*(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+))', re.M)

def discover_modules(py_files: List[Path], root: Path) -> Tuple[Set[str], Set[str]]:
    """Return (all_module_stems, used_module_stems). Very simple heuristic."""
    all_stems: Set[str] = set()
    for f in py_files:
        if f.name == "__init__.py":
            continue
        all_stems.add(f.stem)

    used: Set[str] = set()
    for f in py_files:
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in IMPORT_RE.finditer(t):
            mod = m.group(1) or m.group(2) or ""
            # take last segment as stem heuristic
            stem = mod.split(".")[-1]
            if stem and stem in all_stems:
                used.add(stem)
    return all_stems, used

def list_orphans(py_files: List[Path], root: Path) -> List[str]:
    entry_whitelist = {
        "scheduler", "dashboard", "webhook_handler",
        "rocket_audit_all", "app", "main", "__init__"
    }
    all_stems, used = discover_modules(py_files, root)
    orphans = []
    for f in py_files:
        if f.stem in entry_whitelist:
            continue
        if f.stem not in used:
            orphans.append(norm(f))
    return sorted(orphans)

def csv_checks(root: Path, extra_excludes: Set[str]):
    data_dir = root / "data"
    if not data_dir.exists():
        return
    for csv in data_dir.rglob("*.csv"):
        if path_is_excluded(csv, extra_excludes):
            continue
        rel = norm(csv)
        if pd is None:
            INFO.append(f"- ℹ️ CHECK {rel}: pandas not installed — pomijam sanity-check.")
            continue
        try:
            # robust read
            df = pd.read_csv(csv, encoding="utf-8", engine="python", on_bad_lines="skip")
            rows = len(df)
            anomalies = []
            if rows == 0 or df.shape[1] == 0:
                anomalies.append("empty dataframe")
            # Volume all zeros?
            if "Volume" in df.columns:
                v = pd.to_numeric(df["Volume"], errors="coerce").fillna(0.0)
                if (v == 0).all() and rows > 0:
                    anomalies.append("Volume all zero")
            if anomalies:
                INFO.append(f"- ℹ️ CHECK {rel}: rows {rows} | anomalies: {', '.join(anomalies)}")
            else:
                INFO.append(f"- ℹ️ CHECK {rel}: rows {rows}")
        except Exception as e:
            ERRORS.append(f"- ℹ️ CHECK {rel}: ❌ read error: {str(e).strip().splitlines()[0]}")

def write_report(out_path: Path, project: Path, py_files: List[Path], orphans: List[str]):
    parts: List[str] = []
    parts.append(f"# Audit report — {norm(project)}\n")
    parts.append("## Summary\n")
    parts.append(f"- Python files: **{len(py_files)}**\n")
    parts.append(f"- Warnings: **{len(WARNINGS)}**\n")
    parts.append(f"- Errors: **{len(ERRORS)}**\n")
    parts.append(f"- Osieroconych plików: **{len(orphans)}**\n")

    if WARNINGS:
        parts.append("\n## Warnings\n")
        parts.extend(w + "\n" for w in WARNINGS)

    if ERRORS:
        parts.append("\n## Errors / Read issues\n")
        parts.extend(e + "\n" for e in ERRORS)

    if INFO:
        parts.append("\n## Data checks\n")
        parts.extend(i + "\n" for i in INFO)

    if orphans:
        parts.append("\n## Orphans (heurystyka)\n")
        for o in orphans[:300]:
            parts.append(f"- {o}\n")

    out_path.write_text("".join(parts), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(description="RocketAlerts repo audit")
    ap.add_argument("--project", default=".", help="Ścieżka do projektu (root).")
    ap.add_argument("--out", default="audit_report.md", help="Ścieżka do raportu MD.")
    ap.add_argument("--exclude", action="append", default=[], help="Wzorzec/ścieżka do wykluczenia (można wiele).")
    args = ap.parse_args()

    root = Path(args.project).resolve()
    out_path = Path(args.out).resolve()
    extra_excludes = {e for e in (args.exclude or []) if e}

    print(f"🔎 Start audytu: {norm(root)}")

    py_files = iter_py_files(root, extra_excludes)
    print(f"📦 Znaleziono plików .py: {len(py_files)}")

    # scans
    for py in py_files:
        scan_prints(py)

    # CSV sanity checks (skips data/__quarantine__)
    csv_checks(root, extra_excludes)

    # Orphans
    orphans = list_orphans(py_files, root)

    # Report
    write_report(out_path, root, py_files, orphans)
    print(f"📝 Raport zapisany: {norm(out_path)}")
    print(f"✅ Zakończono. Ostrzeżeń: {len(WARNINGS)}, błędów: {len(ERRORS)}, osieroconych: {len(orphans)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print("✖ Nieoczekiwany błąd audytu:", e)
        traceback.print_exc()
        sys.exit(1)
