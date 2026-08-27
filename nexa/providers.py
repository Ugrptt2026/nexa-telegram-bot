"""Ücretsiz/public piyasa veri sağlayıcıları.

Bu modül, sağlayıcıların birbirinin yerine geçebileceğini varsaymaz:
- Binance: kripto spot fiyatı ve OHLCV.
- yfinance/Yahoo: BIST için gecikmeli/garantisiz fallback.
- CoinGecko: opsiyonel Demo anahtarı ile market-cap/global veri.
- Alternative.me: ücretsiz Fear & Greed endpoint'i.

Hiçbir sağlayıcıdan işlem emri veya kişisel finansal veri alınmaz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd
import yfinance as yf


class MarketDataError(RuntimeError):
    """Sağlayıcıdan geçerli piyasa verisi alınamadığında kullanılır."""


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    name: str
    price: float
    change_pct: float | None
    volume: float | None
    currency: str
    as_of: datetime | None
    source: str
    delayed: bool
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FearGreed:
    value: int
    classification: str
    as_of: datetime | None
    source: str = "Alternative.me"


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    price: float
    quantity: float


@dataclass(frozen=True, slots=True)
class DepthSnapshot:
    symbol: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    as_of: datetime | None
    source: str
    available: bool = True
    note: str | None = None


def normalize_bist_symbol(symbol: str) -> str:
    """Kullanıcı sembolünü Yahoo BIST biçimine dönüştürür."""
    cleaned = symbol.strip().upper().replace(" ", "")
    if not cleaned:
        raise ValueError("Sembol boş olamaz")
    return cleaned if cleaned.endswith(".IS") else f"{cleaned}.IS"


def normalize_binance_symbol(symbol: str, quote_asset: str = "USDT") -> str:
    """BTC, BTCUSDT veya BTC/USDT biçimlerini Binance sembolüne çevirir."""
    cleaned = symbol.strip().upper().replace("/", "").replace("-", "")
    if not cleaned:
        raise ValueError("Sembol boş olamaz")
    quote = quote_asset.upper()
    return cleaned if cleaned.endswith(quote) else f"{cleaned}{quote}"


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


class _HttpProvider:
    def __init__(self, base_url: str, timeout: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = httpx.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "Nexa/0.1 (free-market-data-bot)"},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Veri sağlayıcısına erişilemedi: {self.base_url}") from exc


class BinanceClient(_HttpProvider):
    """Binance Spot public REST piyasa verisi istemcisi."""

    def __init__(self) -> None:
        super().__init__("https://api.binance.com")

    def get_quote(self, symbol: str) -> Quote:
        binance_symbol = normalize_binance_symbol(symbol)
        payload = self._get_json("api/v3/ticker/24hr", {"symbol": binance_symbol})
        price = _as_float(payload.get("lastPrice"))
        if price is None:
            raise MarketDataError(f"Binance sembolü bulunamadı: {binance_symbol}")
        change_pct = _as_float(payload.get("priceChangePercent"))
        close_time = payload.get("closeTime")
        as_of = (
            datetime.fromtimestamp(float(close_time) / 1000, tz=timezone.utc)
            if close_time
            else None
        )
        base = binance_symbol.removesuffix("USDT")
        return Quote(
            symbol=base,
            name=f"{base}/USDT",
            price=price,
            change_pct=change_pct,
            volume=_as_float(payload.get("quoteVolume")),
            currency="USDT",
            as_of=as_of,
            source="Binance Spot public API",
            delayed=False,
            note="24 saatlik değişim; fiyat USDT cinsindendir.",
            metadata={
                "open": _as_float(payload.get("openPrice")),
                "high": _as_float(payload.get("highPrice")),
                "low": _as_float(payload.get("lowPrice")),
                "previous_close": _as_float(payload.get("prevClosePrice")),
            },
        )

    def get_depth(self, symbol: str, limit: int = 10) -> DepthSnapshot:
        """Binance public order book: alış/satış kademelerini anahtarsız döndürür."""
        if not 1 <= limit <= 100:
            raise ValueError("depth limit 1 ile 100 arasında olmalıdır")
        binance_symbol = normalize_binance_symbol(symbol)
        payload = self._get_json("api/v3/depth", {"symbol": binance_symbol, "limit": limit})

        def parse_levels(raw_levels: Any, side: str) -> tuple[OrderBookLevel, ...]:
            levels: list[OrderBookLevel] = []
            for raw in raw_levels or []:
                if not isinstance(raw, (list, tuple)) or len(raw) < 2:
                    continue
                price = _as_float(raw[0])
                quantity = _as_float(raw[1])
                if price is not None and quantity is not None and price > 0 and quantity >= 0:
                    levels.append(OrderBookLevel(price, quantity))
            levels.sort(key=lambda level: level.price, reverse=side == "bid")
            return tuple(levels[:limit])

        bids = parse_levels(payload.get("bids"), "bid")
        asks = parse_levels(payload.get("asks"), "ask")
        if not bids or not asks:
            raise MarketDataError(f"Emir defteri bulunamadı: {binance_symbol}")
        return DepthSnapshot(
            symbol=binance_symbol.removesuffix("USDT"),
            bids=bids,
            asks=asks,
            as_of=datetime.now(timezone.utc),
            source="Binance Spot public API /api/v3/depth",
            note="Gerçek public emir defteri; limit 10 kademe.",
        )

    def get_ohlcv(self, symbol: str, interval: str = "1d", limit: int = 120) -> pd.DataFrame:
        if not 1 <= limit <= 1000:
            raise ValueError("limit 1 ile 1000 arasında olmalıdır")
        binance_symbol = normalize_binance_symbol(symbol)
        rows = self._get_json(
            "api/v3/klines",
            {"symbol": binance_symbol, "interval": interval, "limit": limit},
        )
        if not rows:
            raise MarketDataError(f"OHLCV bulunamadı: {binance_symbol}")
        frame = pd.DataFrame(
            rows,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "unused",
            ],
        )
        frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame.set_index("timestamp")[["open", "high", "low", "close", "volume"]]


class CoinGeckoClient(_HttpProvider):
    """CoinGecko API istemcisi; Demo anahtarı varsa header'a ekler."""

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__("https://api.coingecko.com/api/v3")
        self.api_key = api_key or os.getenv("COINGECKO_DEMO_API_KEY", "").strip() or None

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            headers = {"User-Agent": "Nexa/0.1 (free-market-data-bot)"}
            if self.api_key:
                headers["x-cg-demo-api-key"] = self.api_key
            response = httpx.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                timeout=self.timeout,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("CoinGecko verisine erişilemedi; rate limit veya anahtar kontrol edin") from exc

    def get_global(self) -> dict[str, Any]:
        payload = self._get_json("global")
        data = payload.get("data", {})
        return {
            "total_market_cap_usd": _as_float(data.get("total_market_cap", {}).get("usd")),
            "total_volume_24h_usd": _as_float(data.get("total_volume", {}).get("usd")),
            "btc_dominance_pct": _as_float(data.get("market_cap_percentage", {}).get("btc")),
            "active_cryptocurrencies": data.get("active_cryptocurrencies"),
            "updated_at": data.get("updated_at"),
            "source": "CoinGecko Demo/keyless API",
        }

    def get_market_snapshot(self, coin_id: str) -> dict[str, Any]:
        rows = self._get_json(
            "coins/markets",
            {
                "vs_currency": "usd",
                "ids": coin_id,
                "price_change_percentage": "24h",
                "per_page": 1,
                "page": 1,
            },
        )
        if not rows:
            raise MarketDataError(f"CoinGecko coin id bulunamadı: {coin_id}")
        row = rows[0]
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "symbol": str(row.get("symbol", "")).upper(),
            "price_usd": _as_float(row.get("current_price")),
            "market_cap_usd": _as_float(row.get("market_cap")),
            "volume_24h_usd": _as_float(row.get("total_volume")),
            "change_24h_pct": _as_float(row.get("price_change_percentage_24h")),
            "source": "CoinGecko Demo/keyless API",
        }


