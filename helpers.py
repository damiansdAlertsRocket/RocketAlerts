# helpers.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (HARDENED)

from __future__ import annotations

import os
import re
import pandas as pd
import numpy as np
from datetime import datetime

# === CONFIG (twarde fallbacki gdy czegoś brakuje) ===
try:
    from config.config import *  # noqa
except Exception:
    # Minimalne, sensowne domyślne wartości
    DATA_FOLDER = "data"
    TRADER_MODE = True
    ATR_PERIOD = 14
    ATR_SL_MULTIPLIER = 1.5
    ATR_TP_MULTIPLIER = 2.5
    MOVE_SL_TO_BREAKEVEN_AT_RR = 1.0
    USE_TRAILING_SL = True
    TRAILING_ATR_MULTIPLIER = 1.0
    MIN_ATR_PCT = 0.15
    MAX_BB_SQUEEZE_PCT = 0.15
    MIN_RR = 1.2
    MIN_ADX = 18.0
    SESSION_FILTER_ENABLED = False

# === IMPORTY MODUŁÓW (bezpieczne) ===
try:
    from indicators import analyze_technical_indicators_with_score
except Exception:
    def analyze_technical_indicators_with_score(df, asset=None, interval=None):
        return {"score": 0, "signal": None, "strength": None, "breakdown": {}}

try:
    from candles import analyze_candlestick_patterns
except Exception:
    def analyze_candlestick_patterns(df): return {"score": 0}

try:
    from trendlines import analyze_trendlines
except Exception:
    def analyze_trendlines(df): return {"score": 0}

try:
    from volatility import analyze_volatility
except Exception:
    def analyze_volatility(df): return {"score": 0}

try:
    from fibonacci import fibonacci_score
except Exception:
    def fibonacci_score(df): return {"score": 0}

try:
    from volume_profile import volume_profile_score, calculate_volume_nodes, detect_order_blocks
except Exception:
    def volume_profile_score(_price, _nodes, _ob): return {"score": 0}
    def calculate_volume_nodes(df): return []
    def detect_order_blocks(df): return []

try:
    from pattern_detector import detect_chart_patterns
except Exception:
    def detect_chart_patterns(df): return []

try:
    from seasonality import seasonality_score
except Exception:
    def seasonality_score(df): return {"seasonality_score": 0}

try:
    from trade_filters import _adx_from_tech, _atr_pct, _bb_width_pct, _volume_ok, _in_session
except Exception:
    def _adx_from_tech(tech): return float(tech.get("adx", 0) or 0)
    def _atr_pct(df): return 0.0
    def _bb_width_pct(df): return 0.0
    def _volume_ok(df): return True
    def _in_session(asset, interval): return True

try:
    from risk import _effective_rr
except Exception:
    def _effective_rr(entry, sl, tp):
        try:
            return abs(tp - entry) / max(1e-9, abs(entry - sl))
        except Exception:
            return 0.0

try:
    from plot_utils import save_plot_as_png
except Exception:
    def save_plot_as_png(df, result, asset, interval, layers=None): return None

# =========================
# Cooldown utils
# =========================
COOLDOWN_PATH = os.path.join("logs", "cooldown_log.csv")
_COOLDOWN_REQUIRED_COLS = ["asset", "interval", "last_alert_time"]

def ensure_cooldown_file():
    os.makedirs(os.path.dirname(COOLDOWN_PATH), exist_ok=True)
    if not os.path.exists(COOLDOWN_PATH):
        pd.DataFrame(columns=_COOLDOWN_REQUIRED_COLS).to_csv(COOLDOWN_PATH, index=False, encoding="utf-8")

def _coerce_cooldown_df(df: pd.DataFrame) -> pd.DataFrame:
    for col in _COOLDOWN_REQUIRED_COLS:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    df = df[_COOLDOWN_REQUIRED_COLS]
    df["asset"] = df["asset"].astype("string")
    df["interval"] = df["interval"].astype("string")
    df["last_alert_time"] = pd.to_datetime(df["last_alert_time"], errors="coerce")
    mask_empty = df[_COOLDOWN_REQUIRED_COLS].isna().all(axis=1)
    if mask_empty.any():
        df = df[~mask_empty]
    return df.reset_index(drop=True)

