from datetime import datetime
import pandas as pd
import pytz
from config import LOCAL_TZ

def to_utc_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Konwertuje kolumnę 'Date' do UTC timezone.
    """
    df["Date"] = pd.to_datetime(df["Date"])
    if df["Date"].dt.tz is None:
        df["Date"] = df["Date"].dt.tz_localize(LOCAL_TZ)
    else:
        df["Date"] = df["Date"].dt.tz_convert(LOCAL_TZ)
    df["Date"] = df["Date"].dt.tz_convert("UTC")
    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
