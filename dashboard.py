# dashboard.py – RocketAlerts v12 ULTRA EXTREME (HARDENED, SAFE, CLICKABLE)
# - Odporne parsowanie CSV (OHLCV -> float, naprawa zlepionych wartości)
# - Stabilne mini/full heatmap (brak crashy, dynamiczne kolumny, klikalność)
# - Multi-panel (Cena/Volume/RSI/MACD) + nakładki (EMA/BB/VWAP/FIBO/SL-TP)
# - MTF alignment (lokalny fallback)
# - Eksport PNG/PDF, webhook push
# - Tryb edukacyjny (tooltips), Slideshow, Historia alertów, Histogram score

from __future__ import annotations

import os
import io
import re
import glob
import json
import traceback
from datetime import datetime

import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pytz

from dash import Dash, html, dcc, Input, Output, State, dash_table, no_update, ctx
try:
    from dash import ALL  # Dash >= 2.9
except Exception:
    from dash.dependencies import ALL

# === Importy projektu (z bezpiecznymi fallbackami) ===
try:
    from config.config import ASSETS, INTERVALS, LOCAL_TZ
except Exception:
    # Fallback – zostaw minimalistyczny zestaw
    ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "EURUSD=X", "AUDJPY=X", "USDJPY=X", "GBPUSD=X", "GOLD", "SILVER", "^GSPC", "^DJI", "^IXIC", "FTSE100", "NASDAQ", "DJ30"]
    INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]
    LOCAL_TZ = pytz.timezone("Europe/Amsterdam")

# analyze_asset – w projekcie korzysta z indicators/analyzers; dajemy bezpieczny fallback
try:
    from helpers import analyze_asset
except Exception:
    def analyze_asset(_asset, _interval, _df):
        return {
            "signal": None,
            "score": 0.0,
            "probability": 0.0,
            "tp": None,
            "sl": None,
            "trailing": None,
            "score_breakdown": "Brak danych (fallback)."
        }

# Wykresy zewnętrzne – fallbacki
try:
    from plot_utils import save_plot_as_png, generate_total_plot
except Exception:
    def save_plot_as_png(df, result, asset, interval, layers):
        os.makedirs("exports", exist_ok=True)
        out = os.path.join("exports", f"{asset}_{interval}.png")
        # prościutki zapis jako PNG (offline) – w razie braku plotly-orca użyjemy statycznego zapisu HTML->PNG pomijając (fallback)
        try:
            fig = go.Figure()
            if not df.empty and all(c in df.columns for c in ["Date", "Close"]):
                fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close"))
            fig.update_layout(template="plotly_dark", paper_bgcolor="#121212", plot_bgcolor="#121212")
            fig.write_image(out, scale=2)  # wymaga kaleido
        except Exception:
            pass
        return out

    def generate_total_plot(df, result, layers):
        fig = go.Figure()
        if not df.empty and all(col in df.columns for col in ["Date", "Close"]):
            fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close"))
        fig.update_layout(template="plotly_dark", paper_bgcolor="#121212", plot_bgcolor="#121212")
        return fig

# Opcjonalne moduły – importy miękkie
try:
    from multi_timeframe_analysis import get_multi_tf_alignment
except Exception:
    get_multi_tf_alignment = None

try:
    from pdf_exporter import export_full_report_pdf
except Exception:
    export_full_report_pdf = None

try:
    from webhook_push import push_to_webhook
except Exception:
    def push_to_webhook(_payload):
        return {"ok": False, "message": "Brak modułu webhook_push.py – fallback."}

# === Stałe UI ===
DARK_BG = "#121212"
DARK_PANEL = "#1E1E1E"
FG = "#F0F0F0"
MUTED = "#AAA"
ACCENT = "#E91E63"
BTN_BG = "#2a2a2a"
BTN_BORDER = "#444"

# === Aplikacja Dash ===
app = Dash(__name__, title="🚀 RocketAlerts ULTRA MAX DASHBOARD", suppress_callback_exceptions=True)
server = app.server

# === NUMERIC SAFETY HELPERS (naprawa zlepionych wartości, przecinki itp.) ===
_FLOAT_RE = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

def _extract_first_float(x) -> str | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).replace("\u00A0", "").replace(" ", "")
    m = _FLOAT_RE.search(s)
    return m.group(0) if m else None

def _coerce_float_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    s = s.astype(str).str.replace("\u00A0", "", regex=False).str.replace(" ", "", regex=False)
    # heurystyka PL/EU
    if (s.str.contains(r",\d{1,6}$", regex=True)).mean() > 0.3:
        s = s.str.replace(".", "", regex=False)
        s = s.str.replace(",", ".", regex=False)
    s = s.map(_extract_first_float)
    return pd.to_numeric(s, errors="coerce")