def read_cooldown_log() -> pd.DataFrame:
    ensure_cooldown_file()
    try:
        df = pd.read_csv(COOLDOWN_PATH, encoding="utf-8-sig", on_bad_lines="skip")
    except Exception:
        df = pd.DataFrame(columns=_COOLDOWN_REQUIRED_COLS)
    return _coerce_cooldown_df(df)

def write_cooldown_log(df: pd.DataFrame):
    clean = _coerce_cooldown_df(df.copy())
    clean.to_csv(COOLDOWN_PATH, index=False, encoding="utf-8")

# =========================
# Dane makro
# =========================
def load_macro_events():
    try:
        path = os.path.join(DATA_FOLDER, "macro_events.csv")
        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame()

# =========================
# Heurystyki / scoring
# =========================
def score_to_probability(score: float) -> int:
    if score >= 4.5: return 90
    if score >= 4.0: return 85
    if score >= 3.5: return 75
    if score >= 3.0: return 65
    if score >= 2.5: return 55
    if score >= 2.0: return 50
    if score >= 1.5: return 45
    if score >= 1.0: return 40
    if score >  0.0: return 30
    return 20

# =========================
# Fallbacki progów ADX (gdy brak w config)
# =========================
try:
    MIN_ADX_BY_INTERVAL  # noqa
except NameError:
    MIN_ADX_BY_INTERVAL = {
        "1m": 16.0, "5m": 16.0, "15m": 16.0,
        "1h": 18.0, "4h": 18.0, "1d": 20.0
    }

try:
    SOFT_PASS_ATR_PCT_MIN  # noqa
except NameError:
    SOFT_PASS_ATR_PCT_MIN = 0.50

try:
    SOFT_PASS_BBW_PCT_MIN  # noqa
except NameError:
    SOFT_PASS_BBW_PCT_MIN = 0.60

try:
    SOFT_PASS_MIN_SCORE  # noqa
except NameError:
    SOFT_PASS_MIN_SCORE = 3.2

try:
    PROB_SOFT_ADX_PENALTY  # noqa
except NameError:
    PROB_SOFT_ADX_PENALTY = 12

def _min_adx_for_interval(interval: str) -> float:
    thr = MIN_ADX_BY_INTERVAL.get(interval)
    if thr is None:
        thr = MIN_ADX  # z config
    return float(thr)

# =========================
# SANITY / RZUTOWANIA NUMERYCZNE (naprawa zlepionych wartości)
# =========================
_FLOAT_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

def _extract_first_float(x) -> str | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).replace("\u00A0", "").replace(" ", "")
    m = _FLOAT_RE.search(s)
    return m.group(0) if m else None

def _coerce_float_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    s = s.astype(str).str.replace("\u00A0", "", regex=False).str.replace(" ", "", regex=False)
    # heurystyka europejskich formatów
    if (s.str.contains(r",\d{1,6}$", regex=True)).mean() > 0.3:
        s = s.str.replace(".", "", regex=False)  # tysiące
        s = s.str.replace(",", ".", regex=False)  # przecinek -> kropka
    s = s.map(_extract_first_float)
    return pd.to_numeric(s, errors="coerce")

def _ensure_numeric_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = _coerce_float_series(df[c])
        else:
            # brakująca kolumna – wstaw neutralną
            df[c] = 0.0 if c == "Volume" else np.nan
    return df

