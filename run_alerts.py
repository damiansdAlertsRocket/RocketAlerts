import os
import pandas as pd
from datetime import datetime
from helpers import analyze_asset, calculate_dynamic_sl_tp, save_plot_as_png
from ai_model import predict_asset, predict_proba
from pdf_export import generate_pdf_report
from send_alert import send_summary_alert
import logging, sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Lista aktywów i interwałów
ASSETS = [
    "BTC-USD", "ETH-USD", "SOL-USD",
    "GC=F", "CL=F", "TSLA", "AAPL"
]
INTERVALS = ["1d", "4h"]

# Upewnij się, że folder z logami istnieje
os.makedirs("logs", exist_ok=True)

def run_alerts():
    for asset in ASSETS:
        for interval in INTERVALS:
            try:
                file_path = f"data/{asset}_{interval}.csv"
                if not os.path.exists(file_path):
                    print(f"❌ Brak danych: {file_path}")
                    continue

                df = pd.read_csv(file_path)
                df["Date"] = pd.to_datetime(df["Date"])

                # AI prognoza
                ai_signal = predict_asset(df, asset, interval)            # np. ("KUP", "WYSOKA")
                confidence = predict_proba(df, asset, interval)           # np. 99.73

                # Techniczna analiza
                tech_signal, strength = analyze_asset(df, asset, interval)

                # Filtr – tylko silne sygnały
                if strength != "WYSOKA":
                    print(f"⚠️ Pomijam {asset} ({interval}) – siła {strength}")
                    continue

                # SL/TP (na podstawie sygnału AI)
                direction = ai_signal[0] if isinstance(ai_signal, tuple) else ai_signal
                sl, tp = calculate_dynamic_sl_tp(df, direction)

                # Wykres PNG
                chart_path = save_plot_as_png(
                    df=df,
                    asset=asset,
                    interval=interval,
                    signal=ai_signal,
                    sl=sl,
                    tp=tp,
                    ai_forecast=None  # jeśli masz linię prognozy AI, tu możesz podać listę wartości
                )

                # PDF raport
                out_path = f"assets/pdf/{asset}_{interval}.pdf"
                pdf_path = generate_pdf_report(
                    asset=asset,
                    interval=interval,
                    signal=tech_signal,
                    strength=strength,
                    forecast=ai_signal,
                    confidence=confidence,
                    sl=sl,
                    tp=tp,
                    png_path=chart_path
                )

                # Treść wiadomości
                ai_label, ai_strength = ai_signal if isinstance(ai_signal, tuple) else (ai_signal, "")
                message = f"""
📈 *{asset}* ({interval})
🧠 AI: *{ai_label}* ({ai_strength}) ({confidence:.2f}%)
📊 Siła techniczna: {strength}
🎯 SL: {sl} | TP: {tp}
📎 PDF: {pdf_path}
                """.strip()

                send_summary_alert(message, pdf_path=pdf_path)

                # Log do pliku CSV
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open("logs/alerts_log.csv", "a", encoding="utf-8") as log:
                    log.write(f"{now},{asset},{interval},{ai_label},{ai_strength},{sl},{tp},{pdf_path}\n")

                print(f"✅ Alert: {asset} ({interval})")

            except Exception as e:
                print(f"❌ Błąd przy {asset} ({interval}): {e}")

if __name__ == "__main__":
    run_alerts()
