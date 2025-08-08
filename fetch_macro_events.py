# fetch_macro_events.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (z EODHD i fallback)

import os
import pandas as pd
import requests
from datetime import datetime
from config.config import DATA_FOLDER, MACRO_EVENTS_FILE, EODHD_API_KEY

def fetch_macro_events_from_sources():
    try:
        url = f"https://eodhd.com/api/economic-events?api_token={EODHD_API_KEY}&fmt=json"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            raise ValueError(f"Błąd EODHD: HTTP {response.status_code}")

        data = response.json()

        if not isinstance(data, list):
            raise ValueError("Niepoprawny format danych z EODHD")

        records = []
        for event in data:
            try:
                records.append({
                    "date": pd.to_datetime(event.get("date", None)),
                    "country": event.get("country", ""),
                    "event": event.get("event", ""),
                    "impact": event.get("impact", ""),
                    "latest": event.get("actual", 0),
                    "forecast": event.get("estimate", 0),
                    "previous": event.get("previous", 0)
                })
            except Exception as parse_error:
                print(f"⚠️ Błąd parsowania rekordu: {parse_error}")

        df = pd.DataFrame(records)
        if df.empty:
            raise ValueError("Brak danych makroekonomicznych po przetworzeniu.")

        df["date"] = pd.to_datetime(df["date"])
        os.makedirs(DATA_FOLDER, exist_ok=True)
        df.to_csv(MACRO_EVENTS_FILE, index=False)
        print(f"📄 Zapisano plik makro: {MACRO_EVENTS_FILE} ({len(df)} rekordów)")
        return df

    except Exception as e:
        print(f"⚠️ Błąd pobierania danych makro z EODHD: {e}")
        print("🧪 Zastosowano fallback – dane testowe.")

        # Dane testowe fallback
        fallback_events = [
            {
                "date": "2099-12-31",
                "country": "US",
                "event": "Fallback CPI",
                "impact": "High",
                "latest": 0,
                "forecast": 0,
                "previous": 0
            },
            {
                "date": "2099-12-31",
                "country": "US",
                "event": "Fallback Interest Rate",
                "impact": "High",
                "latest": 0,
                "forecast": 0,
                "previous": 0
            }
        ]
        df = pd.DataFrame(fallback_events)
        df["date"] = pd.to_datetime(df["date"])
        os.makedirs(DATA_FOLDER, exist_ok=True)
        df.to_csv(MACRO_EVENTS_FILE, index=False)
        print(f"📄 Zapisano fallback plik makro: {MACRO_EVENTS_FILE}")
        return df

if __name__ == "__main__":
    fetch_macro_events_from_sources()
