import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

def extract_features(df):
    df = df.copy()
    df["EMA20"] = EMAIndicator(df["Close"]).ema_indicator()
    df["EMA50"] = EMAIndicator(df["Close"], window=50).ema_indicator()
    df["MACD"] = MACD(df["Close"]).macd()
    df["MACD_signal"] = MACD(df["Close"]).macd_signal()
    df["RSI"] = RSIIndicator(df["Close"]).rsi()
    df["ADX"] = ADXIndicator(df["High"], df["Low"], df["Close"]).adx()
    bb = BollingerBands(df["Close"])
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_middle"] = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()
    df["ATR"] = AverageTrueRange(df["High"], df["Low"], df["Close"]).average_true_range()
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    df["price_range"] = df["High"] - df["Low"]
    df["close_open"] = df["Close"] - df["Open"]
    df["trend_slope"] = df["Close"].rolling(5).mean().diff()
    df.dropna(inplace=True)

    return df[[
        'Open', 'High', 'Low', 'Close', 'Volume',
        'EMA20', 'EMA50', 'MACD', 'MACD_signal', 'RSI', 'ADX',
        'BB_upper', 'BB_middle', 'BB_lower', 'ATR',
        'log_return', 'price_range', 'close_open', 'trend_slope'
    ]]
