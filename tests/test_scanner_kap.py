import pytest

from nexa.kap import Disclosure, format_disclosures
from nexa.scanner import scan_crypto_movers
from nexa.providers import BinanceClient


def test_kap_disclosure_fingerprint_is_stable() -> None:
    first = Disclosure("2026-08-27", "A1", "TEST", "Temettü açıklaması", "https://kap.org.tr/a")
    second = Disclosure("2026-08-27", "A1", "TEST", "Temettü açıklaması", "https://kap.org.tr/a")
    assert first.fingerprint == second.fingerprint
    assert "Temettü açıklaması" in format_disclosures([first])


def test_crypto_movers_filters_usdt_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BinanceClient()
    monkeypatch.setattr(
        client,
        "_get_json",
        lambda path, params=None: [
            {"symbol": "AAAUSDT", "lastPrice": "10", "priceChangePercent": "5", "quoteVolume": "100"},
            {"symbol": "BBBUSDT", "lastPrice": "10", "priceChangePercent": "-7", "quoteVolume": "200"},
            {"symbol": "USDCUSDT", "lastPrice": "1", "priceChangePercent": "0", "quoteVolume": "500"},
            {"symbol": "AAABTC", "lastPrice": "1", "priceChangePercent": "99", "quoteVolume": "1"},
        ],
    )
    result = scan_crypto_movers(client, limit=10)
    assert result["gainers"][0].symbol == "AAA"
    assert result["losers"][0].symbol == "BBB"
