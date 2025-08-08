# trade_filters.py — RocketAlerts v12 ULTRA EXTREME TOTAL MAX (fix cooldown)

from datetime import datetime
from pathlib import Path
import pandas as pd
import pytz  # jeśli nie używasz — możesz usunąć

from config.config import (
    ASSET_SESSION_RULES,
    LOCAL_TZ,
    BB_PERIOD,
    ATR_PERIOD,
    MIN_VOLUME_MA_MULT,
    COOLDOWN_LOG_PATH,
    COOLDOWN_MINUTES,
    COOLDOWN_AFTER_LOSS_MIN,
)

# ------------------------------------------------------------
# Sesje rynkowe
# ------------------------------------------------------------

def _in_session(asset: str, interval: str = None) -> bool:
    """
    Sprawdza, czy dany instrument znajduje się w aktywnej sesji.
    Jeśli brak reguł — zwraca True (24h).
    Obsługuje zapis np. "1530-2200" oraz zakres przez północ (np. "2200-0600").
    """
    session = ASSET_SESSION_RULES.get(asset)
    if session is None:
        return True  # brak ograniczeń – 24h sesja

    try:
        now = datetime.now(LOCAL_TZ).time()
        start_str, end_str = session.split("-")
        start = datetime.strptime(start_str, "%H%M").time()
        end = datetime.strptime(end_str, "%H%M").time()

        if start < end:
            return start <= now <= end
        else:
            # zakres przechodzi przez północ
            return now >= start or now <= end

    except Exception:
        # W razie błędu nie blokuj — traktuj jako 24h
        return True

# ------------------------------------------------------------
# Cooldown — samonaprawa i zgodność wstecz
# ------------------------------------------------------------

REQUIRED_COLS = ["asset", "interval", "timestamp", "result"]  # 'result' bywa puste

def _load_cooldown_df() -> pd.DataFrame:
    """
    Wczytuje plik cooldown, automatycznie tworzy/naprawia:
    - jeśli istnieje kolumna last_alert_time, mapuje ją na timestamp,
    - gwarantuje obecność kolumn REQUIRED_COLS,
    - nie wypisuje zbędnych ostrzeżeń.
    """
    path = Path(COOLDOWN_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(path)
    except Exception:
        # brak pliku / uszkodzony CSV -> start od pustego szablonu
        df = pd.DataFrame(columns=REQUIRED_COLS)
        df.to_csv(path, index=False, encoding="utf-8")
        return df

    # Zgodność wstecz: last_alert_time => timestamp
    if "timestamp" not in df.columns and "last_alert_time" in df.columns:
        df = df.rename(columns={"last_alert_time": "timestamp"})

    # Dodaj brakujące kolumny (jako puste)
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")

    # Zredukuj do wymaganych kolumn w ustalonej kolejności
    df = df[REQUIRED_COLS]

    return df


def _parse_ts_aware(ts_str: str):
    """
    Parsuje string timestamp → timezone aware w LOCAL_TZ.
    Akceptuje zarówno datetime z/bez strefy; bez strefy traktuje jako UTC.
    """
    if pd.isna(ts_str):
        return None
    try:
        # Preferencja: zakładamy UTC i konwertujemy do lokalnej
        ts = pd.to_datetime(ts_str, utc=True)
        return ts.tz_convert(LOCAL_TZ)
    except Exception:
        try:
            ts = pd.to_datetime(ts_str)
            if ts is None:
                return None
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize("UTC").tz_convert(LOCAL_TZ)
            else:
                ts = ts.tz_convert(LOCAL_TZ)
            return ts
        except Exception:
            return None


def cooldown_ok(asset: str, interval: str, cooldown_minutes: int = None) -> bool:
    """
    True = można wysłać alert (cooldown minął albo brak wpisu).
    Uwzględnia dłuższy cooldown po LOSS (COOLDOWN_AFTER_LOSS_MIN).
    Obsługuje pliki zarówno ze starą kolumną 'last_alert_time', jak i nową 'timestamp'.
    """
    try:
        df = _load_cooldown_df()

        # odfiltruj dany instrument/interwał
        df = df[(df["asset"] == asset) & (df["interval"] == interval)]
        if df.empty:
            return True

        last_row = df.iloc[-1]

        # parsuj czas ostatniego alertu
        last_ts = _parse_ts_aware(last_row.get("timestamp"))
        if last_ts is None:
            return True  # brak poprawnej daty -> nie blokuj

        now_local = datetime.now(LOCAL_TZ)

        # cooldown bazowy lub po stracie
        is_loss = str(last_row.get("result", "")).upper() == "LOSS"
        base_cd = COOLDOWN_AFTER_LOSS_MIN if is_loss else (
            cooldown_minutes if cooldown_minutes is not None else COOLDOWN_MINUTES
        )

        return (now_local - last_ts).total_seconds() >= base_cd * 60

    except Exception:
        # w razie jakiegokolwiek błędu – nie blokuj pracy systemu
        return True

# ------------------------------------------------------------
# Metryki/filtry techniczne
# ------------------------------------------------------------

def _adx_from_tech(tech: dict) -> float:
    """Wyciąga wartość ADX z wyników analizy technicznej."""
    try:
        return float(tech.get("indicators", {}).get("ADX", 0.0))
    except Exception:
        return 0.0


def _atr_pct(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """
    ATR jako % ceny Close.
    """
    try:
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)
        prev_close = close.shift(1)

        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr = tr.rolling(period).mean()
        last_close = close.iloc[-1]
        return float(atr.iloc[-1]) / last_close * 100 if last_close != 0 else 0.0
    except Exception:
        return 0.0


def _bb_width_pct(df: pd.DataFrame, period: int = BB_PERIOD) -> float:
    """
    Szerokość pasm Bollingera jako % ceny.
    """
    try:
        close = df["Close"].astype(float)
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        width = upper - lower
        return float(width.iloc[-1]) / close.iloc[-1] * 100
    except Exception:
        return 0.0


def _volume_ok(df: pd.DataFrame) -> bool:
    if "Volume" not in df.columns:
        return True  # brak wolumenu -> nie karz (FX/indeksy często tak mają)

    v = pd.to_numeric(df["Volume"], errors="coerce")
    v_nonnull = v.dropna()

    if v_nonnull.empty:
        return True  # brak danych wolumenowych -> nie blokuj

    # jeśli praktycznie wszystko zero, uznaj jako „niewiarygodny wolumen” i NIE karz
    if (v_nonnull.abs() < 1e-12).mean() > 0.95:
        return True

    # klasyczny warunek jakości wolumenu (np. ostatni nie poniżej 20 percentyla)
    try:
        thresh = v_nonnull.quantile(0.2)
        return bool(v_nonnull.iloc[-1] >= thresh)
    except Exception:
        return True


def _effective_rr(entry: float, sl: float, tp: float) -> float:
    """
    Współczynnik zysku do ryzyka (RR) = reward/risk, zaokrąglony do 2 miejsc.
    """
    try:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        return round(reward / risk, 2) if risk > 0 else 0.0
    except Exception:
        return 0.0
