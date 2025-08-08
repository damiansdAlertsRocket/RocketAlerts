import requests
import time
import logging

log = logging.getLogger(__name__)

def http_get_json(url, params=None, retries=3, backoff=2):
    """
    Pobiera dane JSON z podanego URL z mechanizmem retry.
    Zwraca (data, status_code)
    """
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json(), 200
            else:
                log.warning(f"⚠️ HTTP {response.status_code} for URL: {url}")
                return None, response.status_code
        except Exception as e:
            log.warning(f"⚠️ Błąd połączenia: {e}")
            time.sleep(backoff)
    return None, None
