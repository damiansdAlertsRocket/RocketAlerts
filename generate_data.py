# generate_data.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (SMART DAILY + FALLBACK)

import os
import pandas as pd
import logging
from datetime import datetime

from config import (
    ASSETS, INTERVALS, DATA_FOLDER, EODHD_API_KEY, TWELVE_API_KEY,
    SYMBOL_MAP_EODHD, SYMBOL_MAP_TWELVE, LOCAL_TZ, SYMBOL_MAP_BINANCE
)
from utils.timezone import to_utc_datetime
from utils.request_utils import http_get_json
from data_sources.binance import fetch_from_binance

# === Logging – działa na konsoli i w logs/scheduler.log ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("generate_data")

# === Stałe ===
DEFAULT_LIMIT = 1000
DEFAULT_DAILY_LIMIT = 20000
TWELVE_INTRADAY = "https://api.twelvedata.com/time_series"
TWELVEDATA_INTERVAL_MAP = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "4h": "4h", "1d": "1day"
}

# === Zapis danych ===
def save_data(asset: str, interval: str, df: pd.DataFrame):
    if df.empty:
        log.warning(f"⛔ [SAVE] DF pusty – {asset} ({interval}) nie zapisano.")
    else:
        filename = os.path.join(DATA_FOLDER, f"{asset}_{interval}.csv")
        df.to_csv(filename, index=False)
        log.info(f"✅ [SAVE] Zapisano: {asset}_{interval} – {len(df)} świec")

# === Pobieranie z EODHD (1d) ===
def fetch_from_eodhd(asset: str, interval: str) -> pd.DataFrame:
    if interval != "1d":
        return pd.DataFrame()
    mapped_symbol = SYMBOL_MAP_EODHD.get(asset)
    if not mapped_symbol:
        log.warning(f"⛔ Brak mapowania EODHD dla: {asset}")
        return pd.DataFrame()

    url = f"https://eodhd.com/api/eod/{mapped_symbol}"
    params = {"api_token": EODHD_API_KEY, "fmt": "json"}
    log.info(f"🌍 Pobieram dane z EODHD dla {asset} ({interval}) -> {mapped_symbol}")
    data, code = http_get_json(url, params)
    if not data:
        if code == 404:
            log.warning(f"⚠️ HTTP 404 dla EODHD {mapped_symbol} ({asset})")
        else:
            log.warning(f"⛔ EODHD brak danych dla {asset}")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if df.empty:
        log.warning(f"⛔ EODHD zwrócił pusty DF dla {asset}")
        return pd.DataFrame()

    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    })
    df = to_utc_datetime(df)
    log.info(f"🗄️ EODHD OK: {asset} – {len(df)} świec 1d")
    return df

# === Pobieranie z TwelveData (dowolny interwał, w tym 1d) ===
def fetch_from_twelvedata(asset: str, interval: str, limit: int = DEFAULT_LIMIT) -> pd.DataFrame:
    symbol = SYMBOL_MAP_TWELVE.get(asset)
    if not symbol:
        log.warning(f"⛔ Brak mapowania Twelvedata dla {asset}")
        return pd.DataFrame()

    interval_td = TWELVEDATA_INTERVAL_MAP.get(interval, interval)
    params = {
        "symbol": symbol,
        "interval": interval_td,
        "outputsize": limit,
        "apikey": TWELVE_API_KEY
    }

    log.info(f"📡 Pobieram dane z Twelvedata: {symbol} ({interval_td})")
    data, code = http_get_json(TWELVE_INTRADAY, params)
    if not data or "values" not in data:
        log.warning(f"⛔ Twelvedata brak danych {asset} ({interval})")
        return pd.DataFrame()

    df = pd.DataFrame(data["values"])
    if "datetime" not in df:
        log.warning(f"⛔ Brak kolumny datetime dla {asset}")
        return pd.DataFrame()

    df.rename(columns={"datetime": "Date"}, inplace=True)

    # Upewnij się, że wymagane kolumny istnieją
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            log.warning(f"⛔ Kolumna {col} nieobecna w danych {asset}")
            return pd.DataFrame()
    if "volume" not in df.columns:
        df["volume"] = 0

    try:
        df = df[["Date", "open", "high", "low", "close", "volume"]]
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    except Exception as e:
        log.warning(f"⛔ Błąd formatowania danych dla {asset}: {e}")
        return pd.DataFrame()

    df = to_utc_datetime(df)
    log.info(f"🗄️ TwelveData OK: {asset} – {len(df)} świec {interval}")
    return df

