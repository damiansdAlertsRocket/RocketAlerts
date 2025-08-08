# heatmap_view.py

import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import os
from config.config import ASSETS, INTERVALS, LOCAL_TZ
from helpers import analyze_asset

def generate_heatmap_data():
    data = []
    for asset in ASSETS:
        row = []
        for interval in INTERVALS:
            filepath = f"data/{asset}_{interval}.csv"
            if not os.path.exists(filepath):
                row.append("NONE")
                continue
            df = pd.read_csv(filepath)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            result = analyze_asset(asset, interval, df)
            signal = result.get("signal", "NONE")
            row.append(signal.upper())
        data.append(row)
    return pd.DataFrame(data, columns=INTERVALS, index=ASSETS)

def get_color(signal):
    if signal == "KUP":
        return "#4CAF50"  # Zielony
    elif signal == "SPRZEDAJ":
        return "#F44336"  # Czerwony
    else:
        return "#9E9E9E"  # Szary

def render_heatmap_component():
    df = generate_heatmap_data()
    table = []

    for asset in df.index:
        row = []
        for interval in df.columns:
            signal = df.loc[asset, interval]
            color = get_color(signal)
            tooltip = f"{asset} ({interval}): {signal}"
            row.append(html.Td(
                html.Div(tooltip, title=tooltip, style={
                    "backgroundColor": color,
                    "color": "white",
                    "padding": "6px",
                    "textAlign": "center",
                    "borderRadius": "4px",
                    "fontWeight": "bold"
                })
            ))
        table.append(html.Tr([html.Td(html.B(asset))] + row))

    header = html.Tr([html.Th("Aktyw")] + [html.Th(i) for i in df.columns])
    return html.Div([
        html.H3("📊 Heatmapa Sygnalna", style={"textAlign": "center", "color": "#E91E63"}),
        html.Table([header] + table, style={
            "width": "100%",
            "borderCollapse": "collapse",
            "fontSize": "13px",
            "marginTop": "10px"
        }),
        html.Div("✅ Zielony: KUP | ❌ Czerwony: SPRZEDAJ | ⏸️ Szary: Brak", style={
            "textAlign": "center",
            "color": "#AAA",
            "marginTop": "10px"
        })
    ])
