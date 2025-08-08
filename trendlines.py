# trendlines.py – RocketAlerts v12 ULTRA EXTREME

import numpy as np
import pandas as pd
from scipy.stats import linregress

def analyze_regression_trend(df):
    """
    Analiza kierunku trendu na podstawie regresji liniowej.
    """
    y = df['Close'].values[-50:]
    x = np.arange(len(y))

    slope, intercept, r_value, _, _ = linregress(x, y)

    direction = "UP" if slope > 0 else "DOWN"
    strength = abs(slope) * r_value
    score = 1 if slope > 0.2 else -1 if slope < -0.2 else 0

    return {
        "score": score,
        "direction": direction,
        "slope": slope,
        "r2": r_value ** 2,
        "strength": strength
    }

def detect_support_resistance(df, window=20, tolerance=0.003):
    """
    Wykrywa lokalne poziomy wsparcia i oporu.
    """
    levels = []
    for i in range(window, len(df) - window):
        high = df['High'].iloc[i]
        low = df['Low'].iloc[i]

        is_resistance = all(high >= df['High'].iloc[i - j] for j in range(1, window + 1)) and \
                        all(high >= df['High'].iloc[i + j] for j in range(1, window + 1))

        is_support = all(low <= df['Low'].iloc[i - j] for j in range(1, window + 1)) and \
                     all(low <= df['Low'].iloc[i + j] for j in range(1, window + 1))

        if is_support or is_resistance:
            level = round((high + low) / 2, 2)
            if all(abs(level - l) > level * tolerance for l in levels):
                levels.append(level)

    return levels[:5]

def analyze_trendlines(df):
    """
    Główna funkcja analizy trendu:
    - regresja liniowa (nachylenie, r^2, siła)
    - lokalne poziomy wsparcia i oporu
    Zwraca score i opis trendu.
    """
    if df is None or df.empty or len(df) < 60:
        return {"score": 0, "levels": [], "regression": {}, "confidence": "NISKA"}

    regression = analyze_regression_trend(df)
    levels = detect_support_resistance(df)

    confidence = "WYSOKA" if abs(regression["slope"]) > 0.4 else "ŚREDNIA" if abs(regression["slope"]) > 0.2 else "NISKA"

    return {
        "score": regression["score"],
        "levels": levels,
        "regression": regression,
        "confidence": confidence
    }
