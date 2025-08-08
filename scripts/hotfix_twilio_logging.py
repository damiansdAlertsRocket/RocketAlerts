#!/usr/bin/env python3
import re
from pathlib import Path

p = Path("scheduler.py")
src = p.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines(True)

# 1) usuń istniejące wywołania getLogger("twilio") żeby nie dublować
rgx_tw = re.compile(r'^\s*logging\.getLogger\(["\']twilio["\']\)\.setLevel\([^)]*\)\s*$', re.M)
src_wo = rgx_tw.sub("", src)
lines = src_wo.splitlines(True)

# 2) znajdź miejsce po shebang/encoding
i = 0
if lines and lines[0].startswith("#!"):
    i += 1
if i < len(lines) and "coding:" in lines[i]:
    i += 1

# 3) upewnij się, że jest import logging (jeśli nie – wstaw)
import_idx = None
for idx, ln in enumerate(lines):
    if re.match(r'^\s*import\s+logging\b', ln):
        import_idx = idx
        break
if import_idx is None:
    lines.insert(i, "import logging\n")
    import_idx = i

# 4) wstaw getLogger tuż po linii z import logging
insert_after = import_idx + 1
lines.insert(insert_after, 'logging.getLogger("twilio").setLevel(logging.WARNING)\n')

p.write_text("".join(lines), encoding="utf-8")
print("✅ Naprawiono kolejność importów i logger Twilio w scheduler.py")
