#!/usr/bin/env python3
import re, sys, shutil
from pathlib import Path
from datetime import datetime
import pandas as pd

ROOT = Path(".").resolve()
BACKUP_DIR = ROOT / f"archive/auto_patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDE_DIRS = {
    ".git", "venv", ".venv", "env", "node_modules", "ngrok",
    "data", "assets", "__pycache__", "plots", "reports", "archive",
    "dejavu-fonts-ttf-2.37", "static", "tvdatafeed"
}

ADX_MAP = {"12": "10", "14": "12", "16": "14", "18": "16", "20": "18"}
RR_FROM = "1.8"
RR_TO = "1.6"

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

def soften_adx_and_rr(txt: str) -> str:
    out = txt

    # ADX – porównania typu: adx < 10
    adx_cmp = re.compile(r"(\b(?:adx|ADX)\b[^\n<>]{0,80}?<\s*)(12|14|16|18|20)(\.\d+)?\b")
    def repl_cmp(m):
        left, num, dec = m.group(1), m.group(2), m.group(3) or ""
        return f"{left}{ADX_MAP.get(num, num)}{dec}"
    out = adx_cmp.sub(repl_cmp, out)

    # ADX – stałe/zmienne: ADX_MIN = 16 / adx_threshold: 18
    out = re.sub(
        r"(\b(?:ADX|adx)_(?:MIN|TH(?:RESH(?:OLD)?)?)\s*[:=]\s*)(12|14|16|18|20)(?:\.0)?\b",
        lambda m: f"{m.group(1)}{ADX_MAP[m.group(2)]}", out
    )

    # ADX – mapy timeframe: {"1m":12, "15m":14, "1h":16, "4h":18, "1d":20}
    def repl_tf(m):
        pre, val, dec = m.group(1), m.group(2), m.group(3) or ""
        return f"{pre}{ADX_MAP.get(val, val)}{dec}"
    out = re.sub(
        r'(\b["\'](?:1m|5m|15m|1h|4h|1d)["\']\s*:\s*)(12|14|16|18|20)(\.\d+)?\b',
        repl_tf, out
    )

    # RR – porównania rr < 1.6
    out = re.sub(r"(\brr\s*<\s*)1\.8\b", r"\g<1>1.6", out, flags=re.IGNORECASE)

    # RR – ustawienia/stałe
    out = re.sub(
        r"(\b(?:rr_min|min_rr|rr_threshold|RR_MIN|RISK_REWARD_MIN)\s*[:=]\s*)1\.8\b",
        r"\g<1>1.6", out
    )

    # RR – w dict/json/yaml-likes
    out = re.sub(
        r'(\b["\'](?:rr|min_rr|rr_min|rr_threshold|risk_reward_min|RR_MIN|RISK_REWARD_MIN)["\']\s*:\s*)1\.8\b',
        r"\g<1>1.6", out, flags=re.IGNORECASE
    )

    # RR – literalny tekst
    out = out.replace("rr<1.6", "rr<1.6").replace("RR<1.6", "RR<1.6")
    return out

def patch_flask_debug(txt: str) -> str:
    txt = re.sub(r"debug\s*=\s*True", "debug=False", txt)
    txt = re.sub(r"use_reloader\s*=\s*True", "use_reloader=False", txt)

    def add_defaults(m):
        inside = m.group(1)
        new_inside = inside
        if "debug=" not in inside:
            new_inside += (", " if inside.strip() else "") + "debug=False"
        if "use_reloader=" not in inside:
            new_inside += (", " if new_inside.strip() else "") + "use_reloader=False"
        return f"app.run({new_inside})"
    return re.sub(r"app\.run\(\s*(.*?)\)", add_defaults, txt, flags=re.DOTALL)

