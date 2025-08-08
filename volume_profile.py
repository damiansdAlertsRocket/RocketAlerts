# volume_profile.py – RocketAlerts v12 ULTRA EXTREME (FIXED)

import numpy as np
import pandas as pd

def calculate_volume_nodes(df, bins=20):
    """
    Dzieli zakres ceny na strefy i sumuje wolumen w każdej.
    Zwraca 5 najważniejszych poziomów wolumenowych jako listę (price_level, volume)
    """
    if df is None or df.empty or "Close" not in df.columns or "Volume" not in df.columns:
        return []

    price = df["Close"]
    volume = df["Volume"]

    if volume.isnull().all() or price.isnull().all():
        return []

    min_price = price.min()
    max_price = price.max()
    if min_price == max_price:
        return []

    bin_edges = np.linspace(min_price, max_price, bins + 1)
    volume_nodes = []

    for i in range(bins):
        mask = (price >= bin_edges[i]) & (price < bin_edges[i + 1])
        bin_volume = volume[mask].sum()
        avg_price = (bin_edges[i] + bin_edges[i + 1]) / 2
        volume_nodes.append((round(avg_price, 2), round(bin_volume, 2)))

    volume_nodes.sort(key=lambda x: x[1], reverse=True)
    return volume_nodes[:5]


def detect_order_blocks(df, lookback=100):
    """
    Wyszukuje potencjalne order blocki – obszary konsolidacji cenowej.
    """
    if df is None or df.empty or len(df) < lookback:
        return []

    df_recent = df[-lookback:]
    blocks = []
    for i in range(2, len(df_recent) - 2):
        c = df_recent["Close"].iloc[i]
        prev = df_recent["Close"].iloc[i - 2:i]
        next_ = df_recent["Close"].iloc[i + 1:i + 3]

        if prev.isnull().any() or next_.isnull().any():
            continue

        if (abs(prev.mean() - c) < c * 0.003) and (abs(next_.mean() - c) < c * 0.003):
            blocks.append(round(c, 2))

    return sorted(list(set(blocks)))[:3]


def volume_profile_score(current_price, volume_nodes, order_blocks):
    """
    Nadaje punkty, jeśli cena znajduje się blisko istotnego poziomu wolumenowego lub bloku.
    """
    score = 0
    hit = None

    if current_price is None or np.isnan(current_price):
        return {"score": 0, "hit_zone": None, "volume_nodes": volume_nodes, "order_blocks": order_blocks}

    tolerance = current_price * 0.005  # 0.5%

    for price_level, _ in volume_nodes:
        if abs(current_price - price_level) <= tolerance:
            score += 1
            hit = f"🎯 Node: {price_level}"
            break

    for block in order_blocks:
        if abs(current_price - block) <= tolerance:
            score += 1
            hit = f"🧱 Block: {block}"
            break

    return {
        "score": score,
        "hit_zone": hit,
        "volume_nodes": volume_nodes,
        "order_blocks": order_blocks
    }
