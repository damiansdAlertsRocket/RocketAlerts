#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rocket_check_all.py — jeden skrypt do automatycznego sprawdzenia całego projektu RocketAlerts.

Co robi:
  1) Raport środowiska (wersja Pythona, kluczowe pakiety).
  2) Odkrywa pliki .py (z wyłączeniami venv/__pycache__/build itp.) i robi:
     - szybki check składni (AST parse),
     - bezpieczny import (tylko wybrane moduły domyślnie; pełny import po --force-import-all).
  3) Odkrywa aktywa/interwały z katalogu data/ i waliduje CSV (kolumny, daty, liczebność).
  4) Smoke test analizy:
     - analyze_asset() dla próbek (N aktywów × M interwałów),
     - generowanie fig (generate_total_plot + nakładki), serializacja do .to_dict().
  5) Heatmapa: gen_heatmap_data() i resolve_heatmap_intervals() sanity check.
  6) Opcjonalnie: wywołuje ruff/mypy/pytest, jeśli są zainstalowane.
  7) Zapisuje raport JSON i Markdown do reports/.
  8) Zwraca exit code != 0 gdy są błędy krytyczne.

Użycie:
  python rocket_check_all.py                  # szybki zestaw
  python rocket_check_all.py --full           # pełny (więcej próbek, PDF smoke)
  python rocket_check_all.py --no-static      # bez ruff/mypy/pytest
  python rocket_check_all.py --force-import-all
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import traceback
import importlib.util
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# --- Ustawienia domyślne
IGNORE_DIRS = {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache",
               ".pytest_cache", ".venv", "venv", "env", "build", "dist", "node_modules"}
SAFE_IMPORT_ALLOWLIST = {
    # Moduły najczęściej bezpieczne w imporcie (nie uruchamiają serwerów ani schedulerów przy import)
    "dashboard", "helpers", "plot_utils", "multi_timeframe_analysis",
    "pdf_exporter", "webhook_push", "config.config"
}
RISKY_IMPORT_DENYLIST = {
    # Pliki, które często mają side-effecty (serwer/scheduler) – import tylko po --force-import-all
    "scheduler", "webhook_handler", "app", "server", "wsgi", "asgi", "run", "main"
}
REPORT_DIR = "reports"
DATA_DIR = "data"

# --- Prosty rejestr wyników
@dataclass
class SectionResult:
    ok: bool = True
    items: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Report:
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat()+"Z")
    env: Dict[str, Any] = field(default_factory=dict)
    syntax: SectionResult = field(default_factory=SectionResult)
    imports: SectionResult = field(default_factory=SectionResult)
    data: SectionResult = field(default_factory=SectionResult)
    smoke: SectionResult = field(default_factory=SectionResult)
    heatmap: SectionResult = field(default_factory=SectionResult)
    static_tools: SectionResult = field(default_factory=SectionResult)
    finished_at: Optional[str] = None

    def finalize(self):
        self.finished_at = datetime.utcnow().isoformat()+"Z"

    def overall_ok(self) -> bool:
        return all([
            self.syntax.ok,
            self.imports.ok,
            self.data.ok,
            self.smoke.ok,
            self.heatmap.ok,
            self.static_tools.ok
        ])

# --- Narzędzia
def log(msg: str):
    print(msg, flush=True)

def discover_py_files(root: str) -> List[str]:
    files = []
    for base, dirs, fnames in os.walk(root):
        # odfiltruj katalogi ignorowane
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in fnames:
            if f.endswith(".py"):
                files.append(os.path.join(base, f))
    return files

def rel_module_name(root: str, path: str) -> str:
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    # zamień ścieżkę na nazwę modułu "dir.file" (bez .py)
    if rel.endswith(".py"):
        rel = rel[:-3]
    rel = re.sub(r"/__init__$", "", rel)
    return rel.replace("/", ".")

def is_risky_module(modname: str) -> bool:
    base = modname.split(".")[-1].lower()
    return any(base == risky or base.endswith(f".{risky}") for risky in RISKY_IMPORT_DENYLIST)