def _ensure_numeric(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = _coerce_float_series(df[c])
    return df

# === IO danych ===
def read_df(asset: str, interval: str) -> pd.DataFrame:
    path = f"data/{asset}_{interval}.csv"
    if not os.path.exists(path):
        return pd.DataFrame()

    # spróbuj normalnie
    try:
        df = pd.read_csv(path)
    except Exception:
        # autodetekcja delimitera + tolerancja
        try:
            df = pd.read_csv(path, sep=None, engine="python", on_bad_lines="skip", dtype=str)
        except Exception:
            return pd.DataFrame()

    # nazwane kolumny na właściwe typy
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)

    for c in ("Open","High","Low","Close","Volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # drop kompletnie pustych lub bez daty/ceny
    core = [c for c in ("Date","Close") if c in df.columns]
    if not core or df[core].dropna().empty:
        return pd.DataFrame()

    return df.dropna(subset=["Date"]).reset_index(drop=True)

def safe_result(asset: str, interval: str, df: pd.DataFrame) -> dict:
    try:
        res = analyze_asset(asset, interval, df if df is not None else pd.DataFrame())
        return res if isinstance(res, dict) else {}
    except Exception:
        traceback.print_exc()
        return {}

# === Pomocnicze ===
def resolve_heatmap_intervals(mode: str, chart_interval: str):
    mode = (mode or "std")
    chart_interval = chart_interval or "1h"
    # odfiltrowanie dubli i nieznanych TF
    inters = set(INTERVALS) if INTERVALS else {"1m","5m","15m","1h","4h","1d"}

    if mode == "same":
        cand = [chart_interval]
    elif mode == "quick":
        cand = ["1m", "1h", "4h", "1d"]
    elif mode == "all":
        base = [i for i in INTERVALS][:8] if INTERVALS else ["1m","5m","15m","1h","4h","1d"]
        cand = base
    else:  # std
        cand = ["1h", "4h", "1d"]
    # tylko te które istnieją w projekcie (jeśli lista INTERVALS jest restrykcyjna)
    out = [i for i in cand if (i in inters) or (INTERVALS is None)]
    return out or ["1h"]

def compute_alignment_local(asset: str) -> dict:
    needed = ["1h", "4h", "1d"]
    signals = []
    for it in needed:
        df = read_df(asset, it)
        res = safe_result(asset, it, df)
        sig = (res.get("signal") or "BRAK")
        sig = "KUP" if str(sig).upper() == "KUP" else ("SPRZEDAJ" if str(sig).upper() == "SPRZEDAJ" else "BRAK")
        signals.append((it, sig))
    buys = sum(1 for _, s in signals if s == "KUP")
    sells = sum(1 for _, s in signals if s == "SPRZEDAJ")
    status = "BRAK"; color = "gray"
    if buys >= 2 and sells == 0: status, color = "KUP", "lightgreen"
    elif sells >= 2 and buys == 0: status, color = "SPRZEDAJ", "tomato"
    return {"status": status, "color": color, "signals": signals}

def gen_heatmap_data(intervals=None):
    if intervals is None:
        intervals = ["1h", "4h", "1d"]
    rows = []
    for a in ASSETS:
        row = {"asset": a}
        for it in intervals:
            try:
                df = read_df(a, it)
                if df.empty:
                    row[it] = "BRAK"
                    continue
                res = safe_result(a, it, df)
                sig = (res.get("signal") or "BRAK").upper()
                row[it] = sig
            except Exception:
                row[it] = "BRAK"
        rows.append(row)
    return pd.DataFrame(rows)

def sig_color(sig: str) -> str:
    s = (sig or "BRAK").upper()
    if s == "KUP": return "lightgreen"
    if s == "SPRZEDAJ": return "tomato"
    return "gray"

def fmt_last_candle(df: pd.DataFrame):
    if df is not None and not df.empty and "Date" in df.columns:
        last = df["Date"].max()
        try:
            if last.tzinfo is None: last = last.tz_localize("UTC")
            last_local = last.astimezone(LOCAL_TZ)
            tzlabel = getattr(LOCAL_TZ, "zone", str(LOCAL_TZ))
        except Exception:
            last_local = last
            tzlabel = "local"
        return f"🕒 Ostatnia świeca: {last_local.strftime('%Y-%m-%d %H:%M:%S')} ({tzlabel})"
    return "❌ Brak danych"

def build_risk_panel(res: dict) -> html.Div:
    tp = res.get("tp"); sl = res.get("sl"); trailing = res.get("trailing")
    rr = None
    try:
        if tp is not None and sl is not None and isinstance(tp, (int, float)) and isinstance(sl, (int, float)):
            rr = round(abs(tp / sl), 2) if sl not in (0, None) else None
    except Exception:
        rr = None
    rr_color = "#66BB6A" if (rr is not None and rr >= 2) else ("#FFA726" if (rr is not None and 1 <= rr < 2) else "#EF5350")
    items = [
        html.Div(f"🎯 TP: {tp}" if tp is not None else "🎯 TP: –"),
        html.Div(f"🛡️ SL: {sl}" if sl is not None else "🛡️ SL: –"),
        html.Div(f"📏 RR: {rr}" if rr is not None else "📏 RR: –", style={"color": rr_color, "fontWeight": "bold"}),
        html.Div(f"🔄 Trailing: {trailing}" if trailing is not None else "🔄 Trailing: –")
    ]
    return html.Div(items, style={"display": "grid", "gridTemplateColumns": "repeat(2, minmax(120px, 1fr))", "gap": "8px"})

def build_score_histogram(interval: str) -> go.Figure:
    scores = []
    for a in ASSETS or []:
        df = read_df(a, interval)
        res = safe_result(a, interval, df)
        sc = res.get("score")
        if isinstance(sc, (int, float)):
            scores.append(sc)
        else:
            try:
                scores.append(float(sc))
            except Exception:
                pass
    fig = go.Figure()
    if scores:
        fig.add_trace(go.Histogram(x=scores, nbinsx=20, name="Score"))
    fig.update_layout(title=f"Histogram score – interwał {interval}",
                      template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG)
    return fig

# === Lokalne wskaźniki do nakładek (odporne) ===
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    close = _coerce_float_series(close)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    close = _coerce_float_series(close)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - macd_signal
    return macd, macd_signal, hist

def _fibo_levels(low: float, high: float) -> dict:
    if low is None or high is None or pd.isna(low) or pd.isna(high) or low == high:
        return {}
    up = high >= low
    rng = high - low
    levels = {
        "0.0%": low if up else high,
        "23.6%": (low + 0.236 * rng) if up else (high - 0.236 * rng),
        "38.2%": (low + 0.382 * rng) if up else (high - 0.382 * rng),
        "50.0%": (low + 0.5 * rng) if up else (high - 0.5 * rng),
        "61.8%": (low + 0.618 * rng) if up else (high - 0.618 * rng),
        "78.6%": (low + 0.786 * rng) if up else (high - 0.786 * rng),
        "100%": high if up else low,
    }
    return levels

def add_overlay_layers(fig: go.Figure, df: pd.DataFrame, layers, result: dict):
    if df is None or df.empty or "Date" not in df.columns:
        return fig
    layers = set(layers or [])
    df = _ensure_numeric(df.copy())
    x = df["Date"]

    # EMA 20/50/200
    if "ema" in layers and "Close" in df.columns:
        for p in (20, 50, 200):
            try:
                ema = _coerce_float_series(df["Close"]).ewm(span=p, adjust=False).mean()
                fig.add_trace(go.Scatter(x=x, y=ema, name=f"EMA{p}", mode="lines", opacity=0.9))
            except Exception:
                pass

    # Bollinger 20/2
    if "bb" in layers and "Close" in df.columns:
        try:
            close = _coerce_float_series(df["Close"])
            sma = close.rolling(20, min_periods=20).mean()
            std = close.rolling(20, min_periods=20).std()
            upper = sma + 2 * std
            lower = sma - 2 * std
            fig.add_trace(go.Scatter(x=x, y=upper, name="BB Upper", mode="lines", opacity=0.6))
            fig.add_trace(go.Scatter(x=x, y=lower, name="BB Lower", mode="lines", opacity=0.6))
        except Exception:
            pass

    # VWAP
    if "vwap" in layers and all(c in df.columns for c in ["High", "Low", "Close", "Volume"]):
        try:
            tp = (_coerce_float_series(df["High"]) + _coerce_float_series(df["Low"]) + _coerce_float_series(df["Close"])) / 3.0
            vol = _coerce_float_series(df["Volume"])
            vwap = (tp * vol).cumsum() / vol.replace(0, np.nan).cumsum()
            fig.add_trace(go.Scatter(x=x, y=vwap, name="VWAP", mode="lines"))
        except Exception:
            pass

    # FIBO (ostatnie 300 świec)
    if "fibo" in layers and all(c in df.columns for c in ["High", "Low"]):
        try:
            tail = df.tail(300) if len(df) > 300 else df
            swing_high = float(_coerce_float_series(tail["High"]).max())
            swing_low = float(_coerce_float_series(tail["Low"]).min())
            levels = _fibo_levels(swing_low, swing_high)
            if levels:
                x0 = x.iloc[0]; x1 = x.iloc[-1]
                for label, y in levels.items():
                    fig.add_shape(type="line", x0=x0, x1=x1, y0=y, y1=y,
                                  line=dict(width=1, dash="dot"), xref="x", yref="y")
                    fig.add_annotation(x=x1, y=y, xref="x", yref="y",
                                       text=f"Fibo {label}", showarrow=False, xanchor="left", font=dict(size=10))
        except Exception:
            pass

    # SL/TP
    if "sl_tp" in layers:
        for key, label in (("sl", "SL"), ("tp", "TP")):
            val = result.get(key) if isinstance(result, dict) else None
            if isinstance(val, (int, float)) and not pd.isna(val):
                try:
                    fig.add_shape(type="line", x0=x.iloc[0], x1=x.iloc[-1], y0=val, y1=val,
                                  line=dict(width=2), xref="x", yref="y")
                    fig.add_annotation(x=x.iloc[-1], y=val, xref="x", yref="y",
                                       text=f"{label}: {val}", showarrow=False, xanchor="left")
                except Exception:
                    pass
    return fig

def build_multi_panel_figure(df: pd.DataFrame, layers, result: dict) -> go.Figure:
    """Cena + (opcjonalnie) Wolumen + RSI + MACD w osobnych panelach."""
    if df is None or df.empty or "Date" not in df.columns:
        return go.Figure()
    df = _ensure_numeric(df.copy())
    rows = 1
    row_titles = ["Cena"]
    show_volume = "volume" in (layers or [])
    show_rsi = "rsi" in (layers or [])
    show_macd = "macd" in (layers or [])

    if show_volume: row_titles.append("Wolumen")
    if show_rsi:    row_titles.append("RSI(14)")
    if show_macd:   row_titles.append("MACD(12,26,9)")
    rows = len(row_titles)

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        subplot_titles=row_titles, specs=[[{"secondary_y": False}] for _ in range(rows)])

    # — Cena (row 1)
    r = 1
    if all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
        fig.add_trace(go.Candlestick(x=df["Date"], open=df["Open"], high=df["High"],
                                     low=df["Low"], close=df["Close"], name="Świece"), row=r, col=1)
    else:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode="lines", name="Close"), row=r, col=1)

    # Nakładki na cenie:
    base = go.Figure()
    base = add_overlay_layers(base, df, layers, result)
    for tr in base.data:
        fig.add_trace(tr, row=r, col=1)

    # — Wolumen
    if show_volume and "Volume" in df.columns:
        r += 1
        fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], name="Volume"), row=r, col=1)

    # — RSI
    if show_rsi and "Close" in df.columns:
        r += 1
        rsi = compute_rsi(df["Close"])
        fig.add_trace(go.Scatter(x=df["Date"], y=rsi, name="RSI(14)", mode="lines"), row=r, col=1)
        for lvl in (30, 50, 70):
            fig.add_shape(type="line", x0=df["Date"].iloc[0], x1=df["Date"].iloc[-1],
                          y0=lvl, y1=lvl, line=dict(width=1, dash="dot"), row=r, col=1)
        fig.update_yaxes(range=[0, 100], row=r, col=1)

    # — MACD
    if show_macd and "Close" in df.columns:
        r += 1
        macd, sig, hist = compute_macd(df["Close"])
        fig.add_trace(go.Scatter(x=df["Date"], y=macd, name="MACD", mode="lines"), row=r, col=1)
        fig.add_trace(go.Scatter(x=df["Date"], y=sig, name="Signal", mode="lines"), row=r, col=1)
        fig.add_trace(go.Bar(x=df["Date"], y=hist, name="Histogram"), row=r, col=1)

    fig.update_layout(template="plotly_dark", paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    return fig

# === Layout ===
app.layout = html.Div(style={
    "backgroundColor": DARK_BG, "color": FG, "minHeight": "100vh",
    "fontFamily": "Arial, sans-serif", "padding": "16px"
}, children=[
    html.Div([
        html.H1("🚀 RocketAlerts v12 ULTRA EXTREME – TOTAL MAX DASHBOARD",
                style={"textAlign": "center", "color": ACCENT, "margin": "0 0 12px 0"}),
        html.Div([
            html.Div(id="mtf-alignment", style={
                "padding": "10px 14px", "backgroundColor": DARK_PANEL, "border": "1px solid #333",
                "borderRadius": "10px", "display": "inline-block", "minWidth": "240px", "textAlign": "center"
            }),
            html.Div([
                dcc.Checklist(id="edu-mode",
                              options=[{"label": "🧠 Tryb edukacyjny (tooltipy)", "value": "on"}],
                              value=[], style={"marginLeft": "16px"})
            ], style={"display": "inline-block", "verticalAlign": "top"}),
            html.Div([
                dcc.Checklist(id="slideshow-toggle",
                              options=[{"label": "🔄 Slideshow (co 10s)", "value": "on"}],
                              value=[], style={"marginLeft": "16px"}),
                dcc.Interval(id="slideshow-interval", interval=10_000, disabled=True, n_intervals=0)
            ], style={"display": "inline-block", "verticalAlign": "top"})
        ], style={"display": "flex", "gap": "10px", "justifyContent": "center", "alignItems": "center"})
    ]),

    html.Hr(style={"borderColor": "#333"}),

    html.Div([
        html.Div([
            html.Label("🪙 Aktyw:", style={"fontWeight": "bold"}),
            dcc.Dropdown(id='asset-dropdown',
                         options=[{"label": a, "value": a} for a in ASSETS],
                         value=(ASSETS[0] if ASSETS else None), style={"width": "100%", "color": "black"}),

            html.Label("⏱️ Interwał:", style={"fontWeight": "bold", "marginTop": "12px"}),
            dcc.Dropdown(id='interval-dropdown',
                         options=[{"label": i, "value": i} for i in INTERVALS],
                         value=("1h" if "1h" in INTERVALS else (INTERVALS[0] if INTERVALS else None)),
                         style={"width": "100%", "color": "black"}),

            html.Label("🎛️ Tryb wykresu:", style={"fontWeight": "bold", "marginTop": "12px"}),
            dcc.RadioItems(
                id="chart-mode",
                options=[{"label": "Jednopanelowy", "value": "single"},
                         {"label": "Wielopanelowy (Vol/RSI/MACD)", "value": "multi"}],
                value="single",
                labelStyle={"display": "block", "marginBottom": "3px"}
            ),

            html.Label("🧩 Warstwy:", style={"fontWeight": "bold", "marginTop": "12px"}, id="layers-label"),
            dcc.Checklist(
                id="layers-checklist",
                options=[
                    {"label": "EMA", "value": "ema"},
                    {"label": "BB", "value": "bb"},
                    {"label": "RSI", "value": "rsi"},
                    {"label": "MACD", "value": "macd"},
                    {"label": "Volume", "value": "volume"},
                    {"label": "SL/TP", "value": "sl_tp"},
                    {"label": "Sygnały", "value": "signals"},
                    {"label": "Fibo", "value": "fibo"},
                    {"label": "Formacje", "value": "patterns"},
                    {"label": "Struktura", "value": "structure"},
                    {"label": "VWAP", "value": "vwap"},
                    {"label": "BOS/CHoCH", "value": "bos"}
                ],
                value=["ema", "bb", "rsi", "macd", "volume", "sl_tp", "signals"],
                style={"color": FG, "marginBottom": "10px"}
            ),

            html.Button("🔽 Pokaż/Ukryj breakdown", id="toggle-breakdown", n_clicks=0, style={"width": "100%"}),
            html.Button("📸 Zapisz PNG", id="save-png", n_clicks=0, style={"width": "100%", "marginTop": "8px"}),
            html.Button("🧾 Eksport PDF (zbiorczy)", id="export-pdf", n_clicks=0, style={"width": "100%", "marginTop": "8px"}),
            dcc.Download(id="download-pdf"),

            html.Button("📡 Push do Webhooka (aktualny sygnał)", id="push-webhook", n_clicks=0,
                        style={"width": "100%", "marginTop": "8px"}),
            html.Div(id="webhook-status", style={"fontSize": "12px", "color": MUTED, "marginTop": "6px"}),

            html.Hr(style={"borderColor": "#333", "margin": "12px 0"}),

            html.Div([
                html.Div("📊 Mini Heatmapa", id="mini-heatmap-title",
                         style={"fontWeight": "bold", "marginBottom": "6px"}),
                dcc.RadioItems(
                    id="heatmap-mode",
                    options=[
                        {"label": "Standard (1h/4h/1d)", "value": "std"},
                        {"label": "Szybki (1m/1h/4h/1d)", "value": "quick"},
                        {"label": "Jak wykres", "value": "same"},
                        {"label": "Wszystkie (max 8)", "value": "all"},
                    ],
                    value="std",
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"display": "block", "marginBottom": "3px"}
                ),
                html.Div(id="mini-heatmap", style={
                    "display": "grid",
                    "gridTemplateColumns": "120px 70px 70px 70px",
                    "gap": "6px"
                })
            ], style={"backgroundColor": DARK_PANEL, "border": "1px solid #333", "borderRadius": "10px", "padding": "10px"})
        ], style={"width": "24%", "display": "inline-block", "verticalAlign": "top", "paddingRight": "10px"}),

        html.Div([
            dcc.Graph(id='main-graph', config={"displayModeBar": True}),
            html.Div(id='score-display', style={"padding": "8px", "fontSize": "18px", "fontWeight": "bold"}),
            html.Div(id='breakdown', style={
                "padding": "12px", "backgroundColor": DARK_PANEL, "border": "1px solid #444",
                "borderRadius": "10px", "whiteSpace": "pre-wrap", "fontSize": "14px", "display": "none"
            }),

            dcc.Tabs(id="tabs", value="tab-heatmap", children=[
                dcc.Tab(label="🔥 Pełna Heatmapa", value="tab-heatmap", children=[
                    html.Div(id="full-heatmap", style={"marginTop": "10px"})
                ]),
                dcc.Tab(label="🕰️ Historia sygnałów", value="tab-history", children=[
                    html.Div(id="history-table-wrap", style={"marginTop": "10px"})
                ]),
                dcc.Tab(label="🛡️ Panel ryzyka", value="tab-risk", children=[
                    html.Div(id="risk-panel", style={
                        "backgroundColor": DARK_PANEL, "border": "1px solid #333", "borderRadius": "10px",
                        "padding": "12px", "marginTop": "10px"
                    })
                ]),
                dcc.Tab(label="📈 Histogram score", value="tab-hist", children=[
                    dcc.Graph(id="score-hist", style={"marginTop": "10px"})
                ])
            ])
        ], style={"width": "75%", "display": "inline-block", "verticalAlign": "top"})
    ]),

    html.Div(id="last-update", style={"textAlign": "center", "marginTop": "10px", "color": MUTED, "fontSize": "13px"}),

    dcc.Store(id="current-result"),
    dcc.Store(id="slideshow-index", data=0),

    dcc.Interval(id="auto-refresh", interval=60 * 1000, n_intervals=0)
])

