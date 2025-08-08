# alerts.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (POPRAWIONY)

import os
import pandas as pd
from datetime import datetime
import pytz
import logging

# === Logger ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/scheduler.log",
    filemode="a",
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)

from colorama import Fore, init
init(autoreset=True)
import logging, sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from helpers import analyze_asset
from send_alert import send_whatsapp_alert
from config.config import (
    ASSETS, INTERVALS, DATA_FOLDER, ALERTS_LOG_PATH,
    SHOW_SCORE_INFO, LOCAL_TZ, MIN_RR, MIN_PROBABILITY,
    ACCOUNT_EQUITY, RISK_PER_TRADE_PCT, MAX_CONCURRENT_POSITIONS,
    MAX_DAILY_ALERTS, COOLDOWN_MINUTES, COOLDOWN_LOG_PATH
)
from trade_filters import cooldown_ok
from risk import position_size

try:
    from plot_utils import save_plot_as_png
    PLOT_AVAILABLE = True
except Exception:
    PLOT_AVAILABLE = False

TZ = LOCAL_TZ if isinstance(LOCAL_TZ, pytz.BaseTzInfo) else pytz.timezone("Europe/Amsterdam")
SCORE_LOG_PATH = "logs/score_log.csv"

def _log_cooldown(symbol: str, interval: str, result: dict):
    try:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        outcome = "WIN" if result.get("success") else "LOSS" if result.get("signal") else "UNKNOWN"
        row = {"timestamp": now, "asset": symbol, "interval": interval, "result": outcome}
        df = pd.DataFrame([row])
        if os.path.exists(COOLDOWN_LOG_PATH):
            df.to_csv(COOLDOWN_LOG_PATH, mode="a", header=False, index=False)
        else:
            df.to_csv(COOLDOWN_LOG_PATH, mode="w", header=True, index=False)
    except Exception as e:
        logging.error(f"❌ Błąd zapisu cooldown_log: {e}")

def _extract_adx(result: dict) -> float:
    try:
        tech = result.get("details", {}).get("tech", {})
        adx = tech.get("indicators", {}).get("ADX", tech.get("adx", 0.0))
        return float(adx or 0.0)
    except Exception:
        return 0.0

def _atr_pct_from_df_tail(df_tail: pd.DataFrame, period: int = 14) -> float:
    try:
        h = df_tail["High"].astype(float)
        l = df_tail["Low"].astype(float)
        c1 = df_tail["Close"].astype(float).shift(1)
        tr = pd.concat([(h - l).abs(), (h - c1).abs(), (l - c1).abs()], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr / float(df_tail["Close"].iloc[-1]) * 100.0)
    except Exception:
        return 0.0

def load_asset_data(symbol: str, interval: str) -> pd.DataFrame | None:
    try:
        path = os.path.join(DATA_FOLDER, f"{symbol}_{interval}.csv")
        logging.info(f"📥 Ładowanie danych: {path}")
        df = pd.read_csv(path)
        if "Date" not in df.columns:
            logging.error(f"❌ Brak kolumny 'Date' w pliku: {path}")
            return None
        df["Date"] = pd.to_datetime(df["Date"], utc=True)
        df = df.drop_duplicates("Date").set_index("Date").sort_index()
        logging.info(f"✅ Wczytano dane: {symbol} ({interval}) – {len(df)} rekordów.")
        return df
    except Exception as e:
        logging.error(f"❌ Błąd ładowania danych: {symbol} ({interval}) — {e}")
        return None

def _pl_signal(sig: str) -> str:
    return "KUP" if sig == "BUY" else "SPRZEDAJ" if sig == "SELL" else "BRAK"

