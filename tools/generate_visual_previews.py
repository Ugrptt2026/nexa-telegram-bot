from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from nexa.providers import Quote
from nexa.technical_analysis import TechnicalSnapshot
from nexa.visual_cards import (
    save_help_card,
    save_portfolio_card,
    save_quote_card,
    save_start_card,
    save_technical_card,
)

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "previews"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
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
        source="Yahoo Finance via yfinance",
        delayed=True,
        note="Resmi ve garantili gerçek zamanlı BIST API'si değildir; veri gecikmeli olabilir.",
    )
    snapshot = {
        "market_cap_usd": 1_340_000_000_000,
        "volume_24h_usd": 24_600_000_000,
        "change_24h_pct": 1.35,
    }
    technical = TechnicalSnapshot(55.2, 1.2, 0.8, 150.0, 140.0, 120.0, 170.0)
    position = {"asset_type": "stock", "symbol": "THYAO", "quantity": 10.0, "cost": 1_200.0, "currency": "TRY"}

    paths = [
        save_start_card("Ugrptt", OUTPUT),
        save_help_card(OUTPUT),
        save_quote_card(quote, OUTPUT, snapshot=snapshot, ohlcv=ohlcv),
        save_technical_card("THYAO", technical, OUTPUT, last_price=164.0, source="NEXA ücretsiz veri katmanı"),
        save_portfolio_card([position], {("stock", "THYAO"): quote}, OUTPUT),
    ]
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
