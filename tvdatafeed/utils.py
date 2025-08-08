import pandas as pd
from datetime import datetime

def convert_tf(interval):
    tf_map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D"
    }
    return tf_map.get(interval, "1")

def df_from_response(data):
    if not data or 't' not in data:
        return pd.DataFrame()

    return pd.DataFrame({
        "datetime": [datetime.fromtimestamp(t) for t in data["t"]],
        "open": data["o"],
        "high": data["h"],
        "low": data["l"],
        "close": data["c"],
        "volume": data["v"]
    })
