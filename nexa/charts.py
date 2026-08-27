from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


BG = "#07111D"
PANEL = "#0D1D2B"
GRID = "#294553"
TEXT = "#F4F7FA"
MUTED = "#9BAFBB"
GREEN = "#57E389"
CYAN = "#5BD7F4"
GOLD = "#F3C76B"
RED = "#FF747D"


def save_price_chart(ohlcv: pd.DataFrame, title: str, output_dir: Path) -> Path:
    if "close" not in ohlcv.columns or ohlcv["close"].dropna().empty:
        raise ValueError("Grafik için close verisi gerekli")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "nexa_price_chart.png"

    close = pd.to_numeric(ohlcv["close"], errors="coerce").dropna()
    trend_color = GREEN if len(close) < 2 or float(close.iloc[-1]) >= float(close.iloc[0]) else RED
    figure, axis = plt.subplots(figsize=(10, 6.4), dpi=150)
    figure.patch.set_facecolor(BG)
    axis.set_facecolor(PANEL)
    axis.plot(close.index, close, color=trend_color, linewidth=2.5, label="Kapanış", zorder=3)
    if len(close) >= 20:
        axis.plot(close.index, close.rolling(20).mean(), color=CYAN, linewidth=1.6, label="MA20", zorder=2)
    if len(close) >= 50:
        axis.plot(close.index, close.rolling(50).mean(), color=GOLD, linewidth=1.6, label="MA50", zorder=2)

    axis.set_title(f"NEXA  ·  {title}", loc="left", pad=18, color=TEXT, fontsize=16, fontweight="bold")
    axis.set_xlabel("Tarih", color=MUTED, labelpad=10)
    axis.set_ylabel("Fiyat", color=MUTED, labelpad=10)
    axis.grid(alpha=0.35, color=GRID, linewidth=0.8)
    axis.tick_params(axis="both", colors=MUTED, labelsize=9)
    for spine in axis.spines.values():
        spine.set_color(GRID)
    axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(axis.xaxis.get_major_locator()))
    legend = axis.legend(loc="upper left", frameon=True, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)
    for text in legend.get_texts():
        text.set_color(TEXT)
    figure.text(0.01, 0.02, "NEXA | Ücretsiz veri katmanı · Yatırım tavsiyesi değildir.", color=MUTED, fontsize=8)
    figure.autofmt_xdate(rotation=0)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(path, format="png", facecolor=figure.get_facecolor(), bbox_inches="tight")
    plt.close(figure)
    return path
