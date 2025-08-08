import requests
import pandas as pd
from .symbols import symbols
from .utils import convert_tf, df_from_response


class TvDatafeed:
    def __init__(self, username=None, password=None, session=None, sessionid_sign=None):
        self.session = requests.Session()
        self.session.headers.update({
            "Referer": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0",
        })

        if session and sessionid_sign:
            self.session.cookies.set("sessionid", session)
            self.session.cookies.set("sessionid_sign", sessionid_sign)
        elif username and password:
            raise NotImplementedError("Login method via username/password is not supported in this fork.")
        else:
            raise ValueError("You must provide either username/password or session/sessionid_sign.")

    def get_hist(self, symbol, exchange, interval='1d', n_bars=1000):
        symbol_info = symbols.get(exchange.upper(), {}).get(symbol.upper())
        if not symbol_info:
            symbol_info = {"symbol": symbol.upper(), "exchange": exchange.upper()}

        payload = {
            "symbol": f"{symbol_info['exchange']}:{symbol_info['symbol']}",
            "resolution": convert_tf(interval),
            "from": 0,
            "to": 9999999999,
            "countback": n_bars,
        }

        url = "https://www.tradingview.com/bars"
        response = self.session.get(url, params=payload)

        if response.status_code != 200:
            raise Exception(f"HTTP error {response.status_code}")

        return df_from_response(response.json())
