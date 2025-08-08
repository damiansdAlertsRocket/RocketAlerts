from tvDatafeed import TvDatafeed

# Podstawienie danych sesyjnych
session = 'a6zf113ch7r2osv95qzowmb6predu0fg'
session_sign = 'v3:f33979tBicvmMI5mMci+xLjPf8DUa3bGM30tWgr63Jk='

tv = TvDatafeed(session=session, sessionid_sign=session_sign)

# Przykład pobrania danych
df = tv.get_hist(symbol='BTCUSD', exchange='BINANCE', interval='1', n_bars=100)

print(df.head())
