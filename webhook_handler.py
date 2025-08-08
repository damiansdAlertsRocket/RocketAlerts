# webhook_handler.py – RocketAlerts v12 ULTRA EXTREME – obsługa webhooka
from flask import Flask, request, jsonify
from config.config import WEBHOOK_SECRET, USE_WHATSAPP
from send_alert import send_whatsapp_alert, send_summary_alert

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    token = request.headers.get("X-Webhook-Token")
    if token != WEBHOOK_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    try:
        data = request.json

        # Obsługa alertu – oczekiwane dane:
        # { "symbol": "BTC-USD", "interval": "1h", "message": "BUY SIGNAL at 42,000", "priority": "high" }

        symbol = data.get("symbol", "UNKNOWN")
        interval = data.get("interval", "UNKNOWN")
        message = data.get("message", "No message provided.")
        priority = data.get("priority", "normal").upper()

        final_msg = f"🚀 WEBHOOK ALERT\n📈 {symbol} ({interval})\n🧠 {message}\n🔐 Source: webhook"

        if priority == "HIGH":
            send_whatsapp_alert(final_msg)
        else:
            send_summary_alert(final_msg)

        return jsonify({"status": "success", "received": data}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5050, debug=False, use_reloader=False)