# === Binance (krypto, intraday) ===
def fetch_from_binance_wrapper(asset: str, interval: str, limit: int = DEFAULT_LIMIT) -> pd.DataFrame:
    symbol = SYMBOL_MAP_BINANCE.get(asset)
    if not symbol:
        log.warning(f"⛔ Brak symbolu Binance dla {asset}")
        return pd.DataFrame()
    try:
        log.info(f"📡 Pobieram dane z Binance: {symbol} ({interval})")
        df = fetch_from_binance(symbol, interval, limit=limit)
        df = to_utc_datetime(df)
        log.info(f"🗄️ Binance OK: {asset} – {len(df)} świec {interval}")
        return df
    except Exception as e:
        log.warning(f"⛔ Binance fetch error dla {asset} ({symbol}): {e}")
        return pd.DataFrame()

# === Budowanie dziennych z intraday (agregacja 1h -> 1D) ===
def build_daily_from_intraday(df_intraday: pd.DataFrame) -> pd.DataFrame:
    """
    Oczekuje DF z kolumnami: Date(UTC), Open, High, Low, Close, Volume.
    Agreguje po dniu (UTC) do OHLC + sum(Volume).
    """
    if df_intraday.empty:
        return pd.DataFrame()

    df = df_intraday.copy()
    # Upewnij się, że Date jest datetime (UTC) i ustaw index
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df = df.sort_values("Date")
    df.set_index("Date", inplace=True)

    ohlc_dict = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    daily = df.resample("1D", label="left", closed="left").agg(ohlc_dict).dropna(subset=["Open", "High", "Low", "Close"])
    daily = daily.reset_index()
    daily.rename(columns={"Date": "Date"}, inplace=True)

    # Przytnij puste na końcach
    daily = daily.dropna()
    return daily

# === Smart daily (1d): EODHD -> TwelveData 1day -> agregacja z 1h ===
def fetch_daily_smart(asset: str, limit_daily: int = DEFAULT_DAILY_LIMIT) -> pd.DataFrame:
    # 1) EODHD
    log.info(f"🌍 [DAILY SMART] EODHD próba: {asset}")
    df = fetch_from_eodhd(asset, "1d")
    if not df.empty:
        log.info(f"✅ [DAILY] {asset} z EODHD")
        return df

    # 2) TwelveData 1day
    log.info(f"📡 [DAILY SMART] TwelveData 1day próba: {asset}")
    df = fetch_from_twelvedata(asset, "1d", limit=limit_daily)
    if not df.empty:
        log.info(f"✅ [DAILY] {asset} z TwelveData 1day")
        return df

    # 3) Agregacja z 1h
    log.info(f"🧱 [DAILY SMART] Buduję 1d z 1h: {asset}")
    # krypto z Binance, reszta z TwelveData
    if asset in SYMBOL_MAP_BINANCE:
        intraday = fetch_from_binance_wrapper(asset, "1h", limit=limit_daily)
    else:
        intraday = fetch_from_twelvedata(asset, "1h", limit=limit_daily)

    if intraday.empty:
        log.warning(f"⛔ Nie udało się pobrać intraday 1h do budowy 1d: {asset}")
        return pd.DataFrame()

    daily = build_daily_from_intraday(intraday)
    if daily.empty:
        log.warning(f"⛔ Agregacja 1h->1d dała pusty wynik: {asset}")
        return pd.DataFrame()

    log.info(f"✅ [DAILY] {asset} złożone z 1h ({len(daily)} świec)")
    return daily

# === Główna funkcja ===
def generate_all_data():
    log.info("🚀 START: Generowanie danych")
    for asset in ASSETS:
        for interval in INTERVALS:
            log.info(f"\n🔄 Przetwarzam: {asset} ({interval})")
            try:
                # Krypto — zawsze Binance (wszystkie TF-y, łącznie z 1d z Binance 1d jeśli jest)
                if asset in SYMBOL_MAP_BINANCE and interval != "1d":
                    log.info(f"📦 [Binance] Start: {asset} ({interval})")
                    df = fetch_from_binance_wrapper(asset, interval, DEFAULT_LIMIT)
                    save_data(asset, interval, df)
                    continue

                # Dzienny TF: smart strategia (EODHD -> TwelveData 1day -> agregacja 1h)
                if interval == "1d":
                    log.info(f"🧠 [DAILY SMART] Start: {asset} (1d)")
                    df = fetch_daily_smart(asset, limit_daily=DEFAULT_DAILY_LIMIT)
                    save_data(asset, interval, df)
                    continue

                # Intraday dla reszty (Forex/Indeksy/Surowce): TwelveData
                log.info(f"📡 [Twelvedata] Start: {asset} ({interval})")
                df = fetch_from_twelvedata(asset, interval, DEFAULT_LIMIT)
                save_data(asset, interval, df)

            except Exception as e:
                log.warning(f"⚠️ Błąd przetwarzania {asset} ({interval}): {e}")
    log.info("✅ Zakończono generowanie danych.")