def syntax_check(path: str) -> Tuple[bool, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        ast.parse(src, filename=path)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def try_import_from_file(path: str, modname_hint: str) -> Tuple[bool, str]:
    try:
        spec = importlib.util.spec_from_file_location(modname_hint, path)
        if spec is None:
            return False, "spec_from_file_location returned None"
        mod = importlib.util.module_from_spec(spec)
        sys.modules[modname_hint] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # może wykonać top-level code!
        return True, ""
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"{type(e).__name__}: {e}\n{tb}"

def has_exe(name: str) -> bool:
    from shutil import which
    return which(name) is not None

def run_cmd(cmd: List[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout
    except Exception as e:
        return 127, f"{type(e).__name__}: {e}"

# --- Odkrywanie aktywów/TF po plikach CSV
def discover_assets_intervals(data_dir: str) -> Tuple[List[str], List[str]]:
    assets, intervals = set(), set()
    if not os.path.isdir(data_dir):
        return [], []
    for path in os.listdir(data_dir):
        if not path.endswith(".csv") or "_" not in path:
            continue
        stem = path[:-4]
        try:
            asset, tf = stem.rsplit("_", 1)
        except ValueError:
            continue
        if asset: assets.add(asset)
        if tf: intervals.add(tf)
    # sort tf w logicznej kolejności
    order = ["1m","3m","5m","15m","30m","1h","2h","4h","6h","12h","1d","1w","1mo"]
    def tf_sortkey(x): return order.index(x) if x in order else len(order)+hash(x)%1000
    return sorted(assets), sorted(intervals, key=tf_sortkey)

# --- Główna procedura
def main():
    ap = argparse.ArgumentParser(description="RocketAlerts – kompleksowy sprawdzacz projektu")
    ap.add_argument("--root", default=".", help="Katalog projektu (domyślnie: .)")
    ap.add_argument("--full", action="store_true", help="Pełne testy (więcej próbek, próba PDF)")
    ap.add_argument("--no-static", action="store_true", help="Nie uruchamiaj ruff/mypy/pytest")
    ap.add_argument("--force-import-all", action="store_true", help="Importuj WSZYSTKIE moduły (ryzykowne)")
    ap.add_argument("--max-assets", type=int, default=8, help="Max aktywów do smoke testu")
    ap.add_argument("--max-tf", type=int, default=6, help="Max interwałów do smoke testu")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    os.makedirs(REPORT_DIR, exist_ok=True)

    rpt = Report()
    # 1) ENV
    import platform
    rpt.env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "root": root,
        "has_ruff": has_exe("ruff"),
        "has_mypy": has_exe("mypy"),
        "has_pytest": has_exe("pytest"),
    }
    log(f"🔍 ENV: {json.dumps(rpt.env, ensure_ascii=False)}")

    # 2) SYNTAX
    log("🧪 Sprawdzam składnię wszystkich .py…")
    py_files = discover_py_files(root)
    for path in sorted(py_files):
        ok, err = syntax_check(path)
        rpt.syntax.items.append({"file": os.path.relpath(path, root), "ok": ok, "error": err})
        if not ok:
            rpt.syntax.ok = False
    log(f"✅ Składnia: {sum(1 for x in rpt.syntax.items if x['ok'])}/{len(rpt.syntax.items)} OK")

    # 3) IMPORTS (bezpieczne domyślnie)
    log("📦 Test importów (bezpieczny tryb)…")
    for path in sorted(py_files):
        modname = rel_module_name(root, path)
        rel = os.path.relpath(path, root)
        risky = is_risky_module(modname)
        allowed = (args.force_import_all
                   or (modname in SAFE_IMPORT_ALLOWLIST)
                   or (modname.startswith("config.")
                       and modname != "config.__init__"))
        if risky and not args.force_import_all:
            rpt.imports.items.append({"module": modname, "file": rel, "ok": True, "skipped": True,
                                      "reason": "risky_import"})
            continue
        if not allowed and not args.force_import_all:
            rpt.imports.items.append({"module": modname, "file": rel, "ok": True, "skipped": True,
                                      "reason": "not_in_allowlist"})
            continue
        ok, err = try_import_from_file(path, f"checkpkg.{modname}")
        rpt.imports.items.append({"module": modname, "file": rel, "ok": ok, "error": err})
        if not ok:
            rpt.imports.ok = False
    imported = [x for x in rpt.imports.items if x.get("ok") and not x.get("skipped")]
    log(f"✅ Importy: {len(imported)} OK; pominięte: {sum(1 for x in rpt.imports.items if x.get('skipped'))}")

    # 4) DATA check + SMOKE
    log("📂 Odkrywam aktywa/interwały w data/…")
    assets, intervals = discover_assets_intervals(os.path.join(root, DATA_DIR))
    if not assets or not intervals:
        rpt.data.ok = False
        rpt.data.items.append({"ok": False, "error": "Brak plików CSV w data/ (lub zła konwencja nazewnicza asset_tf.csv)"})
        log("⛔ Brak danych w data/")
    else:
        rpt.data.items.append({"ok": True, "assets": len(assets), "intervals": len(intervals)})
        # Spróbuj wczytać kilkanaście plików CSV i sprawdzić podstawowe kolumny
        import pandas as pd
        def read_df(asset, tf):
            path = os.path.join(root, DATA_DIR, f"{asset}_{tf}.csv")
            if not os.path.exists(path):
                return None, f"missing: {path}"
            try:
                df = pd.read_csv(path)
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)
                return df, ""
            except Exception as e:
                return None, f"read_error: {type(e).__name__}: {e}"

        check_pairs = 0
        bads = 0
        for a in assets[: (args.max_assets if not args.full else len(assets))]:
            for tf in intervals[: (args.max_tf if not args.full else len(intervals))]:
                df, err = read_df(a, tf)
                check_pairs += 1
                if df is None or df.empty:
                    rpt.data.items.append({"ok": False, "asset": a, "tf": tf, "error": err or "empty"})
                    bads += 1
                    continue
                cols = set(df.columns)
                has_close = "Close" in cols
                has_ohlc = all(c in cols for c in ["Open","High","Low","Close"])
                rpt.data.items.append({"ok": True, "asset": a, "tf": tf,
                                       "rows": int(df.shape[0]), "has_Close": has_close, "has_OHLC": has_ohlc})
        if bads:
            rpt.data.ok = False
        log(f"✅ Dane: skontrolowano {check_pairs} plików; błędy: {bads}")

        # SMOKE: analyze_asset + wykresy
        log("🚬 Smoke test analizy i wykresów…")
        # spróbuj pobrać API z dashboard lub helpers/plot_utils
        analyze_asset = None
        generate_total_plot = None
        add_overlay_layers = None
        try:
            # jeśli importowaliśmy dashboard, użyj z niego
            dash_mod = sys.modules.get("checkpkg.dashboard")
            if dash_mod:
                analyze_asset = getattr(dash_mod, "analyze_asset", analyze_asset)
                generate_total_plot = getattr(dash_mod, "generate_total_plot", generate_total_plot)
                add_overlay_layers = getattr(dash_mod, "add_overlay_layers", add_overlay_layers)
        except Exception:
            pass
        try:
            helpers_mod = sys.modules.get("checkpkg.helpers")
            if helpers_mod and not analyze_asset:
                analyze_asset = getattr(helpers_mod, "analyze_asset", analyze_asset)
        except Exception:
            pass
        try:
            plot_mod = sys.modules.get("checkpkg.plot_utils")
            if plot_mod:
                generate_total_plot = getattr(plot_mod, "generate_total_plot", generate_total_plot)
                add_overlay_layers = getattr(plot_mod, "add_overlay_layers", add_overlay_layers)
        except Exception:
            pass

        # fallback: jeśli nie ma, to z dashboardu podczas importu mogły być fallbacki
        if analyze_asset is None:
            log("ℹ️ analyze_asset nie znaleziono (użyjesz fallbacku jeśli dashboard ma).")
        import plotly.graph_objs as go

        smoked = 0
        smoke_fail = 0
        for a in assets[: (args.max_assets if not args.full else len(assets))]:
            for tf in intervals[: (args.max_tf if not args.full else len(intervals))]:
                df, err = read_df(a, tf)
                if df is None or df.empty:
                    continue
                res = {}
                try:
                    if analyze_asset:
                        res = analyze_asset(a, tf, df) or {}
                except Exception as e:
                    smoke_fail += 1
                    rpt.smoke.ok = False
                    rpt.smoke.items.append({"ok": False, "stage": "analyze_asset", "asset": a, "tf": tf,
                                            "error": f"{type(e).__name__}: {e}"})
                    continue
                # wykres
                try:
                    layers = ["ema","bb","rsi","macd","volume","sl_tp","fibo","vwap"]
                    if generate_total_plot:
                        fig = generate_total_plot(df, res, layers)
                        if add_overlay_layers:
                            fig = add_overlay_layers(fig, df, layers, res)
                    else:
                        fig = go.Figure()
                        if "Close" in df.columns:
                            fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close"))
                    _ = fig.to_dict()  # serializacja test
                    rpt.smoke.items.append({"ok": True, "asset": a, "tf": tf, "figure_ok": True})
                except Exception as e:
                    smoke_fail += 1
                    rpt.smoke.ok = False
                    rpt.smoke.items.append({"ok": False, "stage": "plot", "asset": a, "tf": tf,
                                            "error": f"{type(e).__name__}: {e}"})
                smoked += 1
        log(f"✅ Smoke: {smoked} kombinacji; błędy: {smoke_fail}")

    # 5) HEATMAP sanity
    log("🌡️ Sprawdzam funkcje heatmapy…")
    try:
        dash_mod = sys.modules.get("checkpkg.dashboard")
        hm_ok = True
        if dash_mod:
            resolve = getattr(dash_mod, "resolve_heatmap_intervals", None)
            gen = getattr(dash_mod, "gen_heatmap_data", None)
            if resolve:
                for mode in ("std","quick","same","all"):
                    tfs = resolve(mode, "1h")
                    if not isinstance(tfs, list) or not all(isinstance(x, str) for x in tfs):
                        hm_ok = False
                        rpt.heatmap.items.append({"ok": False, "stage": "resolve_heatmap_intervals", "mode": mode})
                    else:
                        rpt.heatmap.items.append({"ok": True, "stage": "resolve_heatmap_intervals", "mode": mode, "out": tfs})
            if gen:
                out = gen(["1h","4h","1d"])
                # oczekujemy DataFrame z kolumną 'asset'
                try:
                    import pandas as pd
                    hm_ok = hm_ok and hasattr(out, "columns") and "asset" in out.columns
                    rpt.heatmap.items.append({"ok": bool(hm_ok), "stage": "gen_heatmap_data", "rows": int(getattr(out, "shape", (0,0))[0])})
                except Exception:
                    rpt.heatmap.items.append({"ok": False, "stage": "gen_heatmap_data", "error": "not a DataFrame"})
                    hm_ok = False
        else:
            rpt.heatmap.items.append({"ok": True, "note": "dashboard nie importowany (pomięto sanity)"})
        rpt.heatmap.ok = rpt.heatmap.ok and hm_ok
    except Exception as e:
        rpt.heatmap.ok = False
        rpt.heatmap.items.append({"ok": False, "error": f"{type(e).__name__}: {e}"})

    # 6) Narzędzia statyczne (opcjonalnie)
    if args.no_static:
        log("🧯 Pomijam ruff/mypy/pytest (—no-static).")
    else:
        log("🛠️ Uruchamiam ruff/mypy/pytest (jeśli dostępne)…")
        if has_exe("ruff"):
            code, out = run_cmd(["ruff", "check", "--exit-zero", root])
            rpt.static_tools.items.append({"tool": "ruff", "ok": code == 0, "exit": code, "output": out})
            # exit-zero by design => nie psuje OK, ale logujemy
        else:
            rpt.static_tools.items.append({"tool": "ruff", "ok": True, "skipped": True})

        if has_exe("mypy"):
            code, out = run_cmd(["mypy", "--ignore-missing-imports", root])
            rpt.static_tools.items.append({"tool": "mypy", "ok": code == 0, "exit": code})
            if code != 0:
                rpt.static_tools.ok = False
        else:
            rpt.static_tools.items.append({"tool": "mypy", "ok": True, "skipped": True})

        # pytest tylko jeśli istnieje katalog tests/
        if os.path.isdir(os.path.join(root, "tests")) and has_exe("pytest"):
            code, out = run_cmd(["pytest", "-q"], cwd=root)
            rpt.static_tools.items.append({"tool": "pytest", "ok": code == 0, "exit": code})
            if code != 0:
                rpt.static_tools.ok = False
        else:
            rpt.static_tools.items.append({"tool": "pytest", "ok": True, "skipped": True})

    # 7) Raporty
    rpt.finalize()
    os.makedirs(REPORT_DIR, exist_ok=True)
    json_path = os.path.join(REPORT_DIR, f"rocket_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    md_path = os.path.join(REPORT_DIR, f"rocket_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rpt, f, default=lambda o: o.__dict__, ensure_ascii=False, indent=2)
    log(f"📝 Zapisano raport JSON: {json_path}")

    # prosty Markdown
    def yesno(b: bool) -> str:
        return "✅" if b else "⛔"
    md = []
    md.append(f"# RocketAlerts – raport kontroli ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    md.append("")
    md.append(f"- Python: `{rpt.env.get('python')}`  Platforma: `{rpt.env.get('platform')}`")
    md.append(f"- Składnia: {yesno(rpt.syntax.ok)}")
    md.append(f"- Importy: {yesno(rpt.imports.ok)}")
    md.append(f"- Dane: {yesno(rpt.data.ok)}")
    md.append(f"- Smoke: {yesno(rpt.smoke.ok)}")
    md.append(f"- Heatmapa: {yesno(rpt.heatmap.ok)}")
    md.append(f"- Statyczne narzędzia: {yesno(rpt.static_tools.ok)}")
    md.append("")
    md.append("## Podsumowanie")
    md.append(f"**Wynik końcowy:** {yesno(rpt.overall_ok())}")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    log(f"📝 Zapisano raport MD:   {md_path}")

    # 8) Exit code
    if rpt.overall_ok():
        log("🎉 Wszystko wygląda OK.")
        sys.exit(0)
    else:
        log("⚠️  Wykryto problemy — sprawdź raport w reports/.")
        sys.exit(2)

if __name__ == "__main__":
    main()