# === CALLBACKI ===

@app.callback(Output("layers-label", "title"), Input("edu-mode", "value"))
def edu_tooltips(edu_value):
    if "on" in (edu_value or []):
        return "EMA: średnie; BB: zmienność; RSI/MACD: momentum; BOS/CHoCH: struktura rynku; VWAP: średnia ważona wolumenem."
    return ""

@app.callback(Output("slideshow-interval", "disabled"), Input("slideshow-toggle", "value"))
def toggle_slideshow(val):
    return not ("on" in (val or []))

@app.callback(
    Output("asset-dropdown", "value"),
    Output("slideshow-index", "data"),
    Input("slideshow-interval", "n_intervals"),
    State("slideshow-toggle", "value"),
    State("slideshow-index", "data"),
    prevent_initial_call=True
)
def slideshow_step(_ticks, toggle_val, idx):
    if "on" not in (toggle_val or []):
        return no_update, idx
    if not ASSETS:
        return no_update, idx
    idx = (idx or 0) + 1
    asset = ASSETS[idx % len(ASSETS)]
    return asset, idx

@app.callback(
    Output("main-graph", "figure"),
    Output("score-display", "children"),
    Output("breakdown", "children"),
    Output("last-update", "children"),
    Output("current-result", "data"),
    Output("mtf-alignment", "children"),
    Input("asset-dropdown", "value"),
    Input("interval-dropdown", "value"),
    Input("layers-checklist", "value"),
    Input("chart-mode", "value"),
    Input("auto-refresh", "n_intervals")
)
def update_graph(asset, interval, layers, chart_mode, _tick):
    try:
        if not asset or not interval:
            return go.Figure(), "❌ Brak wyboru", "Brak danych.", "", {}, html.Div("Zgodność MTF: –", style={"color": MUTED})

        df = read_df(asset, interval)
        result = safe_result(asset, interval, df)

        score = float(result.get("score", 0) or 0)
        probability = float(result.get("probability", 0) or 0)
        sig = (result.get("signal") or "BRAK")
        signal_up = "KUP" if str(sig).upper() == "KUP" else ("SPRZEDAJ" if str(sig).upper() == "SPRZEDAJ" else "BRAK")

        color, icon = ("lightgreen", "🚀") if signal_up == "KUP" else (("tomato", "⚠️") if signal_up == "SPRZEDAJ" else ("gray", "⏸️"))

        # Wykres
        if chart_mode == "multi":
            fig = build_multi_panel_figure(df, layers, result)
        else:
            fig = generate_total_plot(df, result, layers)
            fig = add_overlay_layers(fig, df, layers, result)

        info = html.Span([
            html.Span(f"{icon} Sygnał: {signal_up}", style={"color": color, "marginRight": "15px"}),
            html.Span(f"💥 Score: {score:.2f}", style={"marginRight": "15px"}),
            html.Span(f"🎯 Skuteczność: {probability:.1f}%", title="Prawdopodobieństwo sukcesu")
        ])

        breakdown = result.get("score_breakdown", "Brak danych.")
        timestamp = fmt_last_candle(df)

        # Multi-TF alignment (z tooltipem szczegółów)
        try:
            mtf = get_multi_tf_alignment(asset) if get_multi_tf_alignment else compute_alignment_local(asset)
        except Exception:
            mtf = compute_alignment_local(asset)
        status = (mtf.get("status") or "BRAK").upper()
        mcolor = mtf.get("color") or sig_color(status)
        details = ", ".join([f"{it}:{sig}" for it, sig in mtf.get("signals", [])]) or "brak danych"
        inner = html.Div([
            html.Span("Zgodność MTF: ", style={"color": MUTED}),
            html.Span(status, style={"color": mcolor, "fontWeight": "bold"})
        ], title=f"Szczegóły: {details}")

        # Do store wrzućmy lekki pakiet
        store_result = {
            "signal": result.get("signal"),
            "score": result.get("score"),
            "probability": result.get("probability"),
            "tp": result.get("tp"),
            "sl": result.get("sl")
        }

        return fig, info, breakdown, timestamp, store_result, inner

    except Exception as e:
        traceback.print_exc()
        return go.Figure(), "❌ Błąd", f"{e}", "", {}, html.Div("Zgodność MTF: –", style={"color": MUTED})

