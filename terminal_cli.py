# terminal_cli.py

import argparse
import pandas as pd
import os
from helpers import analyze_asset
from config.config import ASSETS, INTERVALS

def main():
    parser = argparse.ArgumentParser(description="RocketAlerts CLI Analyzer")
    parser.add_argument("--asset", type=str, required=True, help="Aktyw (np. BTC-USD)")
    parser.add_argument("--interval", type=str, required=True, help="Interwał (np. 1h)")
    args = parser.parse_args()

    asset = args.asset
    interval = args.interval
    filepath = f"data/{asset}_{interval}.csv"

    if not os.path.exists(filepath):
        print("❌ Brak danych dla:", asset, interval)
        return

    df = pd.read_csv(filepath)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")

    result = analyze_asset(asset, interval, df)
    print(f"\n🔍 ANALIZA: {asset} ({interval})")
    print(f"Sygnał: {result.get('signal')}")
    print(f"Score: {result.get('score')}")
    print(f"Prawdopodobieństwo sukcesu: {result.get('success_prob')}%")
    print(f"TP: {result.get('tp_price')} | SL: {result.get('sl_price')}")
    print(f"Trailing aktywny: {result.get('trailing_active')}")
    print(f"Makro: {result.get('macro_status')}")
    print(f"Formacje: {result.get('candle_pattern')} | BOS: {result.get('bos_status')}")
    print("✅ Gotowe.\n")

if __name__ == "__main__":
    main()
