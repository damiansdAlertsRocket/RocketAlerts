# candles.py – RocketAlerts v12 ULTRA EXTREME

import pandas as pd
import numpy as np

def detect_candlestick_pattern(row):
    o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
    body = abs(c - o)
    candle_range = h - l
    upper_shadow = h - max(c, o)
    lower_shadow = min(c, o) - l

    if candle_range == 0:
        return "Doji"

    if body < candle_range * 0.2:
        if upper_shadow > body * 2 and lower_shadow < body * 0.5:
            return "Shooting Star"
        elif lower_shadow > body * 2 and upper_shadow < body * 0.5:
            return "Hammer"
        else:
            return "Doji"

    if c > o and body > candle_range * 0.6:
        return "Bullish Marubozu"
    elif c < o and body > candle_range * 0.6:
        return "Bearish Marubozu"

    return None

def score_candle_pattern(pattern):
    if pattern in ["Hammer", "Bullish Marubozu"]:
        return 1
    elif pattern in ["Shooting Star", "Bearish Marubozu"]:
        return -1
    elif pattern == "Doji":
        return 0
    return 0

def detect_sequential_patterns(df):
    if len(df) < 3:
        return [], 0

    c0, o0 = df['Close'].iloc[-1], df['Open'].iloc[-1]
    c1, o1 = df['Close'].iloc[-2], df['Open'].iloc[-2]
    c2, o2 = df['Close'].iloc[-3], df['Open'].iloc[-3]

    body1 = abs(c1 - o1)
    body2 = abs(c2 - o2)

    patterns = []

    # Engulfing
    if c1 > o1 and c0 < o0 and o0 > c1 and c0 < o1:
        patterns.append("Bearish Engulfing")
    elif c1 < o1 and c0 > o0 and o0 < c1 and c0 > o1:
        patterns.append("Bullish Engulfing")

    # Morning/Evening Star
    if c2 < o2 and abs(c1 - o1) < body2 * 0.3 and c0 > o0 and c0 > ((o2 + c2) / 2):
        patterns.append("Morning Star")
    elif c2 > o2 and abs(c1 - o1) < body2 * 0.3 and c0 < o0 and c0 < ((o2 + c2) / 2):
        patterns.append("Evening Star")

    score = 0
    for p in patterns:
        if p in ["Bullish Engulfing", "Morning Star"]:
            score += 1
        elif p in ["Bearish Engulfing", "Evening Star"]:
            score -= 1

    return patterns, score

def analyze_candlestick_patterns(df):
    """
    Główna funkcja analizy świecowej.
    Zwraca słownik: score, patterns (single + sequential), confidence
    """
    pattern_single = detect_candlestick_pattern(df.iloc[-1])
    score_single = score_candle_pattern(pattern_single)

    patterns_seq, score_seq = detect_sequential_patterns(df)

    total_score = score_single + score_seq

    # Pewność interpretacji: zależna od ilości i jakości formacji
    confidence = "WYSOKA" if abs(total_score) >= 2 else "ŚREDNIA" if abs(total_score) == 1 else "NISKA"

    return {
        "score": total_score,
        "patterns": {
            "single": pattern_single,
            "sequential": patterns_seq
        },
        "confidence": confidence
    }
