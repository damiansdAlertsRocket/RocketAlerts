# pdf_exporter.py

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from helpers import analyze_asset
from plot_utils import save_plot_as_png
from heatmap_view import generate_heatmap_data
from multi_timeframe_analysis import get_multi_tf_alignment
from config.config import ASSETS, INTERVALS

def export_full_report():
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    pdf_path = f"reports/RocketReport_{timestamp}.pdf"
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4

    for asset in ASSETS:
        for interval in INTERVALS:
            df_path = f"data/{asset}_{interval}.csv"
            if not os.path.exists(df_path):
                continue

            # === ANALIZA
            import pandas as pd
            df = pd.read_csv(df_path)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values("Date")
            result = analyze_asset(asset, interval, df)

            # === WYKRES
            chart_file = f"{asset}_{interval}.png"
            save_plot_as_png(df, result, asset, interval, filename=chart_file)

            # === STRONA PDF
            c.showPage()
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, height - 40, f"{asset} ({interval}) – Score: {result.get('score', 0)}")

            c.setFont("Helvetica", 10)
            c.drawString(40, height - 60, f"Sygnał: {result.get('signal', 'BRAK')} | TP: {result.get('tp_price')} | SL: {result.get('sl_price')}")

            # === ZGODNOŚĆ MTF
            mtf = get_multi_tf_alignment(asset)
            c.drawString(40, height - 80, f"MTF: {mtf['alignment']}")

            # === Obraz
            img_path = os.path.join("charts", chart_file)
            if os.path.exists(img_path):
                c.drawImage(img_path, 40, 120, width=520, preserveAspectRatio=True, mask='auto')

    # === HEATMAPA
    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 40, "Heatmapa Sygnalna")
    heatmap_df = generate_heatmap_data()

    y = height - 60
    c.setFont("Helvetica", 8)
    for asset in heatmap_df.index:
        row = f"{asset}: " + ", ".join([f"{iv}: {heatmap_df.loc[asset, iv]}" for iv in heatmap_df.columns])
        c.drawString(40, y, row)
        y -= 10
        if y < 100:
            c.showPage()
            y = height - 60

    c.save()
    print(f"✅ Zapisano PDF: {pdf_path}")
