from __future__ import annotations

from pathlib import Path

from nexa.providers import BinanceClient, CoinGeckoClient, YahooBistClient, COINGECKO_COIN_IDS
from nexa.visual_cards import save_quote_card


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "live-previews"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    bist = YahooBistClient()
    stock_quote = bist.get_quote("THYAO")
    stock_fundamentals = bist.get_fundamentals("THYAO")
    stock_frame = bist.get_ohlcv("THYAO", "1y", "1d")
    stock_snapshot = {
        "name": stock_fundamentals.get("name") or stock_quote.name,
        "market_cap": stock_fundamentals.get("market_cap"),
    }
    stock_path = save_quote_card(stock_quote, OUTPUT, snapshot=stock_snapshot, ohlcv=stock_frame, time_range="1A")

    binance = BinanceClient()
    crypto_quote = binance.get_quote("BTC")
    crypto_frame = binance.get_ohlcv("BTC", "1d", 60)
    crypto_snapshot = CoinGeckoClient().get_market_snapshot(COINGECKO_COIN_IDS["BTC"])
    crypto_path = save_quote_card(crypto_quote, OUTPUT, snapshot=crypto_snapshot, ohlcv=crypto_frame, time_range="1A")

    print(stock_path)
    print(crypto_path)


if __name__ == "__main__":
    main()