@app.callback(Output("breakdown", "style"),
              Input("toggle-breakdown", "n_clicks"),
              State("breakdown", "style"))
def toggle_breakdown(n_clicks, style):
    style = dict(style or {})
    style["display"] = "block" if (n_clicks or 0) % 2 == 1 else "none"
    return style

@app.callback(
    Output("main-graph", "figure", allow_duplicate=True),
    Input("save-png", "n_clicks"),
    State("asset-dropdown", "value"),
    State("interval-dropdown", "value"),
    State("layers-checklist", "value"),
    State("chart-mode", "value"),
    prevent_initial_call=True
)
def save_graph_as_png_callback(n_clicks, asset, interval, layers, chart_mode):
    try:
        if not asset or not interval:
            return no_update
        df = read_df(asset, interval)
        result = safe_result(asset, interval, df)
        # zapis
        try:
            save_plot_as_png(df, result, asset, interval, layers)
        except Exception:
            pass
        # odśwież wykres
        if chart_mode == "multi":
            return build_multi_panel_figure(df, layers, result)
        fig = generate_total_plot(df, result, layers)
        fig = add_overlay_layers(fig, df, layers, result)
        return fig
    except Exception:
        traceback.print_exc()
        return no_update

# === Mini heatmapa – dynamiczne interwały, KLIKALNA (odporna) ===
@app.callback(
    Output("mini-heatmap", "children"),
    Output("mini-heatmap-title", "children"),
    Output("mini-heatmap", "style"),
    Input("auto-refresh", "n_intervals"),
    Input("heatmap-mode", "value"),
    State("interval-dropdown", "value"),
    State("mini-heatmap", "style"),
)
def update_mini_heatmap(_n, mode, chart_interval, style):
    try:
        intervals = resolve_heatmap_intervals(mode, chart_interval)
        df = gen_heatmap_data(intervals)

        # Jeśli nie ma assetów/danych – pusta ramka UI, ale brak crasha
        if df is None or df.empty:
            title = "📊 Mini Heatmapa (brak danych)"
            style = dict(style or {})
            style["display"] = "grid"
            style["gridTemplateColumns"] = "120px"
            style.setdefault("gap", "6px")
            return [html.Div("Brak danych")], title, style

        grid_cols = ["120px"] + ["70px"] * len(intervals)
        header = [html.Button("Aktyw", disabled=True, style={
                    "background": BTN_BG, "color": FG, "border": f"1px solid {BTN_BORDER}",
                    "borderRadius": "6px", "fontWeight": "bold"})] + [
            html.Button(it, id={"type": "hm-header", "key": it},
                        title="Kliknij, aby ustawić interwał",
                        style={"background": BTN_BG, "color": FG, "border": f"1px solid {BTN_BORDER}",
                               "borderRadius": "6px", "cursor": "pointer", "fontWeight": "bold"})
            for it in intervals
        ]

        rows = []
        for _, r in df.iterrows():
            a = r["asset"]
            rows.append(html.Button(a, id={"type": "hm-asset", "key": a},
                                    title="Kliknij, aby ustawić aktywo",
                                    style={"background": BTN_BG, "color": FG, "border": f"1px solid {BTN_BORDER}",
                                           "borderRadius": "6px", "cursor": "pointer"}))
            for it in intervals:
                sig = r.get(it, "BRAK")
                rows.append(html.Button(sig, id={"type": "hm-cell", "key": f"{a}|{it}"},
                                        title="Kliknij, aby ustawić aktywo i interwał",
                                        style={"backgroundColor": sig_color(sig), "color": "#000",
                                               "border": "none", "borderRadius": "6px",
                                               "cursor": "pointer"}))

        style = dict(style or {})
        style["display"] = "grid"
        style["gridTemplateColumns"] = " ".join(grid_cols)
        style.setdefault("gap", "6px")

        title = "📊 Mini Heatmapa (" + "/".join(intervals) + ")"
        return header + rows, title, style
    except Exception:
        traceback.print_exc()
        # Zwróć nieinwazyjny placeholder
        title = "📊 Mini Heatmapa (błąd – zob. log)"
        style = dict(style or {})
        style["display"] = "grid"
        style["gridTemplateColumns"] = "120px"
        style.setdefault("gap", "6px")
        return [html.Div("Błąd heatmapy")], title, style

