# send_alert.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX
# Obsługa alertów przez Twilio (WhatsApp, SMS) + PDF + statusy

import os
from twilio.rest import Client
from config.config import (
    TWILIO_SID,
    TWILIO_TOKEN,
    TWILIO_WHATSAPP_FROM,
    WHATSAPP_TO,
    TWILIO_SMS_FROM,
    SMS_TO,
    USE_WHATSAPP,
    USE_SMS,
    DEBUG_MODE,
)

# Twilio client – jednokrotnie inicjalizowany
try:
    client = Client(TWILIO_SID, TWILIO_TOKEN)
except Exception as e:
    client = None
    print(f"❌ Błąd inicjalizacji Twilio Client: {e}")

def send_alert(message: str, channel: str = "whatsapp"):
    """
    Uniwersalna funkcja wysyłająca wiadomość przez WhatsApp lub SMS.
    """
    if not client:
        print("❌ Brak klienta Twilio.")
        return
    try:
        if channel == "whatsapp" and USE_WHATSAPP:
            client.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_FROM,
                to=WHATSAPP_TO
            )
            if DEBUG_MODE:
                print("✅ WhatsApp wysłany.")
        elif channel == "sms" and USE_SMS:
            client.messages.create(
                body=message,
                from_=TWILIO_SMS_FROM,
                to=SMS_TO
            )
            if DEBUG_MODE:
                print("✅ SMS wysłany.")
    except Exception as e:
        print(f"❌ Błąd wysyłki ({channel}): {e}")

def send_whatsapp_alert(message: str):
    send_alert(message, channel="whatsapp")

def send_sms_alert(message: str):
    send_alert(message, channel="sms")

def send_pdf_report(pdf_path: str, title: str = "📎 Raport PDF"):
    """
    Wysyła wiadomość informującą o wygenerowanym PDF lokalnie.
    (Twilio nie wspiera przesyłania plików przez WhatsApp)
    """
    if not client or not os.path.exists(pdf_path):
        print(f"❌ PDF nie istnieje: {pdf_path}")
        return
    try:
        msg = f"{title} został wygenerowany lokalnie i zapisany jako:\n`{os.path.basename(pdf_path)}`"
        send_whatsapp_alert(msg)
    except Exception as e:
        print(f"❌ Błąd wysyłki PDF: {e}")

def send_summary_alert(message: str):
    """
    Wysyła status systemu lub podsumowanie działania.
    """
    header = "📢 STATUS SYSTEMU:\n"
    full_msg = header + message
    send_whatsapp_alert(full_msg)

def test_alerts():
    """
    Test działania alertów.
    """
    send_whatsapp_alert("✅ Test WhatsApp – RocketAlerts działa.")
    send_sms_alert("✅ Test SMS – RocketAlerts działa.")