def _format_alert_message(symbol, interval, result, df_last, qty):
    last_ts = df_last["Date"].iloc[0].strftime("%Y-%m-%d %H:%M")
    change = result.get("price_change_pct", None)
    sl = result.get("sl")
    tp = result.get("tp")
    signal = result.get("signal")
    pol = _pl_signal(signal)
    score = float(result.get("score", 0.0) or 0.0)
    prob = float(result.get("probability", 0.0) or 0.0)
    rr = float(result.get("details", {}).get("rr", 0.0) or 0.0)
    adx = _extract_adx(result)
    atrp = _atr_pct_from_df_tail(df_last)

    emoji = "📈" if signal == "BUY" else "📉" if signal == "SELL" else "⚠️"
    msg = f"{emoji} *ALERT – {symbol} ({interval})*\n\n"
    msg += f"🕒 {last_ts}\n"
    msg += f"💡 Sygnał: *{pol}*\n"
    if change is not None:
        msg += f"📊 Zmiana (ostatnia świeca): {change:.2f}%\n"
    msg += f"⚖️ RR: {rr:.2f} | 📏 ADX: {adx:.1f} | ATR%: {atrp:.2f}\n"
    msg += f"🛡 SL: {sl} | 🎯 TP: {tp}\n"
    msg += f"🧠 Score: {score:.2f} | 📈 Szansa: {prob:.1f}%\n"
    msg += f"📦 Wielkość pozycji (risk {RISK_PER_TRADE_PCT:.1f}%): ~{qty:.4f} szt.\n"
    if SHOW_SCORE_INFO:
        msg += "\n📘 *Zarządzanie*: TP1 przy RR=1.0 (50%), SL→BE od RR≥1.2, trailing wg ATR.\n"
    return msg

def _log_alert(symbol, interval, result, confirmed):
    try:
        os.makedirs(os.path.dirname(ALERTS_LOG_PATH), exist_ok=True)
        now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        log_data = {
            "timestamp": now,
            "symbol": symbol,
            "interval": interval,
            "signal": result.get("signal"),
            "strength": result.get("signal_strength"),
            "score": result.get("score"),
            "change_pct": result.get("price_change_pct"),
            "tp": result.get("tp"),
            "sl": result.get("sl"),
            "probability": result.get("probability"),
            "rr": result.get("details", {}).get("rr"),
            "confirmed": confirmed,
        }
        df_log = pd.DataFrame([log_data])
        if os.path.exists(ALERTS_LOG_PATH):
            df_log.to_csv(ALERTS_LOG_PATH, mode="a", header=False, index=False)
        else:
            df_log.to_csv(ALERTS_LOG_PATH, mode="w", header=True, index=False)
    except Exception as e:
        logging.error(f"❌ Błąd zapisu logu alertu: {symbol} ({interval}) — {e}")

def _log_score(symbol: str, interval: str, score: float, prob: float, rr: float, signal: str):
    try:
        now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "timestamp": now,
            "symbol": symbol,
            "interval": interval,
            "score": score,
            "probability": prob,
            "rr": rr,
            "signal": signal
        }
        df = pd.DataFrame([row])
        if os.path.exists(SCORE_LOG_PATH):
            df.to_csv(SCORE_LOG_PATH, mode="a", header=False, index=False)
        else:
            df.to_csv(SCORE_LOG_PATH, mode="w", header=True, index=False)
    except Exception as e:
        logging.error(f"❌ Błąd logowania score: {e}")

def _send_trade_alert(symbol, interval, result, qty):
    try:
        df_last = result["latest"].copy()
        msg = _format_alert_message(symbol, interval, result, df_last, qty)
        if PLOT_AVAILABLE:
            try:
                save_plot_as_png(result["latest"], result, symbol, interval)
            except Exception as e:
                logging.warning(f"ℹ️ Wykres pominięty: {e}")
        send_whatsapp_alert(msg)
        _log_alert(symbol, interval, result, confirmed=True)
        _log_cooldown(symbol, interval, result)
        logging.info(f"✅ Wysłano alert WhatsApp: {symbol} ({interval})")
    except Exception as e:
        logging.error(f"❌ Błąd wysyłania alertu: {symbol} ({interval}) — {e}")

def _send_warning(symbol, interval, result):
    try:
        df_last = result["latest"].copy()
        last_ts = df_last["Date"].iloc[0].strftime("%Y-%m-%d %H:%M")
        change = result.get("price_change_pct", None)
        msg = f"⚠️ *OSTRZEŻENIE: {symbol} ({interval})*\n\n"
        msg += f"📉 Spadek o {change:.2f}% – {last_ts}\n" if change else f"📉 Spadek – {last_ts}\n"
        msg += "Brak jednoznacznego sygnału technicznego.\n"
        send_whatsapp_alert(msg)
        _log_alert(symbol, interval, result, confirmed=False)
        _log_cooldown(symbol, interval, result)
        logging.info(f"⚠️ Wysłano ostrzeżenie WhatsApp: {symbol} ({interval})")
    except Exception as e:
        logging.error(f"❌ Błąd ostrzeżenia: {symbol} ({interval}) — {e}")

