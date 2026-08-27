from pathlib import Path

from nexa.market_profile import calculate_volume_profile
from nexa.providers import BinanceClient, YahooBistClient
from nexa.visual_cards import save_depth_card, save_volume_profile_card


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "previews"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bist = YahooBistClient()
    binance = BinanceClient()

    thyao = bist.get_quote("THYAO")
    thyao_ohlcv = bist.get_ohlcv("THYAO", "3mo", "1d")
    thyao_profile = calculate_volume_profile(thyao_ohlcv, bars=30, zones=5)
    save_volume_profile_card(thyao.symbol, thyao, thyao_profile, OUTPUT)
    btc = binance.get_quote("BTC")
    depth = binance.get_depth("BTC", limit=10)
    save_depth_card(btc.symbol, "crypto", OUTPUT, depth=depth, quote=btc)

    # Keep the stable preview names used by the documentation.
    (OUTPUT / "volume_profile_thyao.png").rename(OUTPUT / "volume_profile_thyao.png")
    (OUTPUT / "depth_crypto_btc.png").rename(OUTPUT / "depth_btc.png")
    print(OUTPUT / "volume_profile_thyao.png")
    print(OUTPUT / "depth_btc.png")


if __name__ == "__main__":
    main()
