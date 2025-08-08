import yfinance as yf
import pandas as pd
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 📌 Lista aktywów i interwałów
TICKERS = [
    "BTC-USD", "GC=F", "SI=F", "ETH-USD", "SOL-USD",
    "EURUSD=X", "USDJPY=X", "USD=X", "CL=F", "^IXIC", "AAPL", "TSLA"
]
INTERVALS = ["1m", "4h", "1d"]

# 📁 Ścieżki
DATA_DIR = "data"
CHART_DIR = "assets/wykresy"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHART_DIR, exist_ok=True)

# 🧮 Wskaźniki techniczne
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def compute_adx(df, period=14):
    df = df.copy()
    df["TR"] = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs()
    ], axis=1).max(axis=1)

    df["+DM"] = df["High"].diff()
    df["-DM"] = -df["Low"].diff()

    df["+DM"] = df["+DM"].where((df["+DM"] > df["-DM"]) & (df["+DM"] > 0), 0.0)
    df["-DM"] = df["-DM"].where((df["-DM"] > df["+DM"]) & (df["-DM"] > 0), 0.0)

    tr_smooth = df["TR"].rolling(window=period).mean()
    plus_dm_smooth = df["+DM"].rolling(window=period).mean()
    minus_dm_smooth = df["-DM"].rolling(window=period).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()
    return adx

def calculate_indicators(df):
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["RSI"] = compute_rsi(df["Close"], 14)
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = compute_macd(df["Close"])
    df["ADX"] = compute_adx(df)
    return df

# 🔁 Pobieranie i zapisywanie danych + wykresów
def process_ticker(ticker, interval):
    try:
        print(f"[⬇️] {ticker} ({interval})")
        data = yf.download(
            ticker,
            interval=interval,
            period="7d" if interval == "1m" else "60d" if interval == "4h" else "5y",
            progress=False,
            auto_adjust=True
        )

        if data.empty:
            print(f"⚠️ Brak danych: {ticker} ({interval})")
            return

        data = data[["Open", "High", "Low", "Close", "Volume"]].dropna()
        data = calculate_indicators(data).dropna()

        # 💾 Zapis CSV
        filepath = os.path.join(DATA_DIR, f"{ticker}_{interval}.csv")
        data.to_csv(filepath)

        # 🖼️ Wykres
        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1, 1]})
        fig.suptitle(f"{ticker} - {interval}", fontsize=14)

        axes[0].plot(data.index, data["Close"], label="Close", linewidth=1.5)
        axes[0].plot(data.index, data["EMA20"], label="EMA20", linestyle="--")
        axes[0].plot(data.index, data["EMA50"], label="EMA50", linestyle="--")
        axes[0].legend(loc="upper left")
        axes[0].set_ylabel("Cena")

        axes[1].plot(data.index, data["RSI"], label="RSI", color="orange")
        axes[1].axhline(70, color="red", linestyle="--", linewidth=0.5)
        axes[1].axhline(30, color="green", linestyle="--", linewidth=0.5)
        axes[1].set_ylabel("RSI")
        axes[1].legend(loc="upper left")

        axes[2].bar(data.index, data["MACD_hist"], label="MACD_hist", color="gray")
        axes[2].plot(data.index, data["MACD"], label="MACD", color="blue", linewidth=0.8)
        axes[2].plot(data.index, data["MACD_signal"], label="Signal", color="red", linewidth=0.8)
        axes[2].legend(loc="upper left")
        axes[2].set_ylabel("MACD")

        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        chart_path = os.path.join(CHART_DIR, f"{ticker}_{interval}.png")
        plt.savefig(chart_path)
        plt.close()
        print(f"[📊] Wygenerowano {chart_path}")

    except Exception as e:
        print(f"❌ Błąd dla {ticker} ({interval}): {e}")

if __name__ == "__main__":
    print("🚀 Pobieranie danych i generowanie wykresów...")
    for ticker in TICKERS:
        for interval in INTERVALS:
            process_ticker(ticker, interval)
    print("🏁 Gotowe.")