_DAILY_ALERTS = 0
_TODAY = datetime.now(TZ).date()

def _reset_daily_counter_if_needed():
    global _DAILY_ALERTS, _TODAY
    nowd = datetime.now(TZ).date()
    if nowd != _TODAY:
        _TODAY = nowd
        _DAILY_ALERTS = 0

def run_all():
    global _DAILY_ALERTS
    _reset_daily_counter_if_needed()
    concurrent = 0

    print(f"\n📡 START ANALIZY – {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    for asset in ASSETS:
        for interval in INTERVALS:
            if _DAILY_ALERTS >= MAX_DAILY_ALERTS:
                print("⛔ Limit alertów dziennych osiągnięty.")
                return
            if concurrent >= MAX_CONCURRENT_POSITIONS:
                print("⛔ Limit pozycji osiągnięty.")
                return
            df = load_asset_data(asset, interval)
            if df is None or len(df) < 60:
                print(f"⏭ {asset} ({interval}) – brak danych.")
                continue
            if not cooldown_ok(asset, interval, COOLDOWN_MINUTES):
                print(f"⏳ Cooldown: {asset} ({interval})")
                continue

            try:
                dfr = df.reset_index()
                res = analyze_asset(asset, interval, dfr)
                change = ((dfr["Close"].iloc[-1] - dfr["Close"].iloc[-2]) / dfr["Close"].iloc[-2]) * 100.0 if len(dfr) >= 2 else None
                res["latest"] = dfr.iloc[-1:].copy()
                res["price_change_pct"] = change

                if res.get("details", {}).get("skipped_reason"):
                    reason = res["details"]["skipped_reason"]
                    print(f"⛔ {asset} ({interval}) – pominięto ({reason})")
                    logging.info(f"⛔ Pominięto {asset} ({interval}) – {reason}")
                    continue

                rr_val = float(res.get("details", {}).get("rr", 0.0) or 0.0)
                prob = float(res.get("probability") or 0.0)
                score = float(res.get("score", 0.0) or 0.0)
                signal = res.get("signal")
                strength = (res.get("signal_strength") or "").upper()

                _log_score(asset, interval, score, prob, rr_val, signal or "BRAK")

                if rr_val < MIN_RR or prob < MIN_PROBABILITY:
                    print(f"⛔ {asset} ({interval}) – RR {rr_val:.2f} / Prob {prob:.1f}% (za nisko)")
                    continue

                if signal in ["BUY", "SELL"] and strength in ["WYSOKA", "ŚREDNIA", "HIGH", "MEDIUM"]:
                    entry = float(dfr["Close"].iloc[-1])
                    sl = float(res.get("sl") or entry * 0.99)
                    qty = position_size(ACCOUNT_EQUITY, RISK_PER_TRADE_PCT, entry, sl)
                    if qty <= 0:
                        print(f"⛔ {asset} ({interval}) – qty<=0 (sprawdź SL/entry)")
                        continue
                    _send_trade_alert(asset, interval, res, qty)
                    _DAILY_ALERTS += 1
                    concurrent += 1
                elif change is not None and change < -2.0:
                    _send_warning(asset, interval, res)
                else:
                    base = f"📊 {asset} ({interval}) – Score: {score:.2f} | Prob: {prob:.1f}% | RR: {rr_val:.2f} | Sygnał: {signal or 'BRAK'}"
                    if signal == "BUY":
                        print(Fore.GREEN + base)
                        logging.info("[BUY] " + base)
                    elif signal == "SELL":
                        print(Fore.RED + base)
                        logging.info("[SELL] " + base)
                    else:
                        print(Fore.LIGHTBLACK_EX + base)
                        logging.info("[NEUTRAL] " + base)
            except Exception as e:
                print(f"❌ Błąd analizy dla {asset} ({interval}): {e}")
                logging.error(f"❌ Błąd analizy dla {asset} ({interval}): {e}")
