## backtest_model.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX

import os
import pandas as pd
from helpers import analyze_asset
from risk import calculate_dynamic_sl_tp, optimize_sl_tp, update_trailing_sl_tp
from config.config import ASSETS, INTERVALS

def run_backtest_on_asset(asset, interval, df, debug=False):
    if df is None or df.empty or len(df) < 50:
        return {"asset": asset, "interval": interval, "trades": 0}

    results = []
    position = None
    entry_price = sl = tp = None

    for i in range(30, len(df)):
        sub_df = df.iloc[:i+1].copy()
        row = df.iloc[i]
        date = row["Date"]
        close = row["Close"]

        # analiza na świecy i
        analysis = analyze_asset(asset, interval, sub_df)
        signal = analysis.get("signal", "BRAK")
        score = analysis.get("score", 0)
        prob = analysis.get("probability", 0)

        # warunek wejścia
        if position is None and signal in ["KUP", "SPRZEDAJ"] and score >= 1.5:
            sl0, tp0 = calculate_dynamic_sl_tp(sub_df)
            sl, tp = optimize_sl_tp(sub_df, sl0, tp0)
            entry_price = close
            position = signal
            entry_index = i
            continue

        # trailing i wyjście
        if position:
            current_price = close
            sl, tp = update_trailing_sl_tp(current_price, sl, tp)

            if position == "KUP":
                if current_price <= sl:
                    results.append({
                        "entry": entry_price, "exit": current_price,
                        "result": "SL", "direction": "LONG",
                        "date": date, "pnl_pct": round((current_price - entry_price)/entry_price * 100, 2)
                    })
                    position = None
                elif current_price >= tp:
                    results.append({
                        "entry": entry_price, "exit": current_price,
                        "result": "TP", "direction": "LONG",
                        "date": date, "pnl_pct": round((current_price - entry_price)/entry_price * 100, 2)
                    })
                    position = None

            elif position == "SPRZEDAJ":
                if current_price >= sl:
                    results.append({
                        "entry": entry_price, "exit": current_price,
                        "result": "SL", "direction": "SHORT",
                        "date": date, "pnl_pct": round((entry_price - current_price)/entry_price * 100, 2)
                    })
                    position = None
                elif current_price <= tp:
                    results.append({
                        "entry": entry_price, "exit": current_price,
                        "result": "TP", "direction": "SHORT",
                        "date": date, "pnl_pct": round((entry_price - current_price)/entry_price * 100, 2)
                    })
                    position = None

    if debug:
        print(f"✅ Backtest {asset} ({interval}): {len(results)} transakcji")

    return {
        "asset": asset,
        "interval": interval,
        "trades": len(results),
        "wins": sum(1 for r in results if r["result"] == "TP"),
        "losses": sum(1 for r in results if r["result"] == "SL"),
        "avg_pnl": round(pd.Series([r["pnl_pct"] for r in results]).mean(), 2) if results else 0,
        "max_dd": round(pd.Series([r["pnl_pct"] for r in results]).min(), 2) if results else 0,
        "results": results
    }

def run_all_backtests():
    os.makedirs("backtests", exist_ok=True)
    summary = []

    for asset in ASSETS:
        for interval in INTERVALS:
            file = f"data/{asset}_{interval}.csv"
            if not os.path.exists(file):
                print(f"⚠️ Brak pliku: {file}")
                continue
            df = pd.read_csv(file)
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")
            result = run_backtest_on_asset(asset, interval, df)
            summary.append(result)

            # zapis wyników szczegółowych
            trades_df = pd.DataFrame(result["results"])
            trades_df.to_csv(f"backtests/{asset}_{interval}_trades.csv", index=False)

    # zapis podsumowania
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("backtests/backtest_summary.csv", index=False)
    print("✅ Zakończono backtest wszystkich aktywów.")

    return summary_df