# Pełna heatmapa – dynamiczne interwały i kolumny (odporna)
@app.callback(
    Output("full-heatmap", "children"),
    Input("tabs", "value"),
    Input("auto-refresh", "n_intervals"),
    Input("heatmap-mode", "value"),
    State("interval-dropdown", "value")
)
def update_full_heatmap(tab, _n, mode, chart_interval):
    try:
        if tab != "tab-heatmap":
            return no_update
        intervals = resolve_heatmap_intervals(mode, chart_interval)
        df = gen_heatmap_data(intervals)

        if df is None or df.empty:
            return html.Div("Brak danych do heatmapy", style={"color": MUTED, "padding": "8px"})

        grid_cols = ["160px"] + ["80px"] * len(intervals)
        header = [html.Div("Aktyw", style={"fontWeight": "bold"})] + [
            html.Div(it, style={"fontWeight": "bold", "textAlign": "center"}) for it in intervals
        ]
        body = []
        for _, r in df.iterrows():
            body.append(html.Div(r["asset"]))
            for it in intervals:
                sig = r.get(it, "BRAK")
                body.append(html.Div(sig, style={
                    "backgroundColor": sig_color(sig), "textAlign": "center",
                    "borderRadius": "6px", "padding": "2px 4px"
                }))

        return html.Div([
            html.Div(header + body, style={
                "display": "grid",
                "gridTemplateColumns": " ".join(grid_cols),
                "gap": "8px",
                "alignItems": "center"
            })
        ], style={"backgroundColor": DARK_PANEL, "border": "1px solid #333", "borderRadius": "10px", "padding": "12px"})
    except Exception:
        traceback.print_exc()
        return html.Div("Błąd przy budowie heatmapy", style={"color": "tomato", "padding": "8px"})

