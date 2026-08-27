from pathlib import Path

import pandas as pd

from nexa.charts import save_price_chart
from nexa.technical_analysis import calculate_indicators


def sample_ohlcv() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    close = pd.Series(range(100, 160), index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000,
        },
        index=index,
    )


def test_calculate_indicators_returns_expected_windows() -> None:
    snapshot = calculate_indicators(sample_ohlcv())
    assert snapshot.ma20 == 149.5
    assert snapshot.ma50 == 134.5
    assert snapshot.support20 == 138.0
    assert snapshot.resistance20 == 161.0
    assert snapshot.rsi14 == 100.0
    assert snapshot.macd is not None
    assert snapshot.macd_signal is not None


def test_save_price_chart_creates_png(tmp_path: Path) -> None:
    path = save_price_chart(sample_ohlcv(), "TEST chart", tmp_path)
    assert path.exists()
    assert path.suffix == ".png"
    assert path.stat().st_size > 1000