def ensure_twilio_quiet_in_scheduler(path: Path, txt: str) -> str:
    if path.name != "scheduler.py":
        return txt
    # usuń duplikaty
    txt = re.sub(r'^\s*logging\.getLogger\(["\']twilio["\']\)\.setLevel\([^)]*\)\s*$', "", txt, flags=re.M)
    lines = txt.splitlines(True)

    # shebang/encoding
    i = 0
    if lines and lines[0].startswith("#!"):
        i += 1
    if i < len(lines) and re.search(r"coding[:=]", lines[i]):
        i += 1

    # import logging (po shebang/encoding)
    import_idx = None
    for idx, ln in enumerate(lines):
        if re.match(r'^\s*import\s+logging\b', ln):
            import_idx = idx
            break
    if import_idx is None:
        lines.insert(i, "import logging\n")
        import_idx = i

    # wstaw getLogger tuż po imporcie
    if not any("getLogger('twilio')" in ln or 'getLogger("twilio")' in ln for ln in lines):
        lines.insert(import_idx + 1, 'logging.getLogger("twilio").setLevel(logging.WARNING)\n')

    return "".join(lines)

def patch_file(p: Path):
    orig = p.read_text(encoding="utf-8", errors="ignore")
    new = orig

    new2 = soften_adx_and_rr(new)
    changed = (new2 != new)
    new = new2

    if p.name in {"webhook_handler.py", "dashboard.py"}:
        new2 = patch_flask_debug(new)
        changed = changed or (new2 != new)
        new = new2

    new2 = ensure_twilio_quiet_in_scheduler(p, new)
    changed = changed or (new2 != new)
    new = new2

    if changed:
        backup(p)
        p.write_text(new, encoding="utf-8")
        return True
    return False

# ==== CSV helpers ====

def _titlecase_cols(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        cl = str(c).lower()
        if cl in ("datetime","date","time","timestamp"): mapping[c] = "Datetime"
        elif cl == "open":   mapping[c] = "Open"
        elif cl == "high":   mapping[c] = "High"
        elif cl == "low":    mapping[c] = "Low"
        elif cl == "close":  mapping[c] = "Close"
        elif cl in ("volume","vol"): mapping[c] = "Volume"
    return df.rename(columns=mapping)

def build_daily_from_local_hourly():
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return 0
    made = 0
    for p1h in sorted(data_dir.glob("*_1h.csv")):
        stem = p1h.stem[:-3]  # bez "_1h"
        p1d = data_dir / f"{stem}_1d.csv"
        if p1d.exists():
            continue
        try:
            df = pd.read_csv(p1h, encoding="utf-8")
        except Exception:
            continue
        cols = {c.lower(): c for c in df.columns}
        tcol = cols.get("datetime") or cols.get("date") or cols.get("time") or cols.get("timestamp")
        ocol = cols.get("open"); hcol = cols.get("high"); lcol = cols.get("low"); ccol = cols.get("close")
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
                df1d = df1d.reset_index()
                # poprawne nagłówki
                df1d = _titlecase_cols(df1d.rename(columns={tcol: "Datetime"}))
                df1d.to_csv(p1d, index=False, encoding="utf-8")
                print(f"[DAILY FIX] Zbudowano {p1d.name} z {p1h.name} ({len(df1d)} świec)")
                made += 1
        except Exception as e:
            print(f"[DAILY FIX] Błąd dla {p1h.name}: {e}")
    return made

def fix_existing_daily_headers():
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return 0
    fixed = 0
    for p in sorted(data_dir.glob("*_1d.csv")):
        try:
            df_sample = pd.read_csv(p, nrows=1, encoding="utf-8")
        except Exception:
            continue
        need = any(col.islower() for col in df_sample.columns) or ("Close" not in df_sample.columns and "close" in [c.lower() for c in df_sample.columns])
        if not need:
            continue
        try:
            df = pd.read_csv(p, encoding="utf-8")
            df = _titlecase_cols(df)
            df.to_csv(p, index=False, encoding="utf-8")
            print(f"[HEADERS] Naprawiono nagłówki: {p.name}")
            fixed += 1
        except Exception as e:
            print(f"[HEADERS] Błąd przy {p.name}: {e}")
    return fixed

def main():
    print("🚀 Rocket bulk fix v2 start...")
    patched = 0
    for p in iter_py_files():
        if patch_file(p):
            patched += 1
            print(f"[PATCHED] {p}")
    print(f"✅ Zmieniono plików: {patched}")

    fixed = fix_existing_daily_headers()
    print(f"✅ Naprawiono nagłówki w istniejących 1D: {fixed}")

    made = build_daily_from_local_hourly()
    print(f"✅ Zbudowano brakujących plików 1D: {made}")

    print(f"🗂️ Backup oryginałów: {BACKUP_DIR}")

if __name__ == "__main__":
    main()
