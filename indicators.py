# indicators.py – RocketAlerts v12 ULTRA EXTREME (HARDENED)

from __future__ import annotations

import re
import pandas as pd
import numpy as np

# ==========
# Coercja numeryczna – odporna na "zlepione" liczby i formaty EU
# ==========
_FLOAT_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

def _extract_first_float(x) -> str | None:
    """Z łańcucha wybiera pierwszy poprawny literał float (np. z '1.23.45' -> '1.23')."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).replace("\u00A0", "").replace(" ", "")
    # heurystyka – zamień przecinek na kropkę tylko gdy wygląd EU
    if "," in s and s.count(",") <= 1 and s.count(".") <= 1:
        s = s.replace(".", "").replace(",", ".")
    m = _FLOAT_RE.search(s)
    return m.group(0) if m else None

def _to_float_series(s: pd.Series) -> pd.Series:
    """Twarde rzutowanie na float z podparciem regexem."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    s = s.astype(str).map(_extract_first_float)
    return pd.to_numeric(s, errors="coerce")

def _ensure_numeric_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = _to_float_series(df[c])
        else:
            df[c] = 0.0 if c == "Volume" else np.nan
    return df


# ==========
# Podstawowe wskaźniki
# ==========
def calculate_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """EMA z zabezpieczeniami typów."""
    close = _to_float_series(df.get("Close", pd.Series(dtype="float64")))
    return close.ewm(span=period, adjust=False).mean()

def calculate_macd(df: pd.DataFrame):
    """MACD (12, 26, 9) – zwraca: macd_line, signal_line, histogram."""
    ema12 = calculate_ema(df, 12)
    ema26 = calculate_ema(df, 26)
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI (Wilder) – EWM alpha=1/period, bezpieczne min_periods."""
    close = _to_float_series(df.get("Close", pd.Series(dtype="float64")))
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _true_range(high, low, prev_close):
    return pd.concat([(high - low).abs(),
                      (high - prev_close).abs(),
                      (low - prev_close).abs()], axis=1).max(axis=1)

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ADX wg Wildera (przybliżenie EWM).
    Zabezpieczone typy + min_periods.
    """
    df = _ensure_numeric_ohlcv(df)
    high, low, close = df["High"], df["Low"], df["Close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = _true_range(high, low, close.shift(1))

    # Wilder smoothing ~ EWM(alpha=1/period)
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    plus_dm_s = plus_dm.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    minus_dm_s = minus_dm.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

    # DI
    plus_di = 100 * (plus_dm_s / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm_s / atr.replace(0, np.nan))

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return adx.fillna(0.0)

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0):
    """Bollinger Bands – zwraca: upper, middle, lower."""
    close = _to_float_series(df.get("Close", pd.Series(dtype="float64")))
    ma = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    upper = ma + std_mult * std
    lower = ma - std_mult * std
    return upper, ma, lower

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    df = _ensure_numeric_ohlcv(df)
    tr = _true_range(df["High"], df["Low"], df["Close"].shift(1))
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return atr


