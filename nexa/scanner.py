"""Ücretsiz kaynaklarla temel piyasa taramaları."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .providers import BinanceClient, MarketDataError, YahooBistClient


@dataclass(frozen=True, slots=True)
class Mover:
    symbol: str
    price: float
    change_pct: float
    volume: float | None
    source: str


def scan_crypto_movers(client: BinanceClient, limit: int = 10) -> dict[str, list[Mover]]:
    """USDT spot çiftlerini 24 saatlik değişime göre sıralar."""
    rows = client._get_json("api/v3/ticker/24hr")
    movers: list[Mover] = []
    excluded = {"USDCUSDT", "BUSDUSDT", "DAIUSDT", "TUSDUSDT", "FDUSDUSDT"}
    for row in rows:
        symbol = str(row.get("symbol", ""))
        if not symbol.endswith("USDT") or symbol in excluded:
            continue
        try:
            price = float(row["lastPrice"])
            change = float(row["priceChangePercent"])
        except (KeyError, TypeError, ValueError):
            continue
        volume = None
        try:
            volume = float(row["quoteVolume"])
        except (KeyError, TypeError, ValueError):
            pass
        movers.append(Mover(symbol=symbol.removesuffix("USDT"), price=price, change_pct=change, volume=volume, source="Binance Spot public API"))
    movers.sort(key=lambda item: item.change_pct)
    return {"losers": movers[:limit], "gainers": list(reversed(movers[-limit:]))}


def scan_bist_symbols(client: YahooBistClient, symbols: list[str], limit: int = 10) -> dict[str, list[Mover]]:
    """BIST sembollerini tek tek, düşük frekansta tarar.

    Yahoo/yfinance için sembol evreni sağlayıcı tarafından eksiksiz ve canlı
    bir BIST 30/100 listesi olarak garanti edilmediğinden çağıran taraf evreni
    açıkça vermelidir.
    """
    movers: list[Mover] = []
    for symbol in symbols[:100]:
        try:
            quote = client.get_quote(symbol)
        except (MarketDataError, ValueError):
            continue
        if quote.change_pct is None:
            continue
        movers.append(Mover(symbol=quote.symbol, price=quote.price, change_pct=quote.change_pct, volume=quote.volume, source=quote.source))
    movers.sort(key=lambda item: item.change_pct)
    return {"losers": movers[:limit], "gainers": list(reversed(movers[-limit:]))}


def format_movers(result: dict[str, list[Mover]], number_fn: Any) -> str:
    def line(item: Mover) -> str:
        return f"<code>{item.symbol}</code> {number_fn(item.price)} ({'+' if item.change_pct >= 0 else ''}{number_fn(item.change_pct)}%)"

    lines = ["<b>Temel tarama</b>", "", "<b>En çok yükselenler</b>"]
    lines.extend(line(item) for item in result["gainers"])
    lines.extend(["", "<b>En çok düşenler</b>"])
    lines.extend(line(item) for item in result["losers"])
    return "\n".join(lines)