# =========================
# ATR / SL / TP / trailing
# =========================
def _atr(df: pd.DataFrame, period: int = None) -> float:
    try:
        period = period or ATR_PERIOD
    except Exception:
        period = 14
    try:
        h = _coerce_float_series(df["High"])
        l = _coerce_float_series(df["Low"])
        c1 = _coerce_float_series(df["Close"]).shift(1)
        tr = pd.concat([(h - l).abs(), (h - c1).abs(), (l - c1).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period, min_periods=period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else 0.0
    except Exception:
        return 0.0

def update_trailing_sl(entry: float, sl: float, tp: float, price: float, atr: float) -> float:
    try:
        rr_now = abs(price - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0.0
        if rr_now >= MOVE_SL_TO_BREAKEVEN_AT_RR:
            return round(entry, 2)
        if USE_TRAILING_SL and tp is not None:
            trailing_sl = price - TRAILING_ATR_MULTIPLIER * atr if entry < tp else price + TRAILING_ATR_MULTIPLIER * atr
            return round(trailing_sl, 2)
        return round(sl, 2)
    except Exception:
        return round(sl, 2)

def export_diagnostic_chart(df: pd.DataFrame, result: dict, asset: str, interval: str):
    try:
        save_plot_as_png(df, result, asset, interval)
    except Exception as e:
        print(f"❌ Wykres diagnostyczny nie zapisany: {e}")

# =========================
# Normalizacja sygnałów PL/EN
# =========================
def _norm_signal_to_en(sig) -> str | None:
    s = (str(sig).strip().upper() if sig is not None else "")
    if s in ("BUY", "KUP"): return "BUY"
    if s in ("SELL", "SPRZEDAJ"): return "SELL"
    return None

def _norm_signal_to_pl(sig) -> str | None:
    s = _norm_signal_to_en(sig)
    if s == "BUY": return "KUP"
    if s == "SELL": return "SPRZEDAJ"
    return None

# =========================
# Główna analiza waloru (utwardzona)
# =========================
def analyze_asset(asset, interval, df):
    out = {
        "asset": asset, "interval": interval, "score": 0,
        "signal": None, "signal_strength": None,
        "sl": None, "tp": None, "probability": None,
        "details": {}, "unvalidated": False, "score_breakdown": ""
    }

    # Dane?
    if df is None or df.empty:
        print(f"⚠️ Brak danych: {asset} ({interval})")
        out["details"]["skipped_reason"] = "no_data"
        return out

    # Rzutowania
    df = df.copy()
    # Date -> datetime (jeśli nie jest)
    if "Date" in df.columns:
        try:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)
        except Exception:
            pass

    # Upewnij się, że mamy OHLCV jako float
    df = _ensure_numeric_ohlcv(df)

    # Minimalne kolumny do działania
    if not all(c in df.columns for c in ["Close", "High", "Low"]):
        out["details"]["skipped_reason"] = "missing_columns"
        return out

    # Filtr sesji (opcjonalny)
    try:
        if SESSION_FILTER_ENABLED and not _in_session(asset, interval):
            out["details"]["skipped_reason"] = "session"
            return out
    except Exception:
        pass

    # ---- POD-ANALIZY (odporne) ----
    try:
        tech = analyze_technical_indicators_with_score(df, asset, interval) or {}
    except Exception:
        tech = {}

    try:
        candles = analyze_candlestick_patterns(df) or {"score": 0}
    except Exception:
        candles = {"score": 0}

    try:
        trends = analyze_trendlines(df) or {"score": 0}
    except Exception:
        trends = {"score": 0}

    try:
        vol = analyze_volatility(df) or {"score": 0}
    except Exception:
        vol = {"score": 0}

    try:
        fib = fibonacci_score(df) or {"score": 0}
    except Exception:
        fib = {"score": 0}

    try:
        current_price = float(_coerce_float_series(df["Close"]).iloc[-1])
    except Exception:
        current_price = np.nan

    try:
        volume_nodes = calculate_volume_nodes(df)
        order_blocks = detect_order_blocks(df)
        volume_prof = volume_profile_score(current_price, volume_nodes, order_blocks) or {"score": 0}
    except Exception:
        volume_nodes, order_blocks, volume_prof = [], [], {"score": 0}

    try:
        chart_patterns = detect_chart_patterns(df) or []
    except Exception:
        chart_patterns = []

    try:
        season = seasonality_score(df) or {"seasonality_score": 0}
    except Exception:
        season = {"seasonality_score": 0}

    # ---- SCORE ŁĄCZNY ----
    total_score = (
        float(tech.get("score", 0) or 0) +
        float(candles.get("score, ", candles.get("score", 0)) or 0) +
        float(trends.get("score", 0) or 0) +
        float(vol.get("score", 0) or 0) +
        float(fib.get("score", 0) or 0) +
        float(volume_prof.get("score", 0) or 0) +
        (1.0 if chart_patterns else 0.0) +
        float(season.get("seasonality_score", 0) or 0)
    )

    out["score"] = round(total_score, 2)
    raw_signal = tech.get("signal", None)
    out["signal"] = _norm_signal_to_pl(raw_signal)  # zgodne z dashboardem
    out["signal_strength"] = tech.get("strength")
    out["details"]["tech"] = tech

    # Tryb „tylko ocena”
    if not TRADER_MODE:
        out["probability"] = score_to_probability(out["score"])
        return out

    # ADX / ATR% / BBW%
    try:
        adx = float(_adx_from_tech(tech))
    except Exception:
        adx = 0.0
    try:
        atr_pct = float(_atr_pct(df))
    except Exception:
        atr_pct = 0.0
    try:
        bbw = float(_bb_width_pct(df))
    except Exception:
        bbw = 0.0

    adx_thr = _min_adx_for_interval(interval)

    # —— Twardy próg ADX z miękkim dopuszczeniem —— #
    if adx < adx_thr:
        high_volatility = (atr_pct >= SOFT_PASS_ATR_PCT_MIN) or (bbw >= SOFT_PASS_BBW_PCT_MIN)
        strong_combo = total_score >= SOFT_PASS_MIN_SCORE
        if not (high_volatility and strong_combo):
            out["details"]["skipped_reason"] = f"adx<{adx_thr}"
            return out
        else:
            out["details"]["soft_pass"] = {
                "reason": "low_adx_but_high_volatility_and_score",
                "adx": float(adx),
                "adx_threshold": float(adx_thr),
                "atr_pct": float(atr_pct),
                "bbw_pct": float(bbw),
                "total_score": float(total_score)
            }

    # Pozostałe filtry jakości
    try:
        if atr_pct < MIN_ATR_PCT:
            out["details"]["skipped_reason"] = f"atr%<{MIN_ATR_PCT}"
            return out
    except Exception:
        pass

    try:
        if bbw < MAX_BB_SQUEEZE_PCT:
            out["details"]["skipped_reason"] = f"bb_squeeze<{MAX_BB_SQUEEZE_PCT}"
            return out
    except Exception:
        pass

    # Wolumen jako warning (nie blokuje)
    try:
        volume_flag = not _volume_ok(df)
    except Exception:
        volume_flag = False
    if volume_flag:
        out["details"]["warning"] = "low_volume"

    # Normalizuj sygnał do EN na potrzeby logiki wejścia
    raw_signal_en = _norm_signal_to_en(raw_signal)
    if raw_signal_en not in ("BUY", "SELL"):
        out["details"]["skipped_reason"] = "no_signal"
        return out

    # Trend na EMA50/EMA200 (na Close float)
    close_f = _coerce_float_series(df["Close"])
    ema200 = close_f.ewm(span=200, adjust=False).mean().iloc[-1]
    ema50 = close_f.ewm(span=50, adjust=False).mean().iloc[-1]
    uptrend = ema50 > ema200

    if raw_signal_en == "BUY" and not uptrend:
        out["details"]["skipped_reason"] = "trend_down"
        return out
    if raw_signal_en == "SELL" and uptrend:
        out["details"]["skipped_reason"] = "trend_up"
        return out

    entry = float(current_price) if pd.notna(current_price) else float(close_f.iloc[-1])
    atr_val = _atr(df)

    if raw_signal_en == "BUY":
        sl = entry - ATR_SL_MULTIPLIER * atr_val
        tp = entry + ATR_TP_MULTIPLIER * atr_val
    else:
        sl = entry + ATR_SL_MULTIPLIER * atr_val
        tp = entry - ATR_TP_MULTIPLIER * atr_val

    rr = _effective_rr(entry, sl, tp)

    try:
        if rr < MIN_RR:
            out["details"]["skipped_reason"] = f"rr<{MIN_RR}"
            return out
    except Exception:
        pass

    # Szacowana skuteczność
    prob = min(95, 50 + int((adx - 20) * 1.2) + int((rr - 1.5) * 10))

    # Kara za miękki ADX
    if adx < adx_thr:
        prob = max(10, prob - PROB_SOFT_ADX_PENALTY)
    if volume_flag:
        prob = max(20, prob - 10)

    out["sl"] = round(sl, 2)
    out["tp"] = round(tp, 2)
    out["probability"] = int(prob)

    out["score_breakdown"] = (
        f"Score:{round(total_score, 2)} | ADX:{adx:.1f} (thr:{adx_thr:.1f}) | "
        f"ATR%:{atr_pct:.2f} | BBW%:{bbw:.2f} | RR:{rr:.2f}"
    )
    out["details"].update({
        "rr": float(rr),
        "ema50": float(ema50) if pd.notna(ema50) else None,
        "ema200": float(ema200) if pd.notna(ema200) else None,
        "volume_ok": not volume_flag
    })

    return out
