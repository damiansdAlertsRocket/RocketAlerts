# plot_utils.py – RocketAlerts v12 ULTRA EXTREME TOTAL MAX (FIXED)

import os
import plotly.graph_objs as go
import numpy as np
from plotly.subplots import make_subplots

def generate_total_plot(df, result, layers):
    layers = [layer.lower() for layer in layers]
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.02,
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "xy"}], [{"type": "xy"}]]
    )

    # === ŚWIECZKI ===
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="Świece", increasing_line_color='green',
        decreasing_line_color='red', opacity=0.95
    ), row=1, col=1)

    # === EMA ===
    if "ema" in layers:
        for name, color in [("ema_20", "blue"), ("ema_50", "orange")]:
            if name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["Date"], y=df[name],
                    mode="lines", name=name.upper(), line=dict(color=color)
                ), row=1, col=1)

    # === BOLLINGER BANDS ===
    if "bb" in layers:
        for col, color in [("bb_upper", "lightgray"), ("bb_lower", "lightgray")]:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["Date"], y=df[col], name=col.upper(),
                    line=dict(dash="dot", color=color), opacity=0.6
                ), row=1, col=1)

    # === VWAP ===
    if "vwap" in layers and "vwap" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["vwap"], name="VWAP",
            line=dict(color="purple", dash="dash")
        ), row=1, col=1)

    # === SL / TP ===
    if "sl/tp" in layers:
        for key, color in [("tp", "green"), ("sl", "red")]:
            if key in result and result[key] is not None:
                fig.add_trace(go.Scatter(
                    x=df["Date"], y=[result[key]] * len(df),
                    mode="lines", name=key.upper(),
                    line=dict(color=color, dash="dot")
                ), row=1, col=1)

    # === TRENDLINES ===
    if "trendlines" in layers:
        for name in ["trendline_regression", "trendline_support", "trendline_resistance"]:
            if name in result and isinstance(result[name], dict):
                line = result[name]
                fig.add_trace(go.Scatter(
                    x=[df["Date"].iloc[0], df["Date"].iloc[-1]],
                    y=[line["start"], line["end"]],
                    mode="lines", name=name,
                    line=dict(color="cyan", dash="dash")
                ), row=1, col=1)

    # === BOS / CHoCH ===
    if "structure" in layers:
        if "bos_points" in result:
            for point in result["bos_points"]:
                fig.add_trace(go.Scatter(
                    x=[point["date"]], y=[point["price"]],
                    mode="markers+text", name="BOS",
                    marker=dict(symbol="x", size=10, color="yellow"),
                    text=["BOS"], textposition="top center"
                ), row=1, col=1)
        if "choch_points" in result:
            for point in result["choch_points"]:
                fig.add_trace(go.Scatter(
                    x=[point["date"]], y=[point["price"]],
                    mode="markers+text", name="CHoCH",
                    marker=dict(symbol="x", size=10, color="magenta"),
                    text=["CHoCH"], textposition="top center"
                ), row=1, col=1)

    # === FIBONACCI ===
    if "fibo" in layers and "fibonacci_levels" in result:
        for level, price in result["fibonacci_levels"].items():
            fig.add_trace(go.Scatter(
                x=df["Date"], y=[price] * len(df),
                mode="lines", name=f"Fibo {level}%",
                line=dict(dash="dot", color="white"), opacity=0.4
            ), row=1, col=1)

    # === FORMACJE KLASYCZNE ===
    if "formacje" in layers and "patterns" in result:
        for pattern in result["patterns"]:
            fig.add_trace(go.Scatter(
                x=[pattern["start_date"], pattern["end_date"]],
                y=[pattern["start_price"], pattern["end_price"]],
                mode="lines+text", name=pattern["type"],
                text=[pattern["type"], ""],
                textposition="bottom right",
                line=dict(color="lightgreen", dash="dash")
            ), row=1, col=1)

    # === ORDER BLOCKS ===
    if "order blocks" in layers and "order_blocks" in result:
        for block in result["order_blocks"]:
            fig.add_shape(
                type="rect",
                x0=block["start_date"], x1=block["end_date"],
                y0=block["low"], y1=block["high"],
                line=dict(color="gray", dash="dot"),
                fillcolor="gray", opacity=0.3,
                row=1, col=1
            )

    # === VOLUME ===
    if "volume" in layers and "Volume" in df.columns:
        fig.add_trace(go.Bar(
            x=df["Date"], y=df["Volume"],
            name="Volume", marker=dict(color="gray")
        ), row=2, col=1)

    # === RSI ===
    if "rsi" in layers and "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["rsi"],
            name="RSI", line=dict(color="violet")
        ), row=3, col=1)
        fig.add_shape(type="line", x0=df["Date"].iloc[0], x1=df["Date"].iloc[-1],
                      y0=70, y1=70, line=dict(dash="dot", color="red"), row=3, col=1)
        fig.add_shape(type="line", x0=df["Date"].iloc[0], x1=df["Date"].iloc[-1],
                      y0=30, y1=30, line=dict(dash="dot", color="green"), row=3, col=1)

    # === MACD ===
    if "macd" in layers and "macd" in df.columns and "macd_signal" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["macd"], name="MACD", line=dict(color="aqua")
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["macd_signal"], name="Signal", line=dict(color="orange")
        ), row=4, col=1)

    fig.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor="#111111", paper_bgcolor="#111111",
        font=dict(color="#F0F0F0"),
        xaxis_rangeslider_visible=False,
        height=900,
        showlegend=True
    )

    return fig

def save_plot_as_png(df, result, asset, interval, path="plots"):
    from plotly.io import write_image
    fig = generate_total_plot(df, result, layers=[
        "ema", "bb", "rsi", "macd", "volume", "vwap",
        "sl/tp", "trendlines", "structure", "fibo", "formacje", "order blocks"
    ])
    os.makedirs(path, exist_ok=True)
    filepath = os.path.join(path, f"{asset}_{interval}.png")
    write_image(fig, filepath, width=1400, height=900, engine="kaleido")
    return filepath
