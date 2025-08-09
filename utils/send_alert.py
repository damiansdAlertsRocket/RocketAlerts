import logging
logger = logging.getLogger(__name__)
from twilio.rest import Client
import os

# Dane Twilio
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TO_PHONE = os.getenv("TO_PHONE", "whatsapp:+48785122240")
USE_WHATSAPP = os.getenv("USE_WHATSAPP", "True") == "True"

client = Client(TWILIO_SID, TWILIO_TOKEN)

def send_alert(message: str, label=None):
    try:
        full_message = f"[{label}] {message}" if label else message
        msg = client.messages.create(
            body=full_message,
            from_=TWILIO_PHONE,
            to=TO_PHONE
        )
        logger.info(f"✅ Wysłano wiadomość: SID {msg.sid}")
    except Exception as e:
        logger.error(f"❌ Błąd wysyłania: {e}")

def send_summary_alert(asset, interval, signal, strength, sl, tp, pdf_path=None):
    """
    Wysyła alert WhatsApp lub SMS z informacjami o sygnale AI.
    """
    message = f"""📢 [ALERT TEST]
📊 Aktywum: {asset}
⏱️ Interwał: {interval}
🧠 AI Sygnał: {signal}
🔥 Siła: {strength}
🎯 SL: {round(sl, 2)}
🎯 TP: {round(tp, 2)}"""

    if pdf_path:
        message += f"\n📎 Wykres: {pdf_path}"

    send_alert(message)
