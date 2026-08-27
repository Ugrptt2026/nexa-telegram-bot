"""Telegram için basit fiyat grafikleri."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def save_price_chart(ohlcv: pd.DataFrame, title: str, output_dir: Path) -> Path:
    if "close" not in ohlcv.columns or ohlcv["close"].dropna().empty:
        raise ValueError("Grafik için close verisi gerekli")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "nexa_price_chart.png"

    figure, axis = plt.subplots(figsize=(10, 5), dpi=150)
    axis.plot(ohlcv.index, ohlcv["close"], color="#1f77b4", linewidth=1.8, label="Kapanış")
    if len(ohlcv) >= 20:
        axis.plot(ohlcv["close"].rolling(20).mean(), color="#ff7f0e", linewidth=1.2, label="MA20")
    if len(ohlcv) >= 50:
        axis.plot(ohlcv["close"].rolling(50).mean(), color="#2ca02c", linewidth=1.2, label="MA50")
    axis.set_title(title)
    axis.set_xlabel("Tarih")
    axis.set_ylabel("Fiyat")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, format="png", bbox_inches="tight")
    plt.close(figure)
    return path
