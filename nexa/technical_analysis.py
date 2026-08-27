"""Basit ve açıklanabilir teknik analiz fonksiyonları."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class TechnicalSnapshot:
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    ma20: float | None
    ma50: float | None
    support20: float | None
    resistance20: float | None


def _last(series: pd.Series) -> float | None:
    values = series.dropna()
    return float(values.iloc[-1]) if not values.empty else None


def calculate_indicators(ohlcv: pd.DataFrame) -> TechnicalSnapshot:
    """Kapanış fiyatından RSI(14), MACD(12,26,9), MA20/50 hesaplar."""
    if "close" not in ohlcv.columns:
        raise ValueError("OHLCV tablosunda close kolonu gerekli")
    close = pd.to_numeric(ohlcv["close"], errors="coerce").dropna()
    if close.empty:
        raise ValueError("Geçerli kapanış fiyatı yok")

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    valid_window = gain.notna() & loss.notna()
    rsi = rsi.mask(valid_window & gain.eq(0) & loss.eq(0), 50.0)
    rsi = rsi.mask(valid_window & gain.gt(0) & loss.eq(0), 100.0)
    rsi = rsi.mask(valid_window & gain.eq(0) & loss.gt(0), 0.0).where(valid_window)

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()

    return TechnicalSnapshot(
        rsi14=_last(rsi),
        macd=_last(macd),
        macd_signal=_last(signal),
        ma20=_last(close.rolling(20, min_periods=20).mean()),
        ma50=_last(close.rolling(50, min_periods=50).mean()),
        support20=_last(pd.to_numeric(ohlcv.get("low", close), errors="coerce").rolling(20, min_periods=1).min()),
        resistance20=_last(pd.to_numeric(ohlcv.get("high", close), errors="coerce").rolling(20, min_periods=1).max()),
    )


def snapshot_to_text(snapshot: TechnicalSnapshot, number_fn: Any) -> str:
    """Telegram'a eklenecek kısa teknik analiz özeti."""
    return "\n".join(
        [
            "<b>Teknik analiz (eğitim amaçlı)</b>",
            f"RSI(14): {number_fn(snapshot.rsi14)}",
            f"MACD: {number_fn(snapshot.macd)}",
            f"MACD sinyal: {number_fn(snapshot.macd_signal)}",
            f"MA20: {number_fn(snapshot.ma20)}",
            f"MA50: {number_fn(snapshot.ma50)}",
            f"Destek (20): {number_fn(snapshot.support20)}",
            f"Direnç (20): {number_fn(snapshot.resistance20)}",
            "<i>Göstergeler tek başına al/sat sinyali değildir.</i>",
        ]
    )
