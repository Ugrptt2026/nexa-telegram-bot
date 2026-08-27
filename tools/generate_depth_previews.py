from pathlib import Path

from nexa.providers import BinanceClient, YahooBistClient
from nexa.visual_cards import save_depth_card


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "previews"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bist = YahooBistClient()
    binance = BinanceClient()

    thyao = bist.get_quote("THYAO")
    save_depth_card(thyao.symbol, "stock", OUTPUT, quote=thyao)
    btc = binance.get_quote("BTC")
    depth = binance.get_depth("BTC", limit=10)
    save_depth_card(btc.symbol, "crypto", OUTPUT, depth=depth, quote=btc)

    # Keep the stable preview names used by the documentation.
    (OUTPUT / "depth_stock_thyao.png").rename(OUTPUT / "depth_thyao.png")
    (OUTPUT / "depth_crypto_btc.png").rename(OUTPUT / "depth_btc.png")
    print(OUTPUT / "depth_thyao.png")
    print(OUTPUT / "depth_btc.png")


if __name__ == "__main__":
    main()
