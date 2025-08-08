# multi_timeframe_analysis.py — RocketAlerts v12 ULTRA EXTREME
import os
import pandas as pd
from datetime import datetime
import pytz

try:
    from config.config import LOCAL_TZ
except Exception:
    LOCAL_TZ = pytz.timezone("Europe/Amsterdam")

try:
    from helpers import analyze_asset
except Exception as e:
    raise ImportError("Brak helpers.analyze_asset – wymagane do MTF") from e


def _read_df(asset: str, interval: str) -> pd.DataFrame:
    path = f"data/{asset}_{interval}.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)
    return df


def _decide_alignment(signals):
    """
    signals: list[tuple(interval, signal_str)]
    Zwraca (status, color)
    """
    ups = sum(1 for _, s in signals if (s or "BRAK").upper() == "KUP")
    dws = sum(1 for _, s in signals if (s or "BRAK").upper() == "SPRZEDAJ")
    if ups >= 2 and dws == 0:
        return "KUP", "lightgreen"
    if dws >= 2 and ups == 0:
        return "SPRZEDAJ", "tomato"
    return "BRAK", "gray"


def get_multi_tf_alignment(asset: str, intervals=None) -> dict:
    """
    Zwraca:
      {
        "status": "KUP|SPRZEDAJ|BRAK",
        "color": "lightgreen|tomato|gray",
        "signals": [("1h","KUP"),("4h","SPRZEDAJ"),("1d","BRAK")]
      }
    """
    if intervals is None:
        intervals = ["1h", "4h", "1d"]

    out = []
    for it in intervals:
        df = _read_df(asset, it)
        try:
            res = analyze_asset(asset, it, df) if not df.empty else {}
        except Exception:
            res = {}
        sig = (res.get("signal") or "BRAK") if isinstance(res, dict) else "BRAK"
        out.append((it, str(sig).upper()))

    status, color = _decide_alignment(out)
    return {"status": status, "color": color, "signals": out}
