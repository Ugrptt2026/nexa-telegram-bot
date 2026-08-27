"""Nexa Telegram botu."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .alerts import parse_alarm_condition, parse_asset_type
from .charts import save_price_chart
from .config import Settings
from .db import Database
from .formatting import (
    format_alarms,
    format_crypto_quote,
    format_daily_summary,
    format_fundamentals,
    format_portfolio,
    format_quote,
    format_watchlist,
    number,
)
from .kap import KAPPublicClient, format_disclosures
from .providers import (
    AlternativeClient,
    BinanceClient,
    CoinGeckoClient,
    COINGECKO_COIN_IDS,
    MarketDataError,
    YahooBistClient,
    YahooMacroClient,
    normalize_bist_symbol,
    normalize_binance_symbol,
)
from .scanner import format_movers, scan_bist_symbols, scan_crypto_movers
from .scheduler import check_active_alarms, check_kap_updates
from .technical_analysis import calculate_indicators, snapshot_to_text
from .texts import HELP_TEXT, MENU_LABELS, START_TEXT

LOGGER = logging.getLogger(__name__)


def main_menu() -> InlineKeyboardMarkup:
    """Ana menü için iki sütunlu inline keyboard oluşturur."""
    rows = [
        [
            InlineKeyboardButton(MENU_LABELS["stock"], callback_data="menu:stock"),
            InlineKeyboardButton(MENU_LABELS["crypto"], callback_data="menu:crypto"),
        ],
        [
            InlineKeyboardButton(MENU_LABELS["portfolio"], callback_data="menu:portfolio"),
            InlineKeyboardButton(MENU_LABELS["alerts"], callback_data="menu:alerts"),
        ],
        [
            InlineKeyboardButton(MENU_LABELS["watchlist"], callback_data="menu:watchlist"),
            InlineKeyboardButton(MENU_LABELS["help"], callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Ana menü", callback_data="menu:home")]]
    )


def canonical_symbol(asset_type: str, symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if asset_type == "stock":
        return normalize_bist_symbol(cleaned).removesuffix(".IS")
    return normalize_binance_symbol(cleaned).removesuffix("USDT")


def parse_number(raw: str) -> float:
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"Sayı okunamadı: {raw}") from exc


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcı kaydı ve ana menü."""
    if not update.effective_chat or not update.effective_user or not update.message:
        return

    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    db.upsert_user(
        chat_id=update.effective_chat.id,
        username=user.username,
        first_name=user.first_name,
    )
    name = user.first_name or user.username or "kullanıcı"
    await update.message.reply_text(
        START_TEXT.format(name=name),
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "<b>Nexa ana menüsü</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


async def _reply_quote(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    asset_type: str,
) -> None:
    if not update.message:
        return
    if not context.args:
        example = "THYAO" if asset_type == "stock" else "BTC"
        command = "hisse" if asset_type == "stock" else "kripto"
        await update.message.reply_text(
            f"Kullanım: <code>/{command} {example}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    symbol = context.args[0].upper()
    try:
        if asset_type == "stock":
            client = context.application.bot_data["bist"]
        else:
            client = context.application.bot_data["binance"]
        quote = await asyncio.to_thread(client.get_quote, symbol)
    except (MarketDataError, ValueError) as exc:
        await update.message.reply_text(
            f"<b>{symbol}</b> için veri alınamadı.\n\n{exc}",
            parse_mode=ParseMode.HTML,
        )
        return
    except Exception:
        LOGGER.exception("%s sorgusunda beklenmeyen hata: %s", asset_type, symbol)
        await update.message.reply_text(
            "Veri sağlayıcısı geçici olarak yanıt vermedi. Lütfen biraz sonra tekrar deneyin."
        )
        return

    snapshot = None
    if asset_type == "crypto":
        coin_id = COINGECKO_COIN_IDS.get(quote.symbol)
        if coin_id:
            try:
                snapshot = await asyncio.to_thread(
                    context.application.bot_data["coingecko"].get_market_snapshot,
                    coin_id,
                )
            except MarketDataError:
                LOGGER.info("CoinGecko coin özeti alınamadı: %s", quote.symbol)
    response = format_crypto_quote(quote, snapshot) if asset_type == "crypto" else format_quote(quote)
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)


async def technical_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 2:
        await update.message.reply_text(
            "Kullanım: <code>/teknik hisse THYAO</code> veya <code>/teknik kripto BTC</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        asset_type = parse_asset_type(context.args[0])
        symbol = canonical_symbol(asset_type, context.args[1])
        client = context.application.bot_data["bist" if asset_type == "stock" else "binance"]
        ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "6mo", "1d")
        snapshot = calculate_indicators(ohlcv)
    except (MarketDataError, ValueError) as exc:
        await update.message.reply_text(f"Teknik analiz alınamadı: {exc}")
        return
    await update.message.reply_text(
        f"<b>{symbol}</b>\n{snapshot_to_text(snapshot, number)}",
        parse_mode=ParseMode.HTML,
    )


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 2:
        await update.message.reply_text(
            "Kullanım: <code>/grafik hisse THYAO</code> veya <code>/grafik kripto BTC</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        asset_type = parse_asset_type(context.args[0])
        symbol = canonical_symbol(asset_type, context.args[1])
        client = context.application.bot_data["bist" if asset_type == "stock" else "binance"]
        ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "6mo", "1d")
        chart_path = await asyncio.to_thread(
            save_price_chart,
            ohlcv,
            f"Nexa — {symbol} fiyat grafiği",
            Path("/tmp") / "nexa_charts" / str(update.effective_chat.id if update.effective_chat else "unknown"),
        )
    except (MarketDataError, ValueError) as exc:
        await update.message.reply_text(f"Grafik üretilemedi: {exc}")
        return
    with chart_path.open("rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=f"{symbol} — kapanış, MA20 ve MA50\nKaynak: {getattr(ohlcv, 'source', 'Nexa ücretsiz veri katmanı')}",
        )


async def fundamentals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Kullanım: <code>/temel THYAO</code>", parse_mode=ParseMode.HTML)
        return
    try:
        symbol = canonical_symbol("stock", context.args[0])
        data = await asyncio.to_thread(context.application.bot_data["bist"].get_fundamentals, symbol)
    except (MarketDataError, ValueError) as exc:
        await update.message.reply_text(f"Temel oranlar alınamadı: {exc}")
        return
    await update.message.reply_text(format_fundamentals(data), parse_mode=ParseMode.HTML)


async def crypto_market_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        data = await asyncio.to_thread(context.application.bot_data["coingecko"].get_global)
    except MarketDataError as exc:
        await update.message.reply_text(f"Kripto piyasa özeti alınamadı: {exc}")
        return
    from .formatting import format_global_market

    await update.message.reply_text(format_global_market(data), parse_mode=ParseMode.HTML)


async def fear_greed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        index = await asyncio.to_thread(context.application.bot_data["alternative"].get_fear_greed)
    except MarketDataError as exc:
        await update.message.reply_text(f"Fear & Greed alınamadı: {exc}")
        return
    from .formatting import format_fear_greed

    await update.message.reply_text(format_fear_greed(index), parse_mode=ParseMode.HTML)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    asset_type = "crypto"
    if context.args:
        try:
            asset_type = parse_asset_type(context.args[0])
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
    try:
        if asset_type == "crypto":
            result = await asyncio.to_thread(scan_crypto_movers, context.application.bot_data["binance"], 10)
        else:
            raw = os.getenv("BIST_UNIVERSE", "THYAO,ASELS,AKBNK,EREGL,TUPRS,BIMAS,SISE,TCELL,KOZAL,PGSUS")
            symbols = [item.strip().upper() for item in raw.split(",") if item.strip()]
            result = await asyncio.to_thread(scan_bist_symbols, context.application.bot_data["bist"], symbols, 10)
    except Exception:
        LOGGER.exception("Tarama başarısız")
        await update.message.reply_text("Tarama geçici olarak başarısız oldu; sağlayıcı limitini veya erişimi kontrol edin.")
        return
    await update.message.reply_text(format_movers(result, number), parse_mode=ParseMode.HTML)


async def daily_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    symbols = ["XU100", "XU030", "USDTRY", "EURTRY", "ALTIN"]
    items = []
    for symbol in symbols:
        try:
            item = await asyncio.to_thread(context.application.bot_data["macro"].get_daily_bar, symbol)
            items.append(item)
        except (MarketDataError, ValueError):
            LOGGER.info("Günlük özet için veri yok: %s", symbol)
    if not items:
        await update.message.reply_text("Günlük piyasa özeti alınamadı.")
        return
    await update.message.reply_text(format_daily_summary(items), parse_mode=ParseMode.HTML)


async def macro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    symbol = context.args[0] if context.args else "XU100"
    try:
        quote = await asyncio.to_thread(context.application.bot_data["macro"].get_quote, symbol)
    except (MarketDataError, ValueError) as exc:
        await update.message.reply_text(f"Endeks/kur verisi alınamadı: {exc}")
        return
    await update.message.reply_text(format_quote(quote), parse_mode=ParseMode.HTML)


async def kap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    try:
        disclosures = await asyncio.to_thread(context.application.bot_data["kap"].fetch_recent_disclosures, 20)
    except Exception:
        LOGGER.exception("KAP public sayfa gözlemi başarısız")
        await update.message.reply_text("KAP public sayfası şu anda okunamadı.")
        return
    from .kap import format_disclosures

    await update.message.reply_text(format_disclosures(disclosures), parse_mode=ParseMode.HTML)


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_quote(update, context, "stock")


async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_quote(update, context, "crypto")


async def alarm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    usage = (
        "Kullanım:\n"
        "<code>/alarm ekle hisse THYAO ust 350</code>\n"
        "<code>/alarm ekle kripto BTC degisim 5</code>\n"
        "<code>/alarm liste</code>\n"
        "<code>/alarm sil 12</code>"
    )
    if not context.args:
        await update.message.reply_text(usage, parse_mode=ParseMode.HTML)
        return

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    action = context.args[0].lower()
    if action == "liste":
        await update.message.reply_text(format_alarms(db.list_alarms(chat_id, active_only=True)), parse_mode=ParseMode.HTML)
        return
    if action == "sil" and len(context.args) == 2:
        try:
            alarm_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Alarm numarası tam sayı olmalı.")
            return
        removed = db.deactivate_alarm(alarm_id, chat_id=chat_id)
        await update.message.reply_text("Alarm kapatıldı." if removed else "Aktif alarm bulunamadı.")
        return
    if action != "ekle" or len(context.args) != 5:
        await update.message.reply_text(usage, parse_mode=ParseMode.HTML)
        return

    try:
        asset_type = parse_asset_type(context.args[1])
        symbol = canonical_symbol(asset_type, context.args[2])
        condition = parse_alarm_condition(context.args[3])
        target = parse_number(context.args[4])
        if target <= 0:
            raise ValueError("Eşik sıfırdan büyük olmalı")
        alarm_id = db.add_alarm(chat_id, asset_type, symbol, condition, target)
    except ValueError as exc:
        await update.message.reply_text(f"Alarm oluşturulamadı: {exc}")
        return

    condition_text = {"above": "üstü", "below": "altı", "change_pct": "mutlak değişim"}[condition]
    suffix = "%" if condition == "change_pct" else ""
    await update.message.reply_text(
        f"Alarm #{alarm_id} oluşturuldu: {symbol} için {condition_text} {target:g}{suffix}."
    )


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    db: Database = context.application.bot_data["db"]
    args = context.args
    if not args or args[0].lower() == "liste":
        await update.message.reply_text(format_watchlist(db.list_watches(chat_id)), parse_mode=ParseMode.HTML)
        return
    if len(args) != 3 or args[0].lower() not in {"ekle", "sil"}:
        await update.message.reply_text(
            "Kullanım: <code>/izleme ekle hisse THYAO</code> veya <code>/izleme sil kripto BTC</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        asset_type = parse_asset_type(args[1])
        symbol = canonical_symbol(asset_type, args[2])
    except ValueError as exc:
        await update.message.reply_text(f"İzleme işlemi başarısız: {exc}")
        return
    if args[0].lower() == "ekle":
        db.add_watch(chat_id, asset_type, symbol)
        await update.message.reply_text(f"{symbol} izleme listenize eklendi.")
    else:
        removed = db.remove_watch(chat_id, asset_type, symbol)
        await update.message.reply_text("İzleme listesinden çıkarıldı." if removed else "Kayıt bulunamadı.")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    db: Database = context.application.bot_data["db"]
    args = context.args
    if not args:
        positions = db.portfolio_positions(chat_id)
        current_quotes = await _fetch_position_quotes(context, positions)
        await update.message.reply_text(
            format_portfolio(positions, current_quotes),
            parse_mode=ParseMode.HTML,
        )
        return
    if len(args) != 5 or args[0].lower() not in {"al", "sat"}:
        await update.message.reply_text(
            "Kullanım: <code>/portfoy al hisse THYAO 10 300</code>\n"
            "Satış için ilk kelimeyi <code>sat</code> yapın.",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        side = "buy" if args[0].lower() == "al" else "sell"
        asset_type = parse_asset_type(args[1])
        symbol = canonical_symbol(asset_type, args[2])
        quantity = parse_number(args[3])
        price = parse_number(args[4])
        if quantity <= 0 or price < 0:
            raise ValueError("Miktar sıfırdan büyük, fiyat sıfır veya daha büyük olmalı")
        currency = "TRY" if asset_type == "stock" else "USDT"
        db.add_transaction(chat_id, asset_type, symbol, side, quantity, price, currency)
    except ValueError as exc:
        await update.message.reply_text(f"Portföy işlemi başarısız: {exc}")
        return
    await update.message.reply_text(f"Sanal portföye işlendi: {symbol}, {quantity:g} adet, {price:g} {currency}.")


async def _fetch_position_quotes(context: ContextTypes.DEFAULT_TYPE, positions: list[dict]) -> dict[tuple[str, str], object]:
    quotes: dict[tuple[str, str], object] = {}
    for position in positions:
        key = (position["asset_type"], position["symbol"])
        try:
            client = context.application.bot_data["bist" if position["asset_type"] == "stock" else "binance"]
            quotes[key] = await asyncio.to_thread(client.get_quote, position["symbol"])
        except Exception:
            LOGGER.warning("Portföy fiyatı alınamadı: %s", key)
    return quotes


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline menü seçimlerini işler."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    key = (query.data or "").split(":", maxsplit=1)[-1]

    if key == "home":
        await query.edit_message_text(
            "<b>Nexa ana menüsü</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
        return
    if key == "help":
        await query.edit_message_text(
            HELP_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(),
        )
        return

    label = MENU_LABELS.get(key, "Nexa")
    await query.edit_message_text(
        f"<b>{label}</b>\n\nBu bölümde komutları kullanabilirsiniz.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.error("Telegram güncellemesi işlenirken hata oluştu", exc_info=context.error)


def register_handlers(application: Application, db: Database) -> None:
    application.bot_data["db"] = db
    application.bot_data["bist"] = YahooBistClient()
    application.bot_data["macro"] = YahooMacroClient()
    application.bot_data["binance"] = BinanceClient()
    application.bot_data["coingecko"] = CoinGeckoClient()
    application.bot_data["alternative"] = AlternativeClient()
    application.bot_data["kap"] = KAPPublicClient()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["yardim", "help"], help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler(["hisse", "stock"], stock_command))
    application.add_handler(CommandHandler(["kripto", "crypto"], crypto_command))
    application.add_handler(CommandHandler(["teknik", "analiz"], technical_command))
    application.add_handler(CommandHandler(["grafik", "chart"], chart_command))
    application.add_handler(CommandHandler(["temel", "fundamentals"], fundamentals_command))
    application.add_handler(CommandHandler(["piyasa", "market"], crypto_market_command))
    application.add_handler(CommandHandler(["endeks", "kur", "makro"], macro_command))
    application.add_handler(CommandHandler(["ozet", "gunluk"], daily_summary_command))
    application.add_handler(CommandHandler(["fng", "korku"], fear_greed_command))
    application.add_handler(CommandHandler(["tara", "tarama"], scan_command))
    application.add_handler(CommandHandler(["kap", "haber"], kap_command))
    application.add_handler(CommandHandler(["alarm", "alarmlar"], alarm_command))
    application.add_handler(CommandHandler(["izleme", "watchlist"], watchlist_command))
    application.add_handler(CommandHandler(["portfoy", "portfolio"], portfolio_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    application.add_error_handler(error_handler)

    interval = max(30, int(os.getenv("ALARM_CHECK_INTERVAL_SECONDS", "60")))
    scheduler_enabled = os.getenv("ENABLE_INTERNAL_SCHEDULER", "true").strip().lower() in {"1", "true", "yes", "on"}
    if scheduler_enabled and application.job_queue is not None:
        application.job_queue.run_repeating(
            check_active_alarms,
            interval=interval,
            first=20,
            name="nexa-alarm-checker",
        )
        application.job_queue.run_repeating(
            check_kap_updates,
            interval=max(300, interval),
            first=45,
            name="nexa-kap-checker",
        )


def build_application(settings: Settings, db: Database | None = None) -> Application:
    """Test edilebilir bir Telegram Application nesnesi döndürür."""
    settings.validate()
    database = db or Database(settings.database_path)
    database.initialize()
    application = ApplicationBuilder().token(settings.telegram_bot_token).build()
    register_handlers(application, database)
    return application


def run_polling(settings: Settings) -> None:
    """Yerel geliştirme için long polling ile botu başlatır."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = build_application(settings)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    run_polling(Settings.from_env())
