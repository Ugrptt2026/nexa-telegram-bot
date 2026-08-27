"""Telegram mesaj biçimlendirme yardımcıları."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .providers import FearGreed, Quote


def number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def integer(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", ".")


def signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{number(value)}%"


def date_text(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M UTC")


def format_quote(quote: Quote) -> str:
    delayed_line = "Gecikmeli/harici kaynak" if quote.delayed else "Anlık borsa fiyatı"
    lines = [
        f"<b>{quote.symbol}</b> — {quote.name}",
        f"Fiyat: <b>{number(quote.price)}</b> {quote.currency}",
        f"24 saat/değişim: <b>{signed_pct(quote.change_pct)}</b>",
        f"İşlem miktarı (adet): {number(quote.volume, 0) if quote.volume is not None else '—'}",
        f"Zaman: {date_text(quote.as_of)}",
        f"Kaynak: {quote.source}",
        f"Veri türü: {delayed_line}",
    ]
    official_turnover = quote.metadata.get("official_turnover")
    if official_turnover is not None:
        lines.insert(4, f"Güncel işlem hacmi (TL): {number(official_turnover, 0)}")
    if quote.note:
        lines.append(f"<i>Not: {quote.note}</i>")
    return "\n".join(lines)


def format_global_market(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            "<b>Kripto piyasa özeti</b>",
            f"Toplam piyasa değeri: {number(data.get('total_market_cap_usd'), 0)} USD",
            f"24 saatlik hacim: {number(data.get('total_volume_24h_usd'), 0)} USD",
            f"BTC dominansı: {signed_pct(data.get('btc_dominance_pct'))}",
            f"Aktif kripto sayısı: {integer(data.get('active_cryptocurrencies'))}",
            f"Kaynak: {data.get('source', '—')}",
        ]
    )


def format_fear_greed(index: FearGreed) -> str:
    return "\n".join(
        [
            "<b>Crypto Fear &amp; Greed Index</b>",
            f"Değer: <b>{index.value}/100</b>",
            f"Sınıf: {index.classification}",
            f"Zaman: {date_text(index.as_of)}",
            f"Kaynak: {index.source}",
            "<i>Bu gösterge tek başına yatırım kararı için kullanılmamalıdır.</i>",
        ]
    )


def format_watchlist(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<b>İzleme listeniz</b>\n\nListeniz boş."
    lines = ["<b>İzleme listeniz</b>"]
    for item in items:
        kind = "BIST" if item["asset_type"] == "stock" else "Kripto"
        lines.append(f"• {kind}: <code>{item['symbol']}</code>")
    return "\n".join(lines)


def format_alarms(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<b>Alarmlar</b>\n\nAktif alarmınız yok."
    condition_labels = {"above": "üstü", "below": "altı", "change_pct": "mutlak değişim"}
    lines = ["<b>Aktif alarmlar</b>"]
    for item in items:
        kind = "BIST" if item["asset_type"] == "stock" else "Kripto"
        condition = condition_labels.get(item["condition"], item["condition"])
        suffix = "%" if item["condition"] == "change_pct" else ""
        lines.append(
            f"#{item['id']} {kind} <code>{item['symbol']}</code> — {condition} {number(item['target'])}{suffix}"
        )
    return "\n".join(lines)


def format_portfolio(
    positions: list[dict[str, Any]],
    current_quotes: dict[tuple[str, str], Any] | None = None,
) -> str:
    if not positions:
        return "<b>Sanal portföy</b>\n\nHenüz pozisyon yok."
    current_quotes = current_quotes or {}
    lines = ["<b>Sanal portföy</b>", "<i>Maliyet, basit ortalama maliyet yöntemiyle hesaplanır.</i>"]
    for position in positions:
        kind = "BIST" if position["asset_type"] == "stock" else "Kripto"
        average_cost = position["cost"] / position["quantity"] if position["quantity"] else 0
        quote = current_quotes.get((position["asset_type"], position["symbol"]))
        market_value = quote.price * position["quantity"] if quote else None
        pnl = market_value - position["cost"] if market_value is not None else None
        pnl_text = f", K/Z {signed_pct((pnl / position['cost']) * 100) if position['cost'] else '—'}" if pnl is not None else ""
        lines.append(
            f"{kind} <code>{position['symbol']}</code>: "
            f"miktar {number(position['quantity'], 6)}, "
            f"maliyet {number(position['cost'])} {position['currency']}, "
            f"ort. {number(average_cost)} {position['currency']}"
            f"{pnl_text}"
        )
    return "\n".join(lines)


def format_fundamentals(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"<b>{data.get('symbol', '—')} temel özet</b>",
            f"Şirket: {data.get('name', '—')}",
            f"F/K (trailing): {number(data.get('pe'))}",
            f"PD/DD: {number(data.get('pb'))}",
            f"Temettü verimi: {signed_pct(data.get('dividend_yield_pct'))}",
            f"Piyasa değeri: {number(data.get('market_cap'), 0)}",
            f"Kaynak: {data.get('source', '—')}",
            f"<i>Not: {data.get('note', 'Oranlar eksik olabilir.')}</i>",
        ]
    )


def format_crypto_quote(quote: Quote, snapshot: dict[str, Any] | None = None) -> str:
    lines = [format_quote(quote)]
    if snapshot:
        lines.extend(
            [
                "",
                "<b>CoinGecko piyasa bilgisi</b>",
                f"Piyasa değeri: {number(snapshot.get('market_cap_usd'), 0)} USD",
                f"24 saatlik hacim: {number(snapshot.get('volume_24h_usd'), 0)} USD",
                f"CoinGecko 24 saat: {signed_pct(snapshot.get('change_24h_pct'))}",
                f"Kaynak: {snapshot.get('source', 'CoinGecko')}",
            ]
        )
    return "\n".join(lines)


def format_daily_summary(items: list[dict[str, Any]]) -> str:
    lines = ["<b>Nexa günlük piyasa özeti</b>"]
    for item in items:
        lines.append(
            f"<b>{item['name']}</b> ({item['date']}) — "
            f"Açılış {number(item.get('open'))}, "
            f"Yüksek {number(item.get('high'))}, "
            f"Düşük {number(item.get('low'))}, "
            f"Kapanış {number(item.get('close'))}"
        )
    lines.append("<i>Kaynak: Yahoo Finance via yfinance; gecikmeli/harici veridir.</i>")
    return "\n".join(lines)
