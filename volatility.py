# volatility.py – RocketAlerts v12 ULTRA EXTREME

import pandas as pd
import numpy as np


def analyze_volatility(df):
    result = {
        "score": 0,
        "atr": None,
        "std_dev": None,
        "volume_spike": None,
        "volatility_cluster": None
    }

    if df is None or df.empty or len(df) < 20:
        return result

    try:
        df = df.copy()
        df["HL"] = df["High"] - df["Low"]
        df["HC"] = np.abs(df["High"] - df["Close"].shift(1))
        df["LC"] = np.abs(df["Low"] - df["Close"].shift(1))
        df["TR"] = df[["HL", "HC", "LC"]].max(axis=1)
        df["ATR"] = df["TR"].rolling(window=14).mean()

        atr = df["ATR"].iloc[-1]
        result["atr"] = atr

        df["STD"] = df["Close"].rolling(window=14).std()
        std_dev = df["STD"].iloc[-1]
        result["std_dev"] = std_dev

        df["Vol_Change"] = df["Volume"] / df["Volume"].rolling(window=20).mean()
        volume_spike = df["Vol_Change"].iloc[-1] > 1.5
        result["volume_spike"] = volume_spike

        # Klaster zmienności: kilka dużych świec z rzędu
        recent_ranges = df["TR"].tail(5)
        cluster_detected = (recent_ranges > recent_ranges.mean()).sum() >= 3
        result["volatility_cluster"] = cluster_detected

        # Scoring:
        score = 0
        if atr > 0 and atr > df["ATR"].mean():
            score += 1
        if std_dev > df["STD"].mean():
            score += 1
        if volume_spike:
            score += 1
        if cluster_detected:
            score += 1

        result["score"] = score

    except Exception as e:
        print(f"❌ Błąd analizy zmienności: {e}")

    return result
