import os
import pytz
from datetime import time

# === 📁 Ścieżki ===
PROJECT_FOLDER       = os.path.join("R:\\", "RocketAlerts")
DATA_FOLDER          = "data"
LOG_FOLDER           = "logs"
ALERTS_LOG_PATH      = f"{LOG_FOLDER}/alerts_log.csv"
COOLDOWN_LOG_PATH    = f"{LOG_FOLDER}/cooldown_log.csv"
PERFORMANCE_LOG_PATH = f"{LOG_FOLDER}/performance_log.csv"
MACRO_EVENTS_FILE    = f"{DATA_FOLDER}/macro_events.csv"
ASSETS_FOLDER        = "assets"
MODELS_FOLDER        = "ai_models"

# === 🔑 Klucze API ===
EODHD_API_KEY  = "688bc5e1dc6fc8.88803033"
TWELVE_API_KEY = "2a4f9dba2af744a9bd82f956a1831cb7"

# === 🌍 Strefa czasowa ===
LOCAL_TZ = pytz.timezone("Europe/Amsterdam")

# === ⚙️ Tryby działania ===
DEBUG_MODE  = False
TEST_MODE   = False
TRADER_MODE = True

# === 🛡️ Bezpieczeństwo ===
SECURITY_PIN = "6532"

# === ✅ Aktywa i interwały ===
ASSETS = [
    "BTC-USD", "ETH-USD", "SOL-USD",
    "EURUSD=X", "AUDJPY=X", "USDJPY=X", "GBPUSD=X",
    "GOLD", "SILVER",
    "^GSPC", "^DJI", "^IXIC", "FTSE100", "NASDAQ", "DJ30"
]
INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

# === ⏰ Zasady sesji handlowych ===
SESSION_FILTER_ENABLED = True
SESSION_WHITELIST = ["00:00-23:59"]
ASSET_SESSION_RULES = {
    "BTC-USD": None, "ETH-USD": None, "SOL-USD": None,
    "EURUSD=X": None, "AUDJPY=X": None, "USDJPY=X": None, "GBPUSD=X": None,
    "GOLD": "1530-2200", "SILVER": "1530-2200",
    "^GSPC": "1530-2200", "^DJI": "1530-2200", "^IXIC": "1530-2200",
    "FTSE100": "0900-1730",
    "NASDAQ": "1530-2200", "DJ30": "1530-2200"
}

# === 📉 SL/TP i strategia wyjścia ===
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 2.5
TRAILING_ATR_MULTIPLIER = 1.0
TP_AT_RESISTANCE = True
SL_AT_SUPPORT = True
USE_TRAILING_SL = True
PARTIAL_TP_ENABLED = True
PARTIAL_TP1_RR = 1.0
MOVE_SL_TO_BREAKEVEN_AT_RR = 1.2

# === 📊 Wymogi jakościowe sygnałów ===
BB_PERIOD = 20
MIN_SCORE_BUY = 2.0
MIN_SCORE_SELL = 1.5
MIN_PROBABILITY = 60.0
MIN_RR = 1.8
MIN_ADX = 14.0
MIN_ADX_BY_INTERVAL = {
    "1m": 12.0,
    "5m": 12.0,
    "15m": 14.0,
    "1h": 16.0,
    "4h": 18.0,
    "1d": 20.0,
}
MIN_ADX_ADJUST_BY_ASSET = {
    "BTC-USD": -2.0,
    "ETH-USD": -2.0,
    "SOL-USD": -1.0,
}
MIN_ATR_PCT = 0.20
MIN_VOLUME_MA_MULT = 1.2
MAX_BB_SQUEEZE_PCT = 0.25
EMA_TREND_FILTER = True
DISABLE_LOW_LIQUIDITY = True
CONFIRM_MTF = True
CONFIRM_LOOKUP = {
    "1m": "5m", "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d",
}

# === 🔁 Multi-timeframe alignment ===
MTF_CHAIN = {
    "1m":  ["5m", "15m"],
    "5m":  ["15m", "1h"],
    "15m": ["1h", "4h"],
    "1h":  ["4h"],
    "4h":  ["1d"],
    "1d":  []
}

