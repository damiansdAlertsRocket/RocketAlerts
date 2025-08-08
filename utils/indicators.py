import logging
logger = logging.getLogger(__name__)
import pandas as pd
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange

def load_technical_indicators(df):
    df = df.copy()

    # Konwersja danych na numeryczne typy
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # EMA
    df['EMA20'] = EMAIndicator(close=df['Close'], window=20).ema_indicator()
    df['EMA50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()

    # RSI
    df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()

    # MACD
    macd = MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()

    # ADX
    df['ADX'] = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14).adx()

    # Bollinger Bands
    bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_middle'] = bb.bollinger_mavg()
    df['BB_lower'] = bb.bollinger_lband()

    # ✅ ATR — wymagany do SL/TP
    df['ATR'] = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14).average_true_range()

    return df

def analyze_asset(df, asset, interval):
    try:
        df = load_technical_indicators(df)
        df = df.dropna().copy()
        last = df.iloc[-1]

        signal_votes = []

        # Logika głosowania
        if last['Close'] > last['EMA20'] and last['EMA20'] > last['EMA50']:
            signal_votes.append('KUP')
        if last['RSI'] > 70:
            signal_votes.append('SPRZEDAJ')
        elif last['RSI'] < 30:
            signal_votes.append('KUP')
        if last['MACD'] > last['MACD_signal']:
            signal_votes.append('KUP')
        else:
            signal_votes.append('SPRZEDAJ')
        if last['ADX'] > 25:
            signal_votes.append('KUP')
        if last['Close'] > last['BB_upper']:
            signal_votes.append('SPRZEDAJ')
        elif last['Close'] < last['BB_lower']:
            signal_votes.append('KUP')

        kup = signal_votes.count('KUP')
        sprzedaj = signal_votes.count('SPRZEDAJ')

        if kup > sprzedaj:
            signal = "KUP"
        elif sprzedaj > kup:
            signal = "SPRZEDAJ"
        else:
            signal = "BRAK"

        strength = "WYSOKA" if abs(kup - sprzedaj) >= 3 else "ŚREDNIA" if abs(kup - sprzedaj) == 2 else "NISKA"

        return signal, strength

    except Exception as e:
        logger.error(f"❌ Błąd w analizie technicznej ({asset} {interval}): {e}")
        return None, None