class AlternativeClient(_HttpProvider):
    """Alternative.me’nin ücretsiz ve anahtarsız endpoint'leri."""

    def __init__(self) -> None:
        super().__init__("https://api.alternative.me")

    def get_fear_greed(self) -> FearGreed:
        payload = self._get_json("fng/", {"limit": 1})
        row = (payload.get("data") or [None])[0]
        if not row:
            raise MarketDataError("Fear & Greed verisi bulunamadı")
        try:
            value = int(row["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("Fear & Greed yanıtı beklenen biçimde değil") from exc
        timestamp = row.get("timestamp")
        as_of = (
            datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            if timestamp
            else None
        )
        return FearGreed(
            value=value,
            classification=str(row.get("value_classification", "Bilinmiyor")),
            as_of=as_of,
        )


BIST_DISPLAY_NAMES: dict[str, str] = {
    "THYAO": "Türk Hava Yolları",
    "ASELS": "Aselsan",
    "AKBNK": "Akbank",
    "EREGL": "Ereğli Demir Çelik",
    "TUPRS": "Tüpraş",
    "BIMAS": "BİM Birleşik Mağazalar",
    "SISE": "Şişecam",
    "TCELL": "Turkcell",
    "KOZAL": "Koza Altın",
    "PGSUS": "Pegasus",
}


class YahooBistClient:
    """Yahoo Finance verisini yfinance ile kullanan BIST istemcisi.

    yfinance resmi Yahoo SDK'sı değildir; bu nedenle quote `delayed=True`
    ve kaynak/uyarı bilgisiyle döndürülür.
    """

    def get_quote(self, symbol: str) -> Quote:
        yahoo_symbol = normalize_bist_symbol(symbol)
        try:
            history = yf.Ticker(yahoo_symbol).history(
                period="5d",
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:  # yfinance farklı ağ/crumb hataları üretebilir
            raise MarketDataError(f"Yahoo Finance verisine erişilemedi: {yahoo_symbol}") from exc
        if history.empty or "Close" not in history:
            raise MarketDataError(f"BIST sembolü için veri bulunamadı: {yahoo_symbol}")
        closes = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if closes.empty:
            raise MarketDataError(f"BIST kapanış fiyatı bulunamadı: {yahoo_symbol}")
        price = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        change_pct = ((price / previous) - 1) * 100 if previous else None
        volumes = pd.to_numeric(history.get("Volume"), errors="coerce").dropna()
        index_value = history.index[-1]
        as_of = pd.Timestamp(index_value).to_pydatetime()
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        display_symbol = yahoo_symbol.removesuffix(".IS")
        latest_row = history.iloc[-1]
        return Quote(
            symbol=display_symbol,
            name=BIST_DISPLAY_NAMES.get(display_symbol, display_symbol),
            price=price,
            change_pct=change_pct,
            volume=float(volumes.iloc[-1]) if not volumes.empty else None,
            currency="TRY",
            as_of=as_of,
            source="Yahoo Finance via yfinance",
            delayed=True,
            note="Resmi ve garantili gerçek zamanlı BIST API'si değildir; veri gecikmeli olabilir.",
            metadata={
                "open": _as_float(latest_row.get("Open")),
                "high": _as_float(latest_row.get("High")),
                "low": _as_float(latest_row.get("Low")),
                "previous_close": previous,
            },
        )

    def get_ohlcv(self, symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        yahoo_symbol = normalize_bist_symbol(symbol)
        try:
            history = yf.Ticker(yahoo_symbol).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            raise MarketDataError(f"Yahoo OHLCV verisine erişilemedi: {yahoo_symbol}") from exc
        if history.empty:
            raise MarketDataError(f"BIST OHLCV bulunamadı: {yahoo_symbol}")
        columns = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        result = history.rename(columns=columns)
        required = ["open", "high", "low", "close", "volume"]
        return result[[column for column in required if column in result.columns]].dropna(how="all")


    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        """Yahoo info alanlarından mevcut temel oranları döndürür.

        Alanlar eksik olabilir; eksik değerler None olarak bırakılır. Bu
        değerler yatırım tavsiyesi değil, sağlayıcının son bildirdiği özet
        oranlardır ve finansal dönem etiketi taşımayabilir.
        """
        yahoo_symbol = normalize_bist_symbol(symbol)
        try:
            info = yf.Ticker(yahoo_symbol).info
        except Exception as exc:
            raise MarketDataError(f"BIST temel verisine erişilemedi: {yahoo_symbol}") from exc
        raw_yield = _as_float(info.get("dividendYield"))
        dividend_rate = _as_float(info.get("dividendRate"))
        reference_price = _as_float(info.get("currentPrice")) or _as_float(info.get("regularMarketPrice"))
        if dividend_rate is not None and reference_price:
            dividend_yield_pct = (dividend_rate / reference_price) * 100
        elif raw_yield is not None:
            # Yahoo alanı bazı piyasalarda 0.0228, bazılarında 2.28 dönebilir.
            dividend_yield_pct = raw_yield if abs(raw_yield) > 1 else raw_yield * 100
        else:
            dividend_yield_pct = None
        return {
            "symbol": yahoo_symbol.removesuffix(".IS"),
            "name": info.get("shortName") or yahoo_symbol.removesuffix(".IS"),
            "pe": _as_float(info.get("trailingPE")),
            "pb": _as_float(info.get("priceToBook")),
            "dividend_yield_pct": dividend_yield_pct,
            "market_cap": _as_float(info.get("marketCap")),
            "source": "Yahoo Finance via yfinance",
            "note": "Temettü verimi mevcutsa yıllık temettü / referans fiyat ile hesaplanır; oranların dönemi ve kapsamı sağlayıcı metadatasına bağlıdır.",
        }


class YahooMacroClient:
    """Yahoo'daki endeks, FX ve emtia sembolleri için gecikmeli istemci."""

    SYMBOLS: dict[str, tuple[str, str]] = {
        "XU030": ("XU030.IS", "BIST 30"),
        "XU100": ("XU100.IS", "BIST 100"),
        "USDTRY": ("USDTRY=X", "USD/TRY"),
        "EURTRY": ("EURTRY=X", "EUR/TRY"),
        "ALTIN": ("GC=F", "Ons altın"),
    }

    def get_daily_bar(self, symbol: str) -> dict[str, Any]:
        key = symbol.strip().upper()
        if key not in self.SYMBOLS:
            raise ValueError("Sembol XU030, XU100, USDTRY, EURTRY veya ALTIN olmalı")
        yahoo_symbol, display_name = self.SYMBOLS[key]
        try:
            history = yf.Ticker(yahoo_symbol).history(
                period="5d",
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            raise MarketDataError(f"Günlük bar alınamadı: {yahoo_symbol}") from exc
        if history.empty:
            raise MarketDataError(f"Günlük bar bulunamadı: {yahoo_symbol}")
        row = history.iloc[-1]
        values = {name.lower(): _as_float(row.get(name)) for name in ("Open", "High", "Low", "Close")}
        if values["close"] is None:
            raise MarketDataError(f"Günlük kapanış bulunamadı: {yahoo_symbol}")
        return {
            "symbol": key,
            "name": display_name,
            "date": pd.Timestamp(history.index[-1]).strftime("%Y-%m-%d"),
            **values,
            "source": "Yahoo Finance via yfinance",
            "note": "Gecikmeli/harici veri kaynağı; gerçek zamanlılık garanti edilmez.",
        }

    def get_quote(self, symbol: str) -> Quote:
        key = symbol.strip().upper()
        if key not in self.SYMBOLS:
            raise ValueError("Sembol XU030, XU100, USDTRY, EURTRY veya ALTIN olmalı")
        yahoo_symbol, display_name = self.SYMBOLS[key]
        try:
            history = yf.Ticker(yahoo_symbol).history(
                period="5d",
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
        except Exception as exc:
            raise MarketDataError(f"Makro veri alınamadı: {yahoo_symbol}") from exc
        if history.empty or "Close" not in history:
            raise MarketDataError(f"Makro sembolü için veri bulunamadı: {yahoo_symbol}")
        closes = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if closes.empty:
            raise MarketDataError(f"Makro kapanış fiyatı bulunamadı: {yahoo_symbol}")
        price = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        change_pct = ((price / previous) - 1) * 100 if previous else None
        index_value = pd.Timestamp(history.index[-1]).to_pydatetime()
        if index_value.tzinfo is None:
            index_value = index_value.replace(tzinfo=timezone.utc)
        currency = "TRY" if key in {"XU030", "XU100", "USDTRY", "EURTRY"} else "USD"
        latest_row = history.iloc[-1]
        return Quote(
            symbol=key,
            name=display_name,
            price=price,
            change_pct=change_pct,
            volume=None,
            currency=currency,
            as_of=index_value,
            source="Yahoo Finance via yfinance",
            delayed=True,
            note="Gecikmeli/harici veri kaynağı; gerçek zamanlılık garanti edilmez.",
            metadata={
                "open": _as_float(latest_row.get("Open")),
                "high": _as_float(latest_row.get("High")),
                "low": _as_float(latest_row.get("Low")),
                "previous_close": previous,
            },
        )


COINGECKO_COIN_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "TRX": "tron",
}