# === 💰 Ryzyko i money management ===
ACCOUNT_EQUITY = 10000.0
RISK_PER_TRADE = 0.005
RISK_PER_TRADE_PCT = 1.0
MAX_TRADES_PER_DAY = 6
MAX_CONCURRENT_POSITIONS = 3
MAX_DAILY_ALERTS = 12
DAILY_DRAWDOWN_STOP = 0.02
COOLDOWN_MINUTES = 20
COOLDOWN_AFTER_LOSS_MIN = 30
FEE_PCT = 0.0006
SLIPPAGE_PCT = 0.0005

# === 📲 Alerty – metoda i szczegóły ===
USE_WHATSAPP = True
USE_SMS = False
SHOW_SCORE_INFO = True
GENERATE_CRITICAL_ALERTS = True
GENERATE_WARNINGS = True
GENERATE_PDF_REPORTS = True
UPLOAD_TO_DRIVE = False
GOOGLE_DRIVE_FOLDER_ID = ""

# === 📡 Twilio dane ===
TWILIO_SID = "AC6fded4b27c89d54ea079f759eb19b0b0"
TWILIO_TOKEN = "d585e82e8103763b6e2d298e9841fe88"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
WHATSAPP_TO = "whatsapp:+48785122240"
TWILIO_SMS_FROM = "+14155238886"
SMS_TO = "+48785122240"

# === 🔐 Webhook / API ===
WEBHOOK_SECRET = "d26faj1r01qvraiq35f0"
BINANCE_API_KEY = ""
BINANCE_API_SECRET = ""

# === 🕐 NGROK linki co 3h ===
NGROK_TIMES = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]

# === 📰 Makroekonomia ===
NEWS_IMPACT_BLOCK_MIN = 30

# === 🔁 Mapowanie symboli – EODHD tylko dla interwału 1d ===
SYMBOL_MAP_EODHD = {
    "^GSPC": "US500.INDX",
    "^DJI": "DJI.INDX",
    "^IXIC": "NDX.INDX",
    "^FTSE": "UK100.INDX",
    "FTSE100": "UKX.INDX",      # <- zmiana: UK100.INDX dawało 404
    "NASDAQ": "NDX.INDX",
    "DJ30": "DJI.INDX",
    "GOLD": "XAUUSD.FOREX",
    "SILVER": "XAGUSD.FOREX",
    "EURUSD=X": "EURUSD.FOREX",
    "USDJPY=X": "USDJPY.FOREX",
    "GBPUSD=X": "GBPUSD.FOREX",
    "AUDJPY=X": "AUDJPY.FOREX"
}

# === 🔁 Mapowanie symboli – TwelveData (dla interwałów <1d) ===
SYMBOL_MAP_TWELVE = {
    # Forex
    "EURUSD=X": "EUR/USD",
    "USDJPY=X": "USD/JPY",
    "GBPUSD=X": "GBP/USD",
    "AUDJPY=X": "AUD/JPY",
    # Surowce
    "GOLD": "XAU/USD",
    "SILVER": "XAG/USD",
    # Indeksy
    "^GSPC": "SPX",
    "^DJI": "DOW",
    "^IXIC": "NDX",     # NASDAQ 100
    "^FTSE": "UK100",
    "FTSE100": "UKX",   # <- zmiana: było UK100, często pusty intraday
    "NASDAQ": "NDX",
    "DJ30": "DOW"
}

# === 🔁 Mapowanie symboli – Binance (tylko krypto) ===
SYMBOL_MAP_BINANCE = {
    "BTC-USD": "BTCUSDT",
    "ETH-USD": "ETHUSDT",
    "SOL-USD": "SOLUSDT"
    # Pozostałe aktywa nie są dostępne na Binance
}

# === 🧭 Dostawcy danych – override i fallback dla 1D ===
# Wymuszenie dostawcy dla dziennych świec (gdy EODHD kaprysi)
PROVIDER_OVERRIDE_DAILY = {
    "FTSE100": "TWELVE"   # użyj TwelveData dla 1d (UKX)
}

# Jeśli dzienne dane nie przyjdą z wybranego źródła, zbuduj 1D z intraday
DAILY_RESAMPLE_FALLBACK = True
DAILY_RESAMPLE_SOURCE_INTERVAL = "1h"   # agreguj 1h -> 1d przy braku 1d
