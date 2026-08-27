"""Alarm scheduler yardımcıları."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from telegram.ext import ContextTypes

from .alerts import alarm_matches
from .db import Database
from .formatting import format_quote
from .providers import BinanceClient, MarketDataError, YahooBistClient

LOGGER = logging.getLogger(__name__)


def _quote_client(context: ContextTypes.DEFAULT_TYPE, asset_type: str):
    return context.application.bot_data["bist" if asset_type == "stock" else "binance"]


async def check_active_alarms(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aktif alarmları kontrol eder; aynı sembolü bir kez sorgular."""
    db: Database = context.application.bot_data["db"]
    alarms = db.list_all_active_alarms()
    if not alarms:
        return

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for alarm in alarms:
        grouped[(alarm["asset_type"], alarm["symbol"])].append(alarm)

    quotes: dict[tuple[str, str], Any] = {}
    for key in grouped:
        asset_type, symbol = key
        try:
            client = _quote_client(context, asset_type)
            quotes[key] = await asyncio.to_thread(client.get_quote, symbol)
        except (MarketDataError, ValueError):
            LOGGER.warning("Alarm için veri alınamadı: %s %s", asset_type, symbol)
        except Exception:
            LOGGER.exception("Alarm sağlayıcısı beklenmeyen hata verdi: %s %s", asset_type, symbol)

    for key, symbol_alarms in grouped.items():
        quote = quotes.get(key)
        if quote is None:
            continue
        for alarm in symbol_alarms:
            match = alarm_matches(alarm, quote)
            if not match:
                continue
            try:
                await context.bot.send_message(
                    chat_id=alarm["chat_id"],
                    text=(
                        f"<b>Nexa alarmı #{alarm['id']}</b>\n"
                        f"<code>{quote.symbol}</code>: {match.reason}.\n\n"
                        f"{format_quote(quote)}"
                    ),
                    parse_mode="HTML",
                )
                db.mark_alarm_triggered(match.alarm_id)
            except Exception:
                LOGGER.exception("Alarm bildirimi gönderilemedi: #%s", alarm["id"])


IMPORTANT_KAP_KEYWORDS = (
    "finansal",
    "temettü",
    "sermaye",
    "birleşme",
    "devralma",
    "pay alım",
    "geri alım",
    "bedelli",
    "bedelsiz",
    "özel durum",
    "yönetim kurulu",
)


async def check_kap_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    """KAP public sayfasındaki yeni ve konu başlığı önemli satırları iletir."""
    db: Database = context.application.bot_data["db"]
    client = context.application.bot_data.get("kap")
    if client is None:
        return
    try:
        items = await asyncio.to_thread(client.fetch_recent_disclosures, 20)
    except Exception:
        LOGGER.warning("KAP public sayfası scheduler tarafından okunamadı", exc_info=True)
        return

    had_baseline = db.kap_seen_count() > 0
    new_items = []
    for item in items:
        if db.mark_kap_seen(item.fingerprint, item.date, item.company, item.subject, item.url):
            if had_baseline:
                new_items.append(item)
    if not had_baseline:
        LOGGER.info("KAP başlangıç snapshot'ı kaydedildi; eski satırlar gönderilmedi")
        return

    chats = db.list_user_chat_ids()
    for item in new_items:
        subject = item.subject.lower()
        if not any(keyword in subject for keyword in IMPORTANT_KAP_KEYWORDS):
            continue
        text = (
            "<b>Yeni önemli KAP bildirimi</b>\n"
            f"{item.date} — <b>{item.company}</b>\n"
            f"{item.subject}"
        )
        if item.url:
            text += f"\n<a href=\"{item.url}\">KAP bildirimini aç</a>"
        for chat_id in chats:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            except Exception:
                LOGGER.exception("KAP bildirimi gönderilemedi: %s", chat_id)
