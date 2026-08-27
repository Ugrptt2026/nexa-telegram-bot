import pandas as pd
import pytest

from nexa.market_profile import calculate_volume_profile


def test_volume_profile_calculates_real_ohlcv_volume_buckets() -> None:
    frame = pd.DataFrame(
        {
            "open": [10, 11, 12, 11, 10, 10],
            "high": [12, 13, 13, 12, 11, 11],
            "low": [9, 10, 11, 10, 9, 9],
            "close": [11, 12, 11, 10, 10, 11],
            "volume": [100, 200, 300, 400, 500, 600],
        },
        index=pd.date_range("2026-01-01", periods=6, freq="D"),
    )
    profile = calculate_volume_profile(frame, bars=6, zones=3)

    assert profile.period_bars == 6
    assert profile.total_volume == 2100
    assert profile.up_volume == 900
    assert profile.down_volume == 700
    assert profile.flat_volume == 500
    assert profile.average_volume == 350
    assert profile.latest_volume == 600
    assert profile.latest_vs_average_pct == pytest.approx(71.4285714)
    assert profile.total_turnover == pytest.approx(22366.6666667)
    assert profile.average_turnover == pytest.approx(3727.7777778)
    assert profile.latest_turnover == pytest.approx(6200)
    assert len(profile.zones) == 3
    assert sum(zone.volume for zone in profile.zones) == 2100
    assert sum(zone.share_pct for zone in profile.zones) == pytest.approx(100)
    assert sum(zone.turnover for zone in profile.zones) == pytest.approx(profile.total_turnover)
    assert sum(zone.turnover_share_pct for zone in profile.zones) == pytest.approx(100)
    assert len(profile.recent_bars) == 6
    assert profile.recent_bars[-1].typical_price == pytest.approx(10.3333333)
    assert profile.recent_bars[-1].turnover == pytest.approx(6200)


def test_volume_profile_rejects_missing_or_short_ohlcv() -> None:
    with pytest.raises(ValueError, match="boş"):
        calculate_volume_profile(pd.DataFrame(), bars=30, zones=5)

    frame = pd.DataFrame({"open": [1, 2], "high": [2, 3], "low": [0, 1], "close": [2, 2], "volume": [10, 20]})
    with pytest.raises(ValueError, match="yeterli"):
        calculate_volume_profile(frame, bars=30, zones=5)
