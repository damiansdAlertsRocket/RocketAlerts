# fibonacci.py – RocketAlerts v12 ULTRA EXTREME

import pandas as pd

def fibonacci_score(df, lookback=100):
    """
    Oblicza poziomy Fibonacciego z ostatnich max/min i sprawdza,
    czy cena zbliża się do istotnych poziomów.
    Zwraca score (0/1) jeśli blisko poziomu 0.382, 0.5, 0.618.
    """

    if df is None or df.empty or 'Close' not in df.columns:
        return {"score": 0, "level_hit": None, "fib_levels": {}}

    recent = df[-lookback:]
    high = recent['High'].max()
    low = recent['Low'].min()
    diff = high - low

    # Kluczowe poziomy Fibo
    levels = {
        "0.236": high - 0.236 * diff,
        "0.382": high - 0.382 * diff,
        "0.500": high - 0.500 * diff,
        "0.618": high - 0.618 * diff,
        "0.786": high - 0.786 * diff,
    }

    close = df['Close'].iloc[-1]
    tolerance = diff * 0.015  # 1.5% margines

    score = 0
    hit_level = None

    for level_name, level_price in levels.items():
        if abs(close - level_price) <= tolerance:
            score = 1
            hit_level = level_name
            break

    return {
        "score": score,
        "level_hit": hit_level,
        "fib_levels": levels
    }
