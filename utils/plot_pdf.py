import os
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF

def generate_chart_pdf(asset, interval):
    filepath = f"data/{asset}_{interval}.csv"
    if not os.path.exists(filepath):
        return None

    df = pd.read_csv(filepath)
    df = df.dropna().tail(100)

    pdf_path = f"assets/alerts/{asset}_{interval}.pdf"
    os.makedirs("assets/alerts", exist_ok=True)

    # 📈 Wykres
    plt.figure(figsize=(10, 4))
    plt.plot(df['Close'], label="Close", linewidth=1.5)
    if 'EMA20' in df.columns:
        plt.plot(df['EMA20'], label="EMA20", linestyle="--")
    if 'EMA50' in df.columns:
        plt.plot(df['EMA50'], label="EMA50", linestyle="--")
    plt.title(f"{asset} ({interval})")
    plt.legend()
    plt.tight_layout()

    # Zapis jako PNG
    temp_png = "temp_chart.png"
    plt.savefig(temp_png)
    plt.close()

    # Konwertuj do PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.image(temp_png, x=10, y=10, w=180)
    pdf.output(pdf_path)
    os.remove(temp_png)

    return pdf_path
