import requests
import pandas as pd
from utils.logger import log
from utils.timezone import to_utc_datetime
from config import TWELVE_API_KEY, SYMBOL_MAP_TWELVE

TWELVE_API_URL = "https://api.twelvedata.com/time_series"
TWELVE_INTERVAL_MAP = {
    "1m": "1min", "5m": "5min", "15m": "15min",
    "1h": "1h", "4h": "4h", "1d": "1day"
}

def fetch_from_twelvedata(symbol, interval, limit=1000):
    if symbol not in SYMBOL_MAP_TWELVE:
        log.warning(f"⛔ Brak mapowania Twelvedata dla {symbol}")
        return pd.DataFrame()

    td_symbol = SYMBOL_MAP_TWELVE[symbol]
    td_interval = TWELVE_INTERVAL_MAP.get(interval, interval)

    params = {
        "symbol": td_symbol,
        "interval": td_interval,
        "outputsize": limit,
        "apikey": TWELVE_API_KEY
    }

    try:
        res = requests.get(TWELVE_API_URL, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        log.error(f"❌ Twelvedata błąd dla {symbol} ({interval}): {e}")
        return pd.DataFrame()

    if "values" not in data:
        log.warning(f"⛔ Twelvedata brak danych {symbol} ({interval}): {data}")
        return pd.DataFrame()

    df = pd.DataFrame(data["values"])
    if "datetime" not in df:
        return pd.DataFrame()

    df.rename(columns={"datetime": "Date"}, inplace=True)

    try:
        df = df[["Date", "open", "high", "low", "close", "volume"]]
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    except Exception as e:
        log.warning(f"⛔ Błąd formatowania Twelvedata dla {symbol}: {e}")
        return pd.DataFrame()

    return to_utc_datetime(df)
