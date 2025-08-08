import time
import requests
from send_alert import send_summary_alert
import subprocess

# ✅ Sprawdzenie czy jest połączenie z Internetem
def is_connected():
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except:
        return False

# ✅ Monitoruj sieć i reaguj na rozłączenie
def monitor_network():
    while True:
        if not is_connected():
            print("❌ Brak Internetu! Wysyłam alert...")
            send_summary_alert("🚨 Utracono połączenie z Internetem! RocketAlerts zatrzymane.")
            time.sleep(10)

            # 🔁 Opcjonalny restart systemu / skryptu
            subprocess.call(["python", "uruchom_alerty.py"])

        time.sleep(30)
