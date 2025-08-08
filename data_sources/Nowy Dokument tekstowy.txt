import requests
import pandas as pd
from utils.logger import log
from utils.timezone import to_utc_datetime
from config import EODHD_API_KEY, SYMBOL_MAP_EODHD

def fetch_from_eodhd(symbol):
    if symbol not in SYMBOL_MAP_EODHD:
        log.warning(f"⛔ Brak mapowania EODHD dla: {symbol}")
        return pd.DataFrame()

    eod_symbol = SYMBOL_MAP_EODHD[symbol]
    url = f"https://eodhd.com/api/eod/{eod_symbol}"
    params = {"api_token": EODHD_API_KEY, "fmt": "json"}

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        log.error(f"❌ EODHD błąd dla {symbol}: {e}")
        return pd.DataFrame()

    if not data or isinstance(data, dict) and "error" in data:
        log.warning(f"⚠️ EODHD brak danych dla {symbol} ({eod_symbol})")
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    })

    return to_utc_datetime(df)
