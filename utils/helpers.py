import logging
logger = logging.getLogger(__name__)
import pandas as pd
import numpy as np
from datetime import datetime
from config.config import *
from indicators import analyze_technical_indicators_with_score
from candles import analyze_candlestick_patterns
from trendlines import analyze_trendlines
from volatility import analyze_volatility
from fibonacci import fibonacci_score
from volume_profile import volume_profile_score
from pattern_detector import detect_chart_patterns


def load_macro_events():
    try:
        df = pd.read_csv("data/macro_events.csv")
        if df.empty or "date" not in df.columns:
            logger.warning("⚠️ Makro: brak danych lub złe kolumny – wstawiamy testowy DataFrame.")
            return pd.DataFrame([{
                "date": "2099-12-31",
                "country": "US",
                "event": "Test Event",
                "impact": "High",
                "latest": 0,
                "forecast": 0,
                "previous": 0
            }])
        return df
    except Exception as e:
        logger.error(f"❌ Błąd ładowania makro: {e}")
        return pd.DataFrame([{
            "date": "2099-12-31",
            "country": "US",
            "event": "Fallback Event",
            "impact": "Low",
            "latest": 0,
            "forecast": 0,
            "previous": 0
        }])


def analyze_asset(asset, interval, df):
    results = {
        "asset": asset,
        "interval": interval,
        "score": 0,
        "signal": None,
        "signal_strength": None,
        "sl": None,
        "tp": None,
        "probability": None,
        "details": {},
        "unvalidated": False
    }

    if df is None or df.empty or "Close" not in df.columns:
        logger.warning(f"⚠️ Brak danych do analizy: {asset} ({interval})")
        return results

    try:
        macro_events = load_macro_events()
        results["details"]["macro_events_loaded"] = isinstance(macro_events, pd.DataFrame)
    except Exception as e:
        logger.error(f"❌ Błąd wczytywania makro dla {asset}: {e}")
        macro_events = pd.DataFrame()

    try:
        tech = analyze_technical_indicators_with_score(df, asset, interval)
        candles = analyze_candlestick_patterns(df)
        trends = analyze_trendlines(df)
        vol = analyze_volatility(df)
        fib = fibonacci_score(df)
        volume_profile = volume_profile_score(df)
        chart_patterns = detect_chart_patterns(df)

        total_score = (
            tech["score"]
            + candles["score"]
            + trends["score"]
            + vol["score"]
            + fib["score"]
            + volume_profile["score"]
            + chart_patterns["score"]
        )

        results["score"] = total_score
        results["signal"] = tech["signal"]
        results["signal_strength"] = tech["strength"]
        results["probability"] = min(99, max(40, total_score * 10))
        results["details"] = {
            "tech": tech,
            "candles": candles,
            "trendlines": trends,
            "volatility": vol,
            "fibonacci": fib,
            "volume_profile": volume_profile,
            "chart_patterns": chart_patterns,
        }

    except Exception as e:
        logger.error(f"❌ Błąd analizy: {asset} ({interval}) — {e}")

    return results
