# risk.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX

import numpy as np
import pandas as pd

from config.config import (
    ATR_PERIOD,
    ATR_SL_MULTIPLIER,
    ATR_TP_MULTIPLIER,
    TP_AT_RESISTANCE,
    SL_AT_SUPPORT,
    TRAILING_ATR_MULTIPLIER,
    USE_TRAILING_SL,
)

# === RR – Reward-to-Risk
def _effective_rr(entry: float, sl: float, tp: float) -> float:
    try:
        if entry == sl:
            return 0.0
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        return round(reward / risk, 2) if risk != 0 else 0.0
    except Exception:
        return 0.0

# === Oblicz wielkość pozycji
def position_size(equity: float, risk_pct: float, entry: float, sl: float) -> float:
    try:
        risk_amount = equity * (risk_pct / 100)
        stop_loss_distance = abs(entry - sl)
        if stop_loss_distance == 0:
            return 0.0
        size = risk_amount / stop_loss_distance
        return round(size, 4)
    except Exception:
        return 0.0

# === SL/TP na bazie ATR
def calculate_dynamic_sl_tp(df: pd.DataFrame, signal: str) -> tuple:
    try:
        df = df.copy()
        df["TR"] = np.maximum.reduce([
            df["High"] - df["Low"],
            abs(df["High"] - df["Close"].shift(1)),
            abs(df["Low"] - df["Close"].shift(1))
        ])
        df["ATR"] = df["TR"].rolling(window=ATR_PERIOD).mean()

        latest = df.iloc[-1]
        atr = latest["ATR"]
        close = latest["Close"]

        if signal == "BUY":
            sl = close - ATR_SL_MULTIPLIER * atr
            tp = close + ATR_TP_MULTIPLIER * atr
        elif signal == "SELL":
            sl = close + ATR_SL_MULTIPLIER * atr
            tp = close - ATR_TP_MULTIPLIER * atr
        else:
            sl, tp = None, None

        return float(sl), float(tp)
    except Exception:
        return None, None

# === Optymalizacja TP/SL (np. opór/wsparcie, BB)
def optimize_sl_tp(df: pd.DataFrame, sl: float, tp: float, signal: str) -> tuple:
    try:
        df = df.copy()
        close = float(df["Close"].iloc[-1])

        if "BB_upper" in df.columns and "BB_lower" in df.columns:
            upper = df["BB_upper"].iloc[-1]
            lower = df["BB_lower"].iloc[-1]
            if TP_AT_RESISTANCE:
                if signal == "BUY":
                    tp = min(tp, upper)
                elif signal == "SELL":
                    tp = max(tp, lower)
            if SL_AT_SUPPORT:
                if signal == "BUY":
                    sl = max(sl, lower)
                elif signal == "SELL":
                    sl = min(sl, upper)

        return float(sl), float(tp)
    except Exception:
        return sl, tp

# === Trailing SL – aktualizacja pozycji
def update_trailing_sl_tp(df: pd.DataFrame, sl: float, tp: float, signal: str, entry: float) -> float:
    if not USE_TRAILING_SL:
        return sl
    try:
        df = df.copy()
        df["TR"] = np.maximum.reduce([
            df["High"] - df["Low"],
            abs(df["High"] - df["Close"].shift(1)),
            abs(df["Low"] - df["Close"].shift(1))
        ])
        df["ATR"] = df["TR"].rolling(window=ATR_PERIOD).mean()
        atr = df["ATR"].iloc[-1]
        price = df["Close"].iloc[-1]

        if signal == "BUY":
            profit = price - entry
            if profit >= (tp - entry) * 0.5:
                new_sl = price - TRAILING_ATR_MULTIPLIER * atr
                sl = max(sl, new_sl)
        elif signal == "SELL":
            profit = entry - price
            if profit >= (entry - tp) * 0.5:
                new_sl = price + TRAILING_ATR_MULTIPLIER * atr
                sl = min(sl, new_sl)

        return float(sl)
    except Exception:
        return sl
