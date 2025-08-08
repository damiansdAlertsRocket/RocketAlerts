import os
import csv
from datetime import datetime

def log_alert(asset, interval, score, signal, strength, sl, tp):
    os.makedirs("logs", exist_ok=True)
    path = "logs/alerts_log.csv"
    headers = ["timestamp", "asset", "interval", "score", "signal", "strength", "SL", "TP"]

    row = [datetime.now().strftime("%Y-%m-%d %H:%M"), asset, interval, round(score, 2), signal, strength, round(sl, 2), round(tp, 2)]

    file_exists = os.path.isfile(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)