# ==========
# Analityka & scoring
# ==========
def analyze_technical_indicators_with_score(df: pd.DataFrame,
                                            asset: str | None = None,
                                            interval: str | None = None) -> dict:
    """
    Pełna analiza techniczna:
      - EMA20/50 (trend)
      - RSI(14) (prze-kup/prze-sprz)
      - MACD(12,26,9) (momentum)
      - ADX(14) (siła trendu)
      - Bollinger Bands(20,2) (wybicie/przeciągnięcie)
      - Wolumen (spike)

    Zwraca:
      {
        "score": float,
        "breakdown": dict[str,int],
        "signal": "BUY" | "SELL" | None,
        "strength": "WYSOKA" | "ŚREDNIA" | "NISKA",
        "adx": float,
        "extras": {...}
      }
    """
    out = {
        "score": 0.0,
        "breakdown": {},
        "signal": None,
        "strength": None,
        "adx": 0.0,
        "extras": {}
    }

    if df is None or df.empty:
        return out

    df = _ensure_numeric_ohlcv(df)

    # Wymagane kolumny
    if not all(c in df.columns for c in ["Close", "High", "Low", "Volume"]):
        return out

    # === Wskaźniki ===
    ema20 = calculate_ema(df, 20)
    ema50 = calculate_ema(df, 50)

    rsi = calculate_rsi(df, 14)
    rsi_last = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else np.nan

    macd_line, signal_line, hist = calculate_macd(df)
    macd_last = float(macd_line.iloc[-1]) if pd.notna(macd_line.iloc[-1]) else np.nan
    macd_sig_last = float(signal_line.iloc[-1]) if pd.notna(signal_line.iloc[-1]) else np.nan

    adx = calculate_adx(df, 14)
    adx_last = float(adx.iloc[-1]) if pd.notna(adx.iloc[-1]) else 0.0
    out["adx"] = adx_last

    upper_bb, mid_bb, lower_bb = calculate_bollinger_bands(df, 20, 2.0)

    close = _to_float_series(df["Close"])
    vol = _to_float_series(df["Volume"])

    # === Scoring ===
    score = 0.0
    br = {}

    # 1) Trend: EMA20 vs EMA50
    if pd.notna(ema20.iloc[-1]) and pd.notna(ema50.iloc[-1]):
        if ema20.iloc[-1] > ema50.iloc[-1]:
            score += 1; br["EMA"] = +1
        else:
            score -= 1; br["EMA"] = -1
    else:
        br["EMA"] = 0

    # 2) RSI – skrajne strefy
    if pd.notna(rsi_last):
        if rsi_last < 30:
            score += 1; br["RSI"] = +1
        elif rsi_last > 70:
            score -= 1; br["RSI"] = -1
        else:
            br["RSI"] = 0
    else:
        br["RSI"] = 0

    # 3) MACD – linia > sygnał
    if pd.notna(macd_last) and pd.notna(macd_sig_last):
        if macd_last > macd_sig_last:
            score += 1; br["MACD"] = +1
        else:
            score -= 1; br["MACD"] = -1
    else:
        br["MACD"] = 0

    # 4) ADX – siła trendu (próg 25)
    if adx_last > 25:
        score += 1; br["ADX"] = +1
    else:
        br["ADX"] = 0

    # 5) Bollinger – przeciągnięcie/wyjście poza pasma
    up_last = upper_bb.iloc[-1] if len(upper_bb) else np.nan
    lo_last = lower_bb.iloc[-1] if len(lower_bb) else np.nan
    cl_last = close.iloc[-1] if len(close) else np.nan
    if pd.notna(up_last) and pd.notna(lo_last) and pd.notna(cl_last):
        if cl_last < lo_last:
            score += 1; br["BB"] = +1
        elif cl_last > up_last:
            score -= 1; br["BB"] = -1
        else:
            br["BB"] = 0
    else:
        br["BB"] = 0

    # 6) Wolumen – spike
    avg_vol = vol.rolling(window=20, min_periods=10).mean()
    if pd.notna(avg_vol.iloc[-1]) and avg_vol.iloc[-1] > 0:
        if vol.iloc[-1] > avg_vol.iloc[-1] * 1.8:
            score += 1; br["VOLUME"] = +1
        else:
            br["VOLUME"] = 0
    else:
        br["VOLUME"] = 0

    # === Sygnał i siła ===
    # Proste zasady: score >= +2 -> BUY; score <= -2 -> SELL; inaczej brak
    if score >= 2:
        sig = "BUY"
    elif score <= -2:
        sig = "SELL"
    else:
        sig = None

    strength = "NISKA"
    if abs(score) >= 4:
        strength = "WYSOKA"
    elif abs(score) == 3:
        strength = "ŚREDNIA"

    out.update({
        "score": float(score),
        "breakdown": br,
        "signal": sig,
        "strength": strength,
        "extras": {
            "rsi_last": rsi_last,
            "macd_last": macd_last,
            "macd_signal_last": macd_sig_last,
            "ema20_last": float(ema20.iloc[-1]) if pd.notna(ema20.iloc[-1]) else np.nan,
            "ema50_last": float(ema50.iloc[-1]) if pd.notna(ema50.iloc[-1]) else np.nan,
            "bb_upper_last": float(up_last) if pd.notna(up_last) else np.nan,
            "bb_lower_last": float(lo_last) if pd.notna(lo_last) else np.nan,
        }
    })
    return out
