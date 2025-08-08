# scheduler.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (POPRAWIONY)

import schedule
import time
import os
from datetime import datetime
import pytz
import requests
import subprocess
import logging

from utils.init_cooldown_log import init_cooldown_log
init_cooldown_log()
from generate_data import generate_all_data
from alerts import run_all
from fetch_macro_events import fetch_macro_events_from_sources
from send_alert import send_whatsapp_alert
from config.config import LOCAL_TZ, DEBUG_MODE

TZ = LOCAL_TZ

# === Logging ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8")
    ]
)

# === Tworzenie cooldown_log.csv jeśli nie istnieje ===
def ensure_cooldown_log_exists():
    filepath = "logs/cooldown_log.csv"
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write("asset,interval,last_signal_time\n")
        logging.info("📄 Utworzono pusty cooldown_log.csv")

# === Sprawdzanie internetu ===
def is_connected() -> bool:
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except:
        return False

# === Zadania ===
def job_data():
    logging.info("🔄 [job_data] Generowanie danych start...")
    try:
        generate_all_data()
        logging.info("✅ [job_data] Generowanie danych zakończone.")
    except Exception as e:
        logging.error(f"❌ [job_data] Błąd: {e}")

def job_alerts():
    logging.info("🚨 [job_alerts] Sprawdzanie alertów start...")
    try:
        run_all()
        logging.info("✅ [job_alerts] Sprawdzanie alertów zakończone.")
    except Exception as e:
        logging.error(f"❌ [job_alerts] Błąd: {e}")

def job_macro():
    logging.info("🌍 [job_macro] Aktualizacja danych makro start...")
    try:
        df = fetch_macro_events_from_sources()
        if df is not None and not df.empty:
            logging.info(f"✅ [job_macro] Dane makro: {len(df)} rekordów")
        else:
            logging.warning("⚠️ [job_macro] Brak danych makro – zapisano nagłówki.")
    except Exception as e:
        logging.error(f"❌ [job_macro] Błąd: {e}")

def job_status():
    logging.info("📨 [job_status] Wysyłanie powiadomienia o statusie systemu...")
    try:
        send_whatsapp_alert("✅ System RocketAlerts v12 działa poprawnie.")
        logging.info("✅ [job_status] Powiadomienie wysłane.")
    except Exception as e:
        logging.error(f"❌ [job_status] Błąd wysyłania statusu: {e}")

# === Harmonogram zadań ===
schedule.every(5).minutes.do(job_data)
schedule.every(6).minutes.do(job_alerts)  # ZAWSZE PO danych
schedule.every().hour.at(":30").do(job_macro)
schedule.every().day.at("00:00").do(job_status)

# === Uruchamianie zaplanowanych zadań ===
def run_scheduler():
    logging.info("🟢 Scheduler wystartował.")
    while True:
        if is_connected():
            schedule.run_pending()
        else:
            logging.warning("❌ Brak połączenia z internetem.")
        time.sleep(30)

# === Uruchamianie webhooka i dashboardu w tle ===
def run_background_services():
    try:
        subprocess.Popen(["python", "webhook_handler.py"])
        logging.info("🔔 Webhook uruchomiony na porcie 5050.")
    except Exception as e:
        logging.error(f"❌ Błąd uruchamiania webhook_handler.py: {e}")

    try:
        subprocess.Popen(["python", "dashboard.py"])
        logging.info("📊 Dashboard Dash uruchomiony na porcie 8051.")
    except Exception as e:
        logging.error(f"❌ Błąd uruchamiania dashboard.py: {e}")

# === Start systemu ===
if __name__ == "__main__":
    logging.info("🚀 Start systemu RocketAlerts v12 ULTRA EXTREME TOTAL MAX")
    ensure_cooldown_log_exists()
    job_data()
    job_alerts()
    job_macro()
    job_status()
    run_background_services()
    run_scheduler()
