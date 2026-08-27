from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import nexa.providers as providers

from nexa.formatting import format_quote
from nexa.providers import (
    BinanceClient,
    FearGreed,
    Quote,
    normalize_bist_symbol,
    normalize_binance_symbol,
)


def test_symbol_normalization() -> None:
    assert normalize_bist_symbol("thyao") == "THYAO.IS"
    assert normalize_bist_symbol("THYAO.IS") == "THYAO.IS"
    assert normalize_binance_symbol("btc") == "BTCUSDT"
    assert normalize_binance_symbol("BTC/USDT") == "BTCUSDT"
    with pytest.raises(ValueError):
        normalize_bist_symbol(" ")


def test_quote_format_includes_source_and_delay_note() -> None:
    quote = Quote(
        symbol="THYAO",
        name="THYAO",
        price=302.5,
        change_pct=0.66,
        volume=1000,
        currency="TRY",
        as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
        source="Yahoo Finance via yfinance",
        delayed=True,
        note="Gecikmeli olabilir",
    )
    text = format_quote(quote)
    assert "302,50" in text
    assert "+0,66%" in text
    assert "Yahoo Finance" in text
    assert "Gecikmeli/harici kaynak" in text


def test_binance_quote_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BinanceClient()
    monkeypatch.setattr(
        client,
        "_get_json",
        lambda path, params=None: {
            "lastPrice": "65000.1",
            "priceChangePercent": "1.25",
            "quoteVolume": "1234",
            "openPrice": "64000",
            "highPrice": "66000",
            "lowPrice": "63000",
            "prevClosePrice": "64200",
            "closeTime": 0,
        },
    )
    quote = client.get_quote("btc")
    assert quote.symbol == "BTC"
    assert quote.price == 65000.1
    assert quote.change_pct == 1.25
    assert quote.delayed is False
    assert quote.metadata["open"] == 64000.0
    assert quote.metadata["high"] == 66000.0
    assert quote.metadata["low"] == 63000.0
    assert quote.metadata["previous_close"] == 64200.0


def test_fear_greed_is_immutable() -> None:
    index = FearGreed(value=50, classification="Neutral", as_of=None)
    assert index.value == 50


def test_fundamentals_calculates_dividend_yield_from_rate_and_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        providers.yf,
        "Ticker",
        lambda symbol: SimpleNamespace(
            info={
                "shortName": "TEST",
                "trailingPE": 10,
                "priceToBook": 2,
                "dividendYield": 2.28,
                "dividendRate": 6.88,
                "currentPrice": 302.5,
                "marketCap": 1000,
            }
        ),
    )
    result = providers.YahooBistClient().get_fundamentals("THYAO")
    assert result["dividend_yield_pct"] == pytest.approx(2.27438, rel=1e-4)


def test_binance_depth_parses_bid_ask_levels(monkeypatch) -> None:
    client = BinanceClient()
    monkeypatch.setattr(
        client,
        "_get_json",
        lambda path, params=None: {
            "lastUpdateId": 7,
            "bids": [["101", "2.5"], ["100", "4.0"]],
            "asks": [["102", "1.5"], ["103", "3.0"]],
        },
    )
    depth = client.get_depth("BTC", limit=2)
    assert depth.symbol == "BTC"
    assert [(level.price, level.quantity) for level in depth.bids] == [(101.0, 2.5), (100.0, 4.0)]
    assert [(level.price, level.quantity) for level in depth.asks] == [(102.0, 1.5), (103.0, 3.0)]
    assert depth.available is True
