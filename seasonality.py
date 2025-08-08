# seasonality.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX

import pandas as pd
import numpy as np
from datetime import datetime


def analyze_monthly_seasonality(df):
    """
    Oblicza średni procentowy zwrot dla każdego miesiąca na podstawie danych historycznych.
    """
    df = df.copy()
    df["Month"] = pd.to_datetime(df["Date"]).dt.month
    df["Return"] = df["Close"].pct_change()
    monthly_avg = df.groupby("Month")["Return"].mean() * 100  # w %
    return monthly_avg.to_dict()


def analyze_weekday_seasonality(df):
    """
    Oblicza średni procentowy zwrot dla każdego dnia tygodnia (0=poniedziałek, 6=niedziela).
    """
    df = df.copy()
    df["Weekday"] = pd.to_datetime(df["Date"]).dt.dayofweek
    df["Return"] = df["Close"].pct_change()
    weekday_avg = df.groupby("Weekday")["Return"].mean() * 100
    return weekday_avg.to_dict()


def seasonality_score(df, current_date=None):
    """
    Przyznaje punkty na podstawie aktualnego dnia tygodnia i miesiąca oraz historycznej sezonowości.
    Skala: -1 do +1 (łącznie), każdy komponent (miesiąc/dzień) ±0.5 pkt.
    """
    df = df.copy()
    if current_date is None:
        current_date = pd.to_datetime(df["Date"].iloc[-1])

    month = current_date.month
    weekday = current_date.dayofweek if hasattr(current_date, "dayofweek") else current_date.weekday()

    monthly_returns = analyze_monthly_seasonality(df)
    weekday_returns = analyze_weekday_seasonality(df)

    month_return = monthly_returns.get(month, 0)
    weekday_return = weekday_returns.get(weekday, 0)

    score = 0
    # logika punktowania na podstawie dodatniej/ujemnej średniej
    if month_return > 0.2:
        score += 0.5
    elif month_return < -0.2:
        score -= 0.5

    if weekday_return > 0.1:
        score += 0.5
    elif weekday_return < -0.1:
        score -= 0.5

    return {
        "score": round(score, 2),
        "month_avg_return": round(month_return, 2),
        "weekday_avg_return": round(weekday_return, 2),
        "month": month,
        "weekday": weekday,
        "month_name": current_date.strftime("%B"),
        "weekday_name": current_date.strftime("%A"),
        "monthly_table": monthly_returns,
        "weekday_table": weekday_returns
    }
