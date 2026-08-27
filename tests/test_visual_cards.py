from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from PIL import Image

from nexa.kap import Disclosure
from nexa.providers import FearGreed, Quote
from nexa.scanner import Mover
from nexa.technical_analysis import TechnicalSnapshot
from nexa.visual_cards import (
    save_alarms_card,
    save_daily_summary_card,
    save_fear_greed_card,
    save_fundamentals_card,
    save_global_market_card,
    save_help_card,
    save_kap_card,
    save_movers_card,
    save_notice_card,
    save_portfolio_card,
    save_quote_card,
    save_start_card,
    save_technical_card,
    save_watchlist_card,
)


def _assert_mobile_card(path):
    assert path.exists()
    assert path.stat().st_size > 1_000
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.width == 1080
        assert image.height >= 720
        assert image.height / image.width >= 0.65
        # Cards use either the dark base or the NEXA green top rail at (0, 0).
        assert image.getpixel((0, 0))[:3] in {(7, 17, 29), (87, 227, 137)}


def test_visual_cards_cover_main_bot_outputs(tmp_path):
    index = pd.date_range("2026-01-01", periods=65, freq="D", tz="UTC")
    close = pd.Series(range(100, 165), index=index, dtype=float)
    ohlcv = pd.DataFrame({"close": close, "high": close + 2, "low": close - 2}, index=index)
    quote = Quote(
        symbol="THYAO",
        name="Türk Hava Yolları",
        price=164.0,
        change_pct=2.15,
        volume=5_680_000,
        currency="TRY",
        as_of=datetime.now(timezone.utc),
        source="Test provider",
        delayed=True,
        note="Test verisi.",
        metadata={"open": 158.0, "high": 166.0, "low": 156.0, "previous_close": 160.5},
    )
    snapshot = {"name": "Türk Hava Yolları", "market_cap": 1_200_000_000_000}
    crypto_quote = Quote(
        symbol="BTC",
        name="BTC/USDT",
        price=68_420.50,
        change_pct=1.35,
        volume=24_600_000_000,
        currency="USDT",
        as_of=datetime.now(timezone.utc),
        source="Binance Spot public API",
        delayed=False,
        note="24 saatlik değişim; fiyat USDT cinsindendir.",
        metadata={"open": 67_500.0, "high": 68_950.0, "low": 67_120.0, "previous_close": 67_509.0},
    )
    crypto_snapshot = {"name": "Bitcoin", "market_cap_usd": 1_340_000_000_000, "volume_24h_usd": 24_600_000_000, "change_24h_pct": 1.35}
    technical = TechnicalSnapshot(55.2, 1.2, 0.8, 150.0, 140.0, 120.0, 170.0)
    mover = Mover("THYAO", 164.0, 2.15, 5_680_000, "Test provider")
    items = [{"name": "BIST 100", "date": "2026-08-27", "open": 100.0, "high": 105.0, "low": 98.0, "close": 103.0}]
    position = {"asset_type": "stock", "symbol": "THYAO", "quantity": 10.0, "cost": 1_200.0, "currency": "TRY"}
    alarm = {"id": 1, "asset_type": "stock", "symbol": "THYAO", "condition": "above", "target": 170.0}
    watch = {"asset_type": "stock", "symbol": "THYAO"}
    disclosure = Disclosure("27.08.2026", "FIN", "THYAO", "Finansal sonuç açıklaması")

    paths = [
        save_start_card("Ugrptt", tmp_path),
        save_help_card(tmp_path),
        save_quote_card(quote, tmp_path, snapshot=snapshot, ohlcv=ohlcv),
        save_quote_card(crypto_quote, tmp_path, snapshot=crypto_snapshot, ohlcv=ohlcv),
        save_technical_card("THYAO", technical, tmp_path, last_price=164.0),
        save_fundamentals_card({"symbol": "THYAO", "name": "Türk Hava Yolları", "pe": 4.85, "pb": 1.32, "dividend_yield_pct": 2.2, "market_cap": 1_200_000_000, "source": "Test"}, tmp_path),
        save_global_market_card({"total_market_cap_usd": 2_000_000_000_000, "total_volume_24h_usd": 70_000_000_000, "btc_dominance_pct": 54.0, "active_cryptocurrencies": 10_000, "source": "Test"}, tmp_path),
        save_fear_greed_card(FearGreed(65, "Greed", datetime.now(timezone.utc)), tmp_path),
        save_daily_summary_card(items, tmp_path),
        save_movers_card({"gainers": [mover], "losers": [Mover("ASELS", 60.0, -1.2, 1_000_000, "Test")]}, tmp_path, "BIST"),
        save_watchlist_card([watch], tmp_path),
        save_alarms_card([alarm], tmp_path),
        save_portfolio_card([position], {("stock", "THYAO"): quote}, tmp_path),
        save_kap_card([disclosure], tmp_path),
        save_notice_card("NEXA BİLGİ", "Deneme mesajı", tmp_path),
    ]
    for path in paths:
        _assert_mobile_card(path)


def test_market_card_logs_empty_ohlc_instead_of_silently_skipping(tmp_path, caplog):
    quote = Quote(
        symbol="THYAO",
        name="Türk Hava Yolları",
        price=300.0,
        change_pct=0.4,
        volume=1_000_000,
        currency="TRY",
        as_of=None,
        source="Test provider",
        delayed=True,
    )
    with caplog.at_level("ERROR"):
        path = save_quote_card(quote, tmp_path, ohlcv=pd.DataFrame())
    assert path.exists()
    assert "OHLC/candlestick" in caplog.text



def test_volume_profile_card_is_mobile_png(tmp_path) -> None:
    from nexa.market_profile import calculate_volume_profile
    from nexa.visual_cards import save_volume_profile_card

    index = pd.date_range("2026-01-01", periods=30, freq="D", tz="UTC")
    close = pd.Series(range(100, 130), index=index, dtype=float)
    ohlcv = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": pd.Series(range(1_000, 31_000, 1_000), index=index, dtype=float),
        },
        index=index,
    )
    quote = Quote(
        symbol="THYAO",
        name="Türk Hava Yolları",
        price=129.0,
        change_pct=1.1,
        volume=30_000,
        currency="TRY",
        as_of=None,
        source="Yahoo Finance via yfinance",
        delayed=True,
    )
    profile = calculate_volume_profile(ohlcv, bars=30, zones=5)
    path = save_volume_profile_card("THYAO", quote, profile, tmp_path)
    _assert_mobile_card(path)
    with Image.open(path) as image:
        assert image.size == (1080, 1640)