# Historia sygnałów (robust)
@app.callback(
    Output("history-table-wrap", "children"),
    Input("tabs", "value"),
    Input("auto-refresh", "n_intervals")
)
def update_history_tab(tab, _n):
    if tab != "tab-history":
        return no_update
    path = os.path.join("logs", "alerts_log.csv")
    if not os.path.exists(path):
        return html.Div("Brak pliku logs/alerts_log.csv", style={"color": MUTED, "padding": "8px"})
    # Tolerancyjny odczyt
    try:
        df = pd.read_csv(path, sep=None, engine="python", on_bad_lines="skip", dtype=str)
    except Exception:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                sample = "".join([next(f) for _ in range(20)])
            delim = ";" if sample.count(";") > sample.count(",") else ","
            df = pd.read_csv(path, sep=delim, engine="python", on_bad_lines="skip", dtype=str)
        except Exception as e:
            traceback.print_exc()
            return html.Div(f"Błąd odczytu historii: {e}", style={"color": "tomato"})
    # Normalizacja
    lower_map = {c.lower(): c for c in df.columns}
    rename = {}
    aliases = {
        "timestamp": ["timestamp", "time", "datetime", "date"],
        "asset": ["asset", "symbol", "pair"],
        "interval": ["interval", "tf", "timeframe"],
        "signal": ["signal", "sig"],
        "score": ["score"],
        "probability": ["probability", "prob", "prob_%", "success", "success_prob"],
    }
    for target, alist in aliases.items():
        for a in alist:
            if a in lower_map:
                rename[lower_map[a]] = target
                break
    if rename:
        df = df.rename(columns=rename)
    needed = ["timestamp", "asset", "interval", "signal", "score", "probability"]
    for c in needed:
        if c not in df.columns: df[c] = None
    df["probability"] = df["probability"].astype(str).str.replace("%", "", regex=False)
    df["probability"] = pd.to_numeric(df["probability"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df[needed].tail(500).iloc[::-1]
    table = dash_table.DataTable(
        id="history-table",
        columns=[{"name": c, "id": c} for c in needed],
        data=df.to_dict("records"),
        page_size=12,
        style_header={"backgroundColor": "#222", "color": FG, "fontWeight": "bold"},
        style_cell={"backgroundColor": "#181818", "color": FG, "border": "1px solid #333"},
        row_selectable="single",
        filter_action="native",
        sort_action="native",
        selected_rows=[]
    )
    return html.Div([table, html.Div(id="history-hint", style={"color": MUTED, "marginTop": "6px"},
                                     children="Kliknij wiersz, aby przejść do aktywa/interwału.")])

@app.callback(
    Output("asset-dropdown", "value", allow_duplicate=True),
    Output("interval-dropdown", "value", allow_duplicate=True),
    Input("history-table", "selected_rows"),
    State("history-table", "data"),
    prevent_initial_call=True
)
def on_history_click(selected_rows, data):
    if not selected_rows:
        return no_update, no_update
    try:
        row = data[selected_rows[0]]
        return row.get("asset", no_update), row.get("interval", no_update)
    except Exception:
        return no_update, no_update

# === Klikalność mini-heatmapy ===
@app.callback(
    Output("asset-dropdown", "value", allow_duplicate=True),
    Output("interval-dropdown", "value", allow_duplicate=True),
    Input({"type": "hm-cell", "key": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def on_mini_cell_click(_clicks):
    tid = ctx.triggered_id
    if not tid or not isinstance(tid, dict):
        return no_update, no_update
    try:
        a, it = str(tid["key"]).split("|", 1)
        return a, it
    except Exception:
        return no_update, no_update

@app.callback(
    Output("asset-dropdown", "value", allow_duplicate=True),
    Input({"type": "hm-asset", "key": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def on_mini_asset_click(_clicks):
    tid = ctx.triggered_id
    if not tid or not isinstance(tid, dict):
        return no_update
    return tid.get("key", no_update)

@app.callback(
    Output("interval-dropdown", "value", allow_duplicate=True),
    Input({"type": "hm-header", "key": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def on_mini_header_click(_clicks):
    tid = ctx.triggered_id
    if not tid or not isinstance(tid, dict):
        return no_update
    return tid.get("key", no_update)

# Panel ryzyka – na bazie current-result
@app.callback(Output("risk-panel", "children"),
              Input("tabs", "value"),
              State("current-result", "data"))
def update_risk_panel(tab, res):
    if tab != "tab-risk":
        return no_update
    return build_risk_panel(res or {})

# Histogram score – na bazie wybranego interwału
@app.callback(Output("score-hist", "figure"),
              Input("tabs", "value"),
              State("interval-dropdown", "value"))
def update_hist(tab, interval):
    if tab != "tab-hist":
        return no_update
    return build_score_histogram(interval or "1h")

# Eksport PDF (zbiorczy)
@app.callback(
    Output("download-pdf", "data"),
    Input("export-pdf", "n_clicks"),
    State("asset-dropdown", "value"),
    State("interval-dropdown", "value"),
    prevent_initial_call=True
)
def export_pdf(n_clicks, asset, interval):
    try:
        os.makedirs("reports", exist_ok=True)
        out_path = os.path.join("reports", f"RocketAlerts_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if export_full_report_pdf is not None:
            export_full_report_pdf(out_path, assets=ASSETS, intervals=INTERVALS)
        else:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.utils import ImageReader
            c = canvas.Canvas(out_path, pagesize=A4)
            w, h = A4
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, h - 50, "RocketAlerts – Zbiorczy Raport")
            c.setFont("Helvetica", 10)
            c.drawString(50, h - 70, f"Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            c.showPage()
            for a in ASSETS or []:
                # ogranicz liczbę interwałów w PDF jeśli jest bardzo dużo
                its = (INTERVALS if len(INTERVALS) <= 6 else ["1h", "4h", "1d"]) if INTERVALS else ["1h","4h","1d"]
                for it in its:
                    df = read_df(a, it); res = safe_result(a, it, df)
                    png_path = save_plot_as_png(df, res, a, it, ["ema", "bb", "rsi", "macd", "volume", "signals"])
                    c.setFont("Helvetica-Bold", 12); c.drawString(30, h - 40, f"{a} – {it}")
                    try:
                        img = ImageReader(png_path)
                        img_w, img_h = img.getSize()
                        scale = min((w - 60) / img_w, (h - 120) / img_h)
                        c.drawImage(img, 30, (h - 80 - img_h * scale), width=img_w * scale, height=img_h * scale, preserveAspectRatio=True)
                    except Exception:
                        c.setFont("Helvetica", 10); c.drawString(30, h - 80, f"(Brak obrazu {png_path})")
                    c.showPage()
            c.save()
        return dcc.send_file(out_path)
    except Exception as e:
        traceback.print_exc()
        return no_update

# Push do webhooka
@app.callback(
    Output("webhook-status", "children"),
    Input("push-webhook", "n_clicks"),
    State("asset-dropdown", "value"),
    State("interval-dropdown", "value"),
    State("current-result", "data"),
    prevent_initial_call=True
)
def do_push_webhook(n_clicks, asset, interval, res):
    try:
        payload = {
            "asset": asset, "interval": interval,
            "signal": (res or {}).get("signal"),
            "score": (res or {}).get("score"),
            "probability": (res or {}).get("probability"),
            "tp": (res or {}).get("tp"), "sl": (res or {}).get("sl"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        resp = push_to_webhook(payload)
        ok = (isinstance(resp, dict) and resp.get("ok")) or (hasattr(resp, "ok") and getattr(resp, "ok"))
        msg = (resp.get("message") if isinstance(resp, dict) else str(resp)) if resp is not None else ""
        return f"Webhook: {'OK' if ok else 'NIE'} {('- ' + msg) if msg else ''}"
    except Exception as e:
        traceback.print_exc()
        return f"Webhook: błąd – {e}"

if __name__ == "__main__":
    # Port zgodny z Twoim logiem
    app.run(debug=False, port=8051, use_reloader=False)
