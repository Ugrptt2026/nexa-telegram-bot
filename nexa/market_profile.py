"""OHLCV tabanlı, emir defteri olmayan BIST hacim dağılımı analizi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class VolumeBar:
    label: str
    volume: float
    close: float
    direction: str


@dataclass(frozen=True, slots=True)
class VolumeZone:
    low: float
    high: float
    volume: float
    share_pct: float


@dataclass(frozen=True, slots=True)
class VolumeProfile:
    period_bars: int
    total_volume: float
    up_volume: float
    down_volume: float
    flat_volume: float
    average_volume: float
    latest_volume: float
    latest_vs_average_pct: float | None
    zones: tuple[VolumeZone, ...]
    recent_bars: tuple[VolumeBar, ...]
    note: str = "OHLCV ANALİZ VERİSİ"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def calculate_volume_profile(ohlcv: pd.DataFrame, bars: int = 30, zones: int = 5) -> VolumeProfile:
    """Son OHLCV barlarından yön ve yaklaşık fiyat bölgesi hacim dağılımı hesaplar.

    Fiyat bölgeleri, her mumun tipik fiyatına (high + low + close) / 3
    göre o mumun toplam hacmini gruplayan bir proxy'dir; market-by-price
    veya gerçek alış/satış emri verisi olarak yorumlanmamalıdır.
    """
    if bars < 5:
        raise ValueError("Hacim analizi için en az 5 bar gerekir")
    if zones < 2:
        raise ValueError("En az 2 hacim bölgesi gerekir")
    if not isinstance(ohlcv, pd.DataFrame) or ohlcv.empty:
        raise ValueError("OHLCV hacim verisi boş")

    required = {column: _numeric(ohlcv, column) for column in ("open", "high", "low", "close", "volume")}
    frame = pd.DataFrame(required, index=ohlcv.index).dropna()
    frame = frame[frame["volume"] >= 0].tail(bars)
    if len(frame) < 5:
        raise ValueError("OHLCV hacim verisi yeterli değil")

    up = frame.loc[frame["close"] > frame["open"], "volume"]
    down = frame.loc[frame["close"] < frame["open"], "volume"]
    flat = frame.loc[frame["close"] == frame["open"], "volume"]
    total = float(frame["volume"].sum())
    average = float(frame["volume"].mean())
    latest = float(frame["volume"].iloc[-1])
    latest_vs_average = ((latest / average) - 1) * 100 if average else None

    minimum = float(frame["low"].min())
    maximum = float(frame["high"].max())
    if minimum == maximum:
        edges = [minimum + step for step in range(zones + 1)]
    else:
        edges = [minimum + (maximum - minimum) * step / zones for step in range(zones + 1)]
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    bucket = pd.cut(typical, bins=edges, labels=False, include_lowest=True)
    profile_zones: list[VolumeZone] = []
    for index in range(zones):
        zone_volume = float(frame.loc[bucket == index, "volume"].sum())
        share = zone_volume / total * 100 if total else 0.0
        profile_zones.append(VolumeZone(edges[index], edges[index + 1], zone_volume, share))

    recent: list[VolumeBar] = []
    for timestamp, row in frame.iterrows():
        direction = "up" if row["close"] > row["open"] else "down" if row["close"] < row["open"] else "flat"
        if hasattr(timestamp, "strftime"):
            label = timestamp.strftime("%d.%m")
        else:
            label = str(timestamp)[:10]
        recent.append(VolumeBar(label, float(row["volume"]), float(row["close"]), direction))

    return VolumeProfile(
        period_bars=len(frame),
        total_volume=total,
        up_volume=float(up.sum()),
        down_volume=float(down.sum()),
        flat_volume=float(flat.sum()),
        average_volume=average,
        latest_volume=latest,
        latest_vs_average_pct=latest_vs_average,
        zones=tuple(profile_zones),
        recent_bars=tuple(recent),
    )
