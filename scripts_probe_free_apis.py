"""Nexa sağlayıcılarının erişilebilirlik smoke test'i.

Bu dosya tek seferlik geliştirme doğrulaması içindir. Çıktıdaki canlı fiyatlar
kalıcı veri veya yatırım tavsiyesi olarak kullanılmaz.
"""

from nexa.providers import AlternativeClient, BinanceClient, CoinGeckoClient, YahooBistClient


def main() -> None:
    checks = [
        ("Binance BTC", lambda: BinanceClient().get_quote("BTC")),
        ("Alternative.me FNG", lambda: AlternativeClient().get_fear_greed()),
        ("CoinGecko global", lambda: CoinGeckoClient().get_global()),
        ("Yahoo BIST THYAO", lambda: YahooBistClient().get_quote("THYAO")),
    ]
    for label, callback in checks:
        try:
            result = callback()
            print(f"OK   {label}: {result}")
        except Exception as exc:
            print(f"FAIL {label}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
