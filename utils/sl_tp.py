def calculate_dynamic_sl_tp(df, signal: str, atr_multiplier_sl=1.5, atr_multiplier_tp=2.5):
    """
    Oblicza poziomy SL (Stop Loss) i TP (Take Profit) na podstawie ATR.

    Parametry:
    - df: DataFrame z kolumnami 'High', 'Low', 'Close'
    - signal: 'KUP', 'SPRZEDAJ' lub 'BRAK'
    - atr_multiplier_sl: mnożnik ATR do SL
    - atr_multiplier_tp: mnożnik ATR do TP

    Zwraca:
    - (SL, TP) zaokrąglone do 2 miejsc
    """

    if df is None or df.empty:
        raise ValueError("Brak danych do obliczenia SL/TP")

    if not all(col in df.columns for col in ['Close', 'High', 'Low']):
        raise ValueError("Brakuje wymaganych kolumn (Close, High, Low)")

    df = df.copy()
    df['range'] = df['High'] - df['Low']
    df['ATR'] = df['range'].rolling(window=14).mean()

    atr = df['ATR'].iloc[-1]
    close = df['Close'].iloc[-1]

    if pd.isna(atr):
        return None, None

    if signal == "KUP":
        sl = close - atr * atr_multiplier_sl
        tp = close + atr * atr_multiplier_tp
    elif signal == "SPRZEDAJ":
        sl = close + atr * atr_multiplier_sl
        tp = close - atr * atr_multiplier_tp
    else:
        sl = tp = None

    return round(sl, 2), round(tp, 2)
