import logging
logger = logging.getLogger(__name__)
import requests

def get_ngrok_url():
    """
    Pobiera publiczny adres URL tunelu NGROK (https preferowane).
    """
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=3)
        data = response.json()
        tunnels = data.get("tunnels", [])

        # Preferuj HTTPS
        for t in tunnels:
            if t.get("proto") == "https":
                return t.get("public_url")

        # Fallback do HTTP
        for t in tunnels:
            if t.get("proto") == "http":
                return t.get("public_url")

        logger.warning("⚠️ Brak aktywnego tunelu NGROK")
    except requests.exceptions.ConnectionError:
        logger.error("❌ NGROK API nie działa – upewnij się, że NGROK jest uruchomiony.")
    except Exception as e:
        logger.error(f"❌ Błąd pobierania NGROK URL: {e}")

    return None
