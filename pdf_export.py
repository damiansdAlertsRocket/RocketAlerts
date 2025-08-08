# pdf_exporter.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX

import os
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from helpers import analyze_asset
from plot_utils import save_plot_as_png
from config.config import ASSETS, INTERVALS, LOCAL_TZ

OUTPUT_DIR = "output/pdf_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, '🚀 RocketAlerts – Raport Analizy Technicznej', ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(180, 180, 180)
        self.cell(0, 10, f'Strona {self.page_no()}', align='C')

def generate_report_for_asset(asset, interval):
    file = f"data/{asset}_{interval}.csv"
    if not os.path.exists(file):
        return None

    df = pd.read_csv(file)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")

    result = analyze_asset(asset, interval, df)
    fig = save_plot_as_png(
        generate_total_plot(df, result, ["ema", "bb", "rsi", "macd", "volume", "sl_tp", "signals", "fibo", "patterns"]),
        f"{OUTPUT_DIR}/{asset}_{interval}.png"
    )

    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "", 12)

    # Info
    signal = result.get("signal", "BRAK")
    score = result.get("score", 0)
    prob = result.get("success_probability", 0)
    breakdown = result.get("score_breakdown", "Brak danych")

    last = df["Date"].max().tz_localize("UTC").tz_convert(LOCAL_TZ)
    timestamp = last.strftime("%Y-%m-%d %H:%M:%S")

    pdf.cell(0, 10, f"🪙 Aktyw: {asset}", ln=True)
    pdf.cell(0, 10, f"⏱️ Interwał: {interval}", ln=True)
    pdf.cell(0, 10, f"📈 Sygnał: {signal} | Score: {score} | 🎯 Skuteczność: {prob}%", ln=True)
    pdf.cell(0, 10, f"🕒 Data: {timestamp} ({LOCAL_TZ.zone})", ln=True)
    pdf.ln(5)

    # Wykres
    pdf.image(f"{OUTPUT_DIR}/{asset}_{interval}.png", w=180)
    pdf.ln(5)

    # Breakdown
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6, f"{breakdown}")

    filename = f"{OUTPUT_DIR}/RA_{asset}_{interval}.pdf"
    pdf.output(filename)
    return filename

def generate_full_report():
    generated = []
    for asset in ASSETS:
        for interval in INTERVALS:
            print(f"📤 Generuję raport PDF: {asset} ({interval})...")
            path = generate_report_for_asset(asset, interval)
            if path:
                generated.append(path)
    print(f"✅ Wygenerowano {len(generated)} PDF-ów.")
    return generated
