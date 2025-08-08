# pattern_detector.py
import pandas as pd
import numpy as np
from scipy.stats import linregress

def detect_channel(df, lookback=30, threshold=0.01):
    """
    Detekcja kanału cenowego (rosnącego lub spadkowego)
    """
    highs = df['High'][-lookback:]
    lows = df['Low'][-lookback:]
    x = np.arange(lookback)

    slope_high, intercept_high, _, _, _ = linregress(x, highs)
    slope_low, intercept_low, _, _, _ = linregress(x, lows)

    slope_diff = abs(slope_high - slope_low)
    if slope_diff < threshold:
        slope_avg = (slope_high + slope_low) / 2
        trend = 'bullish' if slope_avg > 0 else 'bearish'
        return {'pattern': 'channel', 'trend': trend, 'score': 2}
    return None

def detect_triangle(df, lookback=30, tolerance=0.02):
    """
    Detekcja trójkąta symetrycznego
    """
    highs = df['High'][-lookback:]
    lows = df['Low'][-lookback:]
    x = np.arange(lookback)

    high_slope, _, _, _, _ = linregress(x, highs)
    low_slope, _, _, _, _ = linregress(x, lows)

    if high_slope < 0 and low_slope > 0:
        if abs(high_slope - low_slope) < tolerance:
            return {'pattern': 'triangle', 'trend': 'neutral', 'score': 2}
    return None

def detect_flag(df, lookback=30):
    """
    Detekcja flagi po gwałtownym ruchu
    """
    df = df[-lookback:].copy()
    change = df['Close'].iloc[-1] / df['Close'].iloc[0] - 1

    if abs(change) > 0.03:
        highs = df['High']
        lows = df['Low']
        x = np.arange(lookback)
        slope_high, _, _, _, _ = linregress(x, highs)
        slope_low, _, _, _, _ = linregress(x, lows)

        if slope_high * slope_low > 0:
            trend = 'bullish' if slope_high > 0 else 'bearish'
            return {'pattern': 'flag', 'trend': trend, 'score': 2}
    return None

def detect_head_and_shoulders(df, lookback=50):
    """
    Prosty wykrywacz H&S lub odwróconego H&S
    """
    df = df[-lookback:].copy()
    prices = df['Close'].values

    if len(prices) < 7:
        return None

    peak1 = np.argmax(prices[:lookback//3])
    valley1 = np.argmin(prices[peak1:lookback//2]) + peak1
    peak2 = np.argmax(prices[valley1:]) + valley1

    if peak1 < valley1 < peak2:
        if prices[peak1] > prices[peak2] and prices[valley1] < min(prices[peak1], prices[peak2]):
            return {'pattern': 'head_and_shoulders', 'trend': 'bearish', 'score': 3}
        elif prices[peak1] < prices[peak2] and prices[valley1] > max(prices[peak1], prices[peak2]):
            return {'pattern': 'inverse_head_and_shoulders', 'trend': 'bullish', 'score': 3}
    return None

def detect_chart_patterns(df):
    """
    Główna funkcja agregująca detekcję wszystkich formacji
    """
    patterns = []

    for func in [detect_channel, detect_triangle, detect_flag, detect_head_and_shoulders]:
        result = func(df)
        if result:
            patterns.append(result)

    return patterns

def pattern_score(patterns):
    """
    Zwraca łączną punktację za wykryte formacje
    """
    return sum(p['score'] for p in patterns)
