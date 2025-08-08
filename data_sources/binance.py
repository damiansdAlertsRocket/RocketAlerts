import requests
import pandas as pd
import logging
from datetime import datetime
from utils.timezone import to_utc_datetime

log = logging.getLogger(__name__)

INTERVAL_MAP_BINANCE = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d"
}

def fetch_from_binance(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    base_url = "https://api.binance.com"
    endpoint = "/api/v3/klines"

    binance_symbol = symbol.replace("-", "").upper()
    binance_interval = INTERVAL_MAP_BINANCE.get(interval)
    if not binance_interval:
        log.warning(f"⛔ Nieobsługiwany interwał dla Binance: {interval}")
        return pd.DataFrame()

    url = f"{base_url}{endpoint}"
    params = {
        "symbol": binance_symbol,
        "interval": binance_interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            log.warning(f"⚠️ Binance HTTP {response.status_code} – {response.text}")
            return pd.DataFrame()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "Open time", "Open", "High", "Low", "Close", "Volume",
            "Close time", "Quote asset volume", "Number of trades",
            "Taker buy base volume", "Taker buy quote volume", "Ignore"
        ])
        df = df[["Open time", "Open", "High", "Low", "Close", "Volume"]]
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df["Date"] = pd.to_datetime(df["Date"], unit='ms')
        return to_utc_datetime(df)
    except Exception as e:
        log.warning(f"⚠️ Błąd pobierania z Binance: {e}")
        return pd.DataFrame()
