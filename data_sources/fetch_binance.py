import requests
import pandas as pd
from datetime import datetime
from time import sleep
from config import SYMBOL_MAP_BINANCE
from utils.logger import log

BINANCE_BASE_URL = "https://api.binance.com/api/v3/klines"

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

def fetch_from_binance(symbol, interval, limit=1000):
    if interval not in INTERVAL_MAP:
        raise ValueError(f"⛔ Nieobsługiwany interwał: {interval}")

    binance_symbol = SYMBOL_MAP_BINANCE.get(symbol)
    if not binance_symbol:
        raise ValueError(f"⛔ Brak symbolu Binance dla {symbol}")

    params = {
        "symbol": binance_symbol,
        "interval": INTERVAL_MAP[interval],
        "limit": limit
    }

    try:
        response = requests.get(BINANCE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log.error(f"❌ Błąd pobierania z Binance dla {symbol} – {e}")
        return pd.DataFrame()

    if not data or isinstance(data, dict) and "code" in data:
        log.error(f"⚠️ Binance HTTP error – {data}")
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=[
        "OpenTime", "Open", "High", "Low", "Close", "Volume",
        "CloseTime", "QuoteAssetVolume", "NumberOfTrades",
        "TakerBuyBaseVolume", "TakerBuyQuoteVolume", "Ignore"
    ])

    df["Date"] = pd.to_datetime(df["OpenTime"], unit="ms")
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
    df[["Open", "High", "Low", "Close", "Volume"]] = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)

    return df.sort_values("Date").reset_index(drop=True)

def fetch_from_binance_wrapper(asset, interval, limit=1000):
    for _ in range(3):
        df = fetch_from_binance(asset, interval, limit)
        if not df.empty:
            return df
        sleep(2)
    return pd.DataFrame()
