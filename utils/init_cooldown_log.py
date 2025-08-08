import logging
logger = logging.getLogger(__name__)
import os
import pandas as pd
import logging

def init_cooldown_log():
    path = "logs/cooldown_log.csv"
    os.makedirs("logs", exist_ok=True)
    required_columns = ["asset", "interval", "last_alert_time"]

    # Utwórz plik, jeśli nie istnieje
    if not os.path.exists(path):
        logger.info("🛠️ cooldown_log.csv nie istnieje – tworzę...")
        df = pd.DataFrame(columns=required_columns)
        df.to_csv(path, index=False)
        return

    try:
        df = pd.read_csv(path)

        # Sprawdź brakujące kolumny
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            logger.warning(f"⚠️ Brakuje kolumn: {missing} – naprawiam cooldown_log.csv")
            raise ValueError("Błędne kolumny")

        # Sprawdź typ danych
        if df.empty or df.isnull().all().all():
            raise ValueError("Plik pusty lub zawiera tylko NaN")

        # OK
        logger.info("✅ cooldown_log.csv OK.")

    except Exception as e:
        logger.error(f"❌ cooldown_log.csv uszkodzony: {e} – nadpisuję poprawną wersją")
        df = pd.DataFrame(columns=required_columns)
        df.to_csv(path, index=False, encoding="utf-8")
