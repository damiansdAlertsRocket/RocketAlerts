# utils/date_utils.py

from datetime import datetime, timedelta
import pytz

def get_now_ams():
    tz = pytz.timezone("Europe/Amsterdam")
    return datetime.now(tz)

def to_local(dt, tz_name="Europe/Amsterdam"):
    tz = pytz.timezone(tz_name)
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)

def get_prev_trading_day(dt=None):
    if dt is None:
        dt = get_now_ams()
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt

def format_datetime(dt, fmt="%Y-%m-%d %H:%M:%S"):
    return dt.strftime(fmt)
