#!/usr/bin/env python3
import re, sys, shutil, logging
from pathlib import Path
from datetime import datetime
import pandas as pd

ROOT = Path(".").resolve()
BACKUP_DIR = ROOT / f"archive/auto_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git", "venv", ".venv", "env", "node_modules", "ngrok",
    "data", "assets", "__pycache__", "plots", "reports", "archive",
    "dejavu-fonts-ttf-2.37", "static", "tvdatafeed" # vendor
}

def iter_py_files():
    for p in ROOT.rglob("*.py"):
        parts = set(p.relative_to(ROOT).parts)
        if parts & EXCLUDE_DIRS:
            continue
        yield p

def backup(p: Path):
    rel = p.relative_to(ROOT)
    dst = BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(p, dst)

def patch_text_adx_rr(txt: str):
    """
    - ADX thresholds: 12->10, 14->12, 16->14, 18->16, 20->18
    - RR threshold: 1.8 -> 1.6
    """
    mapping = { "12": "10", "14": "12", "16": "14", "18": "16", "20": "18" }

    def repl_adx(m):
        left = m.group(1)
        num = m.group(2)
        dec = m.group(3) or ""
        new = mapping.get(num, num)
        # zachowaj .0 jeśli było
        if dec:
            return f"{left}{new}{dec}"
        # zachowaj brak .0 jeśli nie było
        return f"{left}{new}"

    # <adx ... < N> (również ADX). Działamy tylko na porównaniach "mniejsze niż".
    # Przykłady łapane: adx<10, ADX < 12.0, adx_val  < 16
    adx_pat = re.compile(r"(\b(?:adx|ADX)\b[^\n<>]{0,40}?<\s*)(12|14|16|18|20)(\.\d+)?\b")
    txt = adx_pat.sub(repl_adx, txt)

    # RR 1.8 -> 1.6 (w porównaniach i ustawieniach)
    txt = re.sub(r"(\brr\s*<\s*)1\.8\b", r"\g<1>1.6", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(\brr_min\s*=\s*)1\.8\b", r"\g<1>1.6", txt, flags=re.IGNORECASE)
    # również w komunikatach typu "rr<1.6"
    txt = txt.replace("rr<1.6", "rr<1.6").replace("RR<1.6", "RR<1.6")

    return txt

def patch_flask_debug(txt: str):
    # debug=True -> False, use_reloader=True -> False
    txt = re.sub(r"debug\s*=\s*True", "debug=False", txt)
    txt = re.sub(r"use_reloader\s*=\s*True", "use_reloader=False", txt)

    # Jeżeli jest app.run( ... ) bez parametrów debug/loader – dopisz bezpiecznie.
    def add_defaults(m):
        inside = m.group(1)
        new_inside = inside
        if "debug=" not in inside:
            new_inside += (", " if inside.strip() else "") + "debug=False"
        if "use_reloader=" not in inside:
            new_inside += (", " if new_inside.strip() else "") + "use_reloader=False"
        return f"app.run({new_inside})"
    txt = re.sub(r"app\.run\(\s*(.*?)\)", add_defaults, txt, flags=re.DOTALL)
    return txt

def ensure_twilio_quiet_in_scheduler(path: Path, txt: str):
    if path.name != "scheduler.py":
        return txt
    if "import logging" not in txt:
        txt = "import logging\n" + txt
    if 'logging.getLogger("twilio")' not in txt:
        # wstrzyknij tuż po importach
        lines = txt.splitlines(True)
        ins = 0
        while ins < len(lines) and (lines[ins].strip().startswith("import") or lines[ins].strip().startswith("from")):
            ins += 1
        lines.insert(ins, 'logging.getLogger("twilio").setLevel(logging.WARNING)\n')
        txt = "".join(lines)
    return txt

def patch_file(p: Path):
    orig = p.read_text(encoding="utf-8", errors="ignore")
    new = orig

    # 1) ADX / RR
    new2 = patch_text_adx_rr(new)
    changed = (new2 != new)
    new = new2

    # 2) Flask debug OFF w znanych plikach
    if p.name in {"webhook_handler.py", "dashboard.py"}:
        new2 = patch_flask_debug(new)
        changed = changed or (new2 != new)
        new = new2

    # 3) Twilio logger OFF w scheduler.py
    new2 = ensure_twilio_quiet_in_scheduler(p, new)
    changed = changed or (new2 != new)
    new = new2

    if changed:
        backup(p)
        p.write_text(new, encoding="utf-8")
        return True
    return False

def build_daily_from_local_hourly():
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return 0

    made = 0
    # Zbierz wszystkie *_1h.csv i sprawdź odpowiadające *_1d.csv
    for p1h in sorted(data_dir.glob("*_1h.csv")):
        stem = p1h.stem[:-3]  # utnie "_1h"
        p1d = data_dir / f"{stem}_1d.csv"
        if p1d.exists():
            continue
        # pomiń indeksy gdzie i tak już mamy 1d z providera i nie chcemy podmieniać
        try:
            df = pd.read_csv(p1h, encoding="utf-8")
        except Exception:
            continue
        # heurystyka kolumn
        cols = {c.lower(): c for c in df.columns}
        # obsłuż kilka możliwych nazw
        tcol = cols.get("datetime") or cols.get("date") or cols.get("time") or cols.get("timestamp")
        ocol = cols.get("open")
        hcol = cols.get("high")
        lcol = cols.get("low")
        ccol = cols.get("close")
        vcol = cols.get("volume") or cols.get("vol")

        if not (tcol and ocol and hcol and lcol and ccol):
            continue

        try:
            df[tcol] = pd.to_datetime(df[tcol], utc=True, errors="coerce")
            df = df.dropna(subset=[tcol]).set_index(tcol).sort_index()
            agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
            if vcol:
                agg["volume"] = "sum"
                df = df.rename(columns={ocol:"open", hcol:"high", lcol:"low", ccol:"close", vcol:"volume"})
            else:
                df = df.rename(columns={ocol:"open", hcol:"high", lcol:"low", ccol:"close"})
            df1d = df.resample("1D").agg(agg).dropna(how="any")
            if not df1d.empty:
                df1d.reset_index().rename(columns={ "index":"datetime"}).to_csv(p1d, index=False, encoding="utf-8")
                print(f"[DAILY FIX] Zbudowano {p1d.name} z {p1h.name} ({len(df1d)} świec)")
                made += 1
        except Exception as e:
            print(f"[DAILY FIX] Błąd dla {p1h.name}: {e}")
    return made

def main():
    print("🚀 Rocket bulk fix start...")
    patched = 0
    for p in iter_py_files():
        if patch_file(p):
            patched += 1
            print(f"[PATCHED] {p}")

    print(f"✅ Zmieniono plików: {patched}")

    # Post-fix: dobuduj brakujące 1D z lokalnych 1H
    made = build_daily_from_local_hourly()
    print(f"✅ Zbudowano brakujących plików 1D: {made}")

    print(f"🗂️ Backup oryginałów: {BACKUP_DIR}")

if __name__ == "__main__":
    main()
