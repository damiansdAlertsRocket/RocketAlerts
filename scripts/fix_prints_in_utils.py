#!/usr/bin/env python3
import re, sys
from pathlib import Path

ROOT = Path(".")
TARGETS = list((ROOT / "utils").glob("*.py"))

def ensure_logger(src: str) -> str:
    if "logging.getLogger(__name__)" in src:
        return src
    lines = src.splitlines(True)
    i = 0
    if lines and lines[0].startswith("#!"):
        i += 1
    if i < len(lines) and "coding:" in lines[i]:
        i += 1
    inject = "import logging\nlogger = logging.getLogger(__name__)\n"
    lines[i:i] = [inject]
    return "".join(lines)

def decide_level(line: str) -> str:
    s = line.lower()
    if "❌" in line or "błąd" in s or "error" in s:
        return "error"
    if "⚠️" in line or "warn" in s or "brak" in s:
        return "warning"
    return "info"

def replace_prints(src: str) -> str:
    out = []
    for line in src.splitlines(True):
        if "print(" in line:
            lvl = decide_level(line)
            line = re.sub(r"(^[ \t]*)print\s*\(", rf"\1logger.{lvl}(", line)
        out.append(line)
    return "".join(out)

changed = 0
for p in TARGETS:
    if p.name == "__init__.py":
        continue
    txt = p.read_text(encoding="utf-8", errors="ignore")
    if "print(" not in txt:
        continue
    new = ensure_logger(replace_prints(txt))
    if new != txt:
        p.write_text(new, encoding="utf-8")
        print(f"patched: {p}")
        changed += 1

print(f"\n✅ Patched files: {changed}")
