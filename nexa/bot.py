"""Nexa Telegram botu."""

from __future__ import annotations

import asyncio
import logging
import os

import pandas as pd
from pathlib import Path
from typing import Any, Callable

from telegram import BotCommand, BotCommandScopeChat, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
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
from .kap import KAPPublicClient
from .market_profile import calculate_volume_profile
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
from .scanner import scan_bist_symbols, scan_crypto_movers
from .scheduler import check_active_alarms, check_kap_updates
from .technical_analysis import calculate_indicators
from .texts import MENU_LABELS
from .visual_cards import (
    save_alarms_card,
    save_daily_summary_card,
    save_depth_card,
    save_fear_greed_card,
    save_fundamentals_card,
    save_global_market_card,
    save_help_card,
    save_kap_card,
    save_movers_card,
    save_notice_card,
    save_portfolio_card,
    save_quote_card,
    save_start_card,
    save_technical_card,
    save_watchlist_card,
    save_volume_profile_card,
)

LOGGER = logging.getLogger(__name__)


ROOT_COMMANDS = [
    BotCommand("start", "NEXA başlangıç menüsü"),
    BotCommand("yardim", "BIST ve kripto rehberi"),
    BotCommand("hisse", "BIST tarafına geç"),
    BotCommand("kripto", "Kripto tarafına geç"),
]

BIST_COMMANDS = [
    *ROOT_COMMANDS[:2],
    BotCommand("hisse", "BIST hisse piyasa kartı"),
    BotCommand("teknik", "BIST RSI, MACD ve seviyeler"),
    BotCommand("grafik", "BIST mum fiyat grafiği"),
    BotCommand("temel", "BIST F/K, PD/DD, temettü"),
    BotCommand("endeks", "BIST endeks, döviz, altın"),
    BotCommand("ozet", "BIST günlük piyasa özeti"),
    BotCommand("derinlik", "BIST derinlik durumu"),
    BotCommand("tara", "BIST yükselen ve düşenler"),
    BotCommand("kap", "BIST public KAP gözlemi"),
    BotCommand("alarm", "BIST fiyat alarmı"),
    BotCommand("izleme", "BIST izleme listesi"),
    BotCommand("portfoy", "Sanal portföy özeti"),
]

CRYPTO_COMMANDS = [
    *ROOT_COMMANDS[:2],
    BotCommand("kripto", "Kripto fiyat kartı"),
    BotCommand("teknik", "Kripto RSI, MACD ve seviyeler"),
    BotCommand("grafik", "Kripto mum fiyat grafiği"),
    BotCommand("piyasa", "Kripto piyasa görünümü"),
    BotCommand("fng", "Fear & Greed göstergesi"),
    BotCommand("derinlik", "Kripto emir defteri"),
    BotCommand("tara", "Kripto yükselen ve düşenler"),
    BotCommand("alarm", "Kripto fiyat alarmı"),
    BotCommand("izleme", "Kripto izleme listesi"),
    BotCommand("portfoy", "Sanal portföy özeti"),
]

# Geriye dönük import/test uyumluluğu; global Telegram menüsü ROOT_COMMANDS kullanır.
NEXA_COMMANDS = ROOT_COMMANDS


MENU_GUIDES = {
    "stock": {
        "title": "BIST HİSSE",
        "message": "Bir hisse kodu yazarak başlayın. Komutu mesaj alanına gönderdiğinizde NEXA fiyat ve analiz kartını hazırlar.",
        "commands": [
            ("/hisse THYAO", "Fiyat + mum kartı"),
            ("/teknik hisse THYAO", "RSI, MACD, seviyeler"),
            ("/temel THYAO", "F/K, PD/DD, temettü"),
            ("/grafik hisse THYAO", "Detaylı fiyat grafiği"),
            ("/derinlik THYAO", "BIST derinlik durumu"),
            ("/endeks XU100", "BIST 100 görünümü"),
        ],
        "accent": "#57E389",
    },
    "crypto": {
        "title": "KRİPTO",
        "message": "Coin sembolünü yazarak başlayın. BTC, ETH gibi sembollerle fiyat, mum grafik ve piyasa görünümünü açabilirsiniz.",
        "commands": [
            ("/kripto BTC", "Fiyat + mum kartı"),
            ("/teknik kripto BTC", "RSI, MACD, seviyeler"),
            ("/grafik kripto BTC", "Detaylı fiyat grafiği"),
            ("/derinlik BTC", "Gerçek emir defteri"),
            ("/tara kripto", "Yükselen / düşenler"),
            ("/fng", "Fear & Greed göstergesi"),
        ],
        "accent": "#F7A34D",
    },
    "portfolio": {
        "title": "PORTFÖY",
        "message": "Önce işlem kaydedin, ardından /portfoy komutuyla sanal portföyünüzün güncel değerini ve kâr/zararını görün.",
        "commands": [
            ("/portfoy", "Portföy özeti"),
            ("/portfoy al hisse THYAO 10 300", "Alım kaydı"),
            ("/portfoy sat kripto BTC 0.1 65000", "Satış kaydı"),
            ("/portfoy", "Güncel değer ve K/Z"),
        ],
        "accent": "#F3C76B",
    },
    "alerts": {
        "title": "ALARMLAR",
        "message": "Bir fiyat veya yüzde değişim eşiği belirleyin. Alarm aktif olduğunda NEXA kontrol döngüsünde size bildirim gönderir.",
        "commands": [
            ("/alarm ekle hisse THYAO ust 350", "Fiyat üstü alarmı"),
            ("/alarm ekle kripto BTC degisim 5", "%5 değişim alarmı"),
            ("/alarm liste", "Aktif alarmları gör"),
            ("/alarm sil 12", "Alarmı pasifleştir"),
        ],
        "accent": "#F3C76B",
    },
    "watchlist": {
        "title": "İZLEME LİSTESİ",
        "message": "Takip etmek istediğiniz varlığı ekleyin. Listeyi tek komutla görüntüleyebilir veya sembolü silebilirsiniz.",
        "commands": [
            ("/izleme liste", "Listenizi görüntüle"),
            ("/izleme ekle hisse THYAO", "BIST varlığı ekle"),
            ("/izleme sil hisse THYAO", "BIST varlığı kaldır"),
        ],
        "accent": "#5BD7F4",
    },
}


DOMAIN_SHARED_GUIDES = {
    "bist": {
        "portfolio": {
            "title": "PORTFÖY · BIST",
            "message": "BIST işleminizi sanal olarak kaydedin. Ardından /portfoy ile güncel değer ve kâr/zarar özetini görün.",
            "commands": [
                ("/portfoy", "BIST portföy özeti"),
                ("/portfoy al hisse THYAO 10 300", "BIST alım kaydı"),
                ("/portfoy sat hisse THYAO 5 320", "BIST satış kaydı"),
            ],
            "accent": "#F3C76B",
        },
        "alerts": {
            "title": "ALARMLAR · BIST",
            "message": "BIST hisseniz için fiyat eşiği belirleyin. Aktif alarmı listeleyebilir veya numarasıyla silebilirsiniz.",
            "commands": [
                ("/alarm ekle hisse THYAO ust 350", "BIST fiyat üstü alarmı"),
                ("/alarm liste", "Aktif BIST alarmları"),
                ("/alarm sil 12", "Alarmı pasifleştir"),
            ],
            "accent": "#F3C76B",
        },
        "watchlist": {
            "title": "İZLEME LİSTESİ · BIST",
            "message": "Takip etmek istediğiniz BIST hisselerini ekleyin; listeyi açın veya sembolü kaldırın.",
            "commands": [
                ("/izleme ekle hisse THYAO", "BIST hissesi ekle"),
                ("/izleme liste", "BIST listenizi gör"),
                ("/izleme sil hisse THYAO", "BIST hissesini kaldır"),
            ],
            "accent": "#5BD7F4",
        },
    },
    "crypto": {
        "portfolio": {
            "title": "PORTFÖY · KRİPTO",
            "message": "Kripto işleminizi sanal olarak kaydedin. Ardından /portfoy ile güncel değer ve kâr/zarar özetini görün.",
            "commands": [
                ("/portfoy", "Kripto portföy özeti"),
                ("/portfoy al kripto BTC 0.1 65000", "Kripto alım kaydı"),
                ("/portfoy sat kripto BTC 0.05 70000", "Kripto satış kaydı"),
            ],
            "accent": "#F3C76B",
        },
        "alerts": {
            "title": "ALARMLAR · KRİPTO",
            "message": "Kripto varlığınız için fiyat veya yüzde değişim eşiği belirleyin. Aktif alarmı listeleyebilir veya silebilirsiniz.",
            "commands": [
                ("/alarm ekle kripto BTC ust 70000", "Kripto fiyat alarmı"),
                ("/alarm ekle kripto BTC degisim 5", "%5 değişim alarmı"),
                ("/alarm liste", "Aktif kripto alarmları"),
            ],
            "accent": "#F3C76B",
        },
        "watchlist": {
            "title": "İZLEME LİSTESİ · KRİPTO",
            "message": "Takip etmek istediğiniz coinleri ekleyin; listeyi açın veya sembolü kaldırın.",
            "commands": [
                ("/izleme ekle kripto BTC", "Kripto ekle"),
                ("/izleme liste", "Kripto listenizi gör"),
                ("/izleme sil kripto BTC", "Kriptoyu kaldır"),
            ],
            "accent": "#5BD7F4",
        },
    },
}


def active_menu_guide(key: str, domain: str | None = None) -> dict[str, object] | None:
    if domain in DOMAIN_SHARED_GUIDES and key in DOMAIN_SHARED_GUIDES[domain]:
        return DOMAIN_SHARED_GUIDES[domain][key]
    return MENU_GUIDES.get(key)


def help_commands_for_domain(domain: str | None) -> list[tuple[str, str]]:
    if domain == "bist":
        return [
            ("/hisse THYAO", "BIST fiyat ve mum kartı"),
            ("/teknik hisse THYAO", "BIST RSI, MACD, seviyeler"),
            ("/grafik hisse THYAO", "BIST detaylı grafik"),
            ("/temel THYAO", "BIST F/K, PD/DD, temettü"),
            ("/endeks XU100", "BIST endeks görünümü"),
            ("/derinlik THYAO", "BIST Level 2 durumu"),
            ("/alarm ekle hisse THYAO ust 350", "BIST fiyat alarmı"),
            ("/izleme ekle hisse THYAO", "BIST izleme listesine ekle"),
            ("/portfoy", "BIST portföy özeti"),
        ]
    if domain == "crypto":
        return [
            ("/kripto BTC", "Kripto fiyat ve mum kartı"),
            ("/teknik kripto BTC", "Kripto RSI, MACD, seviyeler"),
            ("/grafik kripto BTC", "Kripto detaylı grafik"),
            ("/piyasa", "Kripto piyasa görünümü"),
            ("/fng", "Fear & Greed göstergesi"),
            ("/derinlik BTC", "Gerçek kripto emir defteri"),
            ("/alarm ekle kripto BTC ust 70000", "Kripto fiyat alarmı"),
            ("/izleme ekle kripto BTC", "Kripto izleme listesine ekle"),
            ("/portfoy", "Kripto portföy özeti"),
        ]
    return HELP_COMMANDS


async def _activate_domain(context: ContextTypes.DEFAULT_TYPE, chat_id: int | None, domain: str | None) -> None:
    """Kullanıcının bulunduğu BIST/KRİPTO alanına göre chat-scope menüyü senkronize eder."""
    if domain not in {"bist", "crypto"} or chat_id is None:
        return
    if context.user_data.get("nexa_domain") == domain:
        return
    context.user_data["nexa_domain"] = domain
    await configure_command_menu(context.bot, chat_id=chat_id, domain=domain)


async def configure_command_menu(bot: Any, chat_id: int | None = None, domain: str | None = None) -> bool:
    """Global veya chat-scope BIST/KRİPTO Telegram komut menüsünü kurar."""
    commands = BIST_COMMANDS if domain == "bist" else CRYPTO_COMMANDS if domain == "crypto" else ROOT_COMMANDS
    scope = BotCommandScopeChat(chat_id=chat_id) if chat_id is not None else None
    try:
        if scope is None:
            await bot.set_my_commands(commands)
        else:
            await bot.set_my_commands(commands, scope=scope)
        scope_label = f"chat={chat_id}, domain={domain or 'root'}" if chat_id is not None else "global root"
        LOGGER.info("Telegram komut menüsü ayarlandı: %d komut (%s)", len(commands), scope_label)
        return True
    except TelegramError:
        LOGGER.warning("Telegram komut menüsü ayarlanamadı", exc_info=True)
        return False


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


def command_copy_keyboard(commands: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Komutları Telegram’da tek dokunuşla panoya kopyalanabilir butonlara çevirir."""
    rows = []
    for command, _ in commands:
        rows.append([InlineKeyboardButton(command, copy_text=CopyTextButton(command))])
    return InlineKeyboardMarkup(rows)


async def _reply_command_list(target: Any, title: str, commands: list[tuple[str, str]]) -> None:
    """Görsel kartın altında komutları yazılı ve kopyalanabilir biçimde gönderir."""
    lines = [f"NEXA | {title} KOMUTLARI", "Komutu kopyalayıp mesaj alanına yapıştırın ve gönderin.", ""]
    lines.extend(f"{command} — {description}" for command, description in commands)
    await target.reply_text("\n".join(lines), reply_markup=command_copy_keyboard(commands))


HELP_COMMANDS = [
    ("/hisse THYAO", "BIST fiyat ve mum kartı"),
    ("/kripto BTC", "Kripto fiyat ve mum kartı"),
    ("/teknik hisse THYAO", "RSI, MACD ve seviyeler"),
    ("/grafik kripto BTC", "Detaylı fiyat grafiği"),
    ("/temel THYAO", "F/K, PD/DD ve temettü"),
    ("/endeks XU100", "BIST 100 görünümü"),
    ("/ozet", "Günlük piyasa özeti"),
    ("/piyasa", "Kripto piyasa görünümü"),
    ("/fng", "Fear & Greed göstergesi"),
    ("/tara kripto", "Yükselen ve düşenler"),
    ("/kap", "Public KAP gözlemi"),
    ("/alarm liste", "Aktif alarmlar"),
    ("/izleme liste", "İzleme listesi"),
    ("/portfoy", "Sanal portföy özeti"),
]


def guide_keyboard(key: str) -> InlineKeyboardMarkup:
    """Bölüm kartında ilgili bölümlere ve ana menüye hızlı geçiş sağlar."""
    related = {
        "stock": [],
        "crypto": [],
        "portfolio": [("Alarmlar", "alerts"), ("İzleme Listesi", "watchlist")],
        "alerts": [("Portföy", "portfolio"), ("İzleme Listesi", "watchlist")],
        "watchlist": [("Portföy", "portfolio"), ("Alarmlar", "alerts")],
    }.get(key, [])
    rows = []
    if related:
        rows.append([InlineKeyboardButton(label, callback_data=f"menu:{target}") for label, target in related])
    rows.append([InlineKeyboardButton("Yardım", callback_data="menu:help"), InlineKeyboardButton("Ana menü", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


async def _reply_card(
    target: Any,
    builder: Callable[[Path], Path],
    caption: str = "NEXA | Ücretsiz veri katmanı",
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Kartı sohbet bazlı geçici dizinde üretip Telegram fotoğrafı olarak gönderir."""
    chat_id = getattr(target, "chat_id", None) or getattr(getattr(target, "chat", None), "id", "unknown")
    output_dir = Path("/tmp/nexa_cards") / str(chat_id)
    path = await asyncio.to_thread(builder, output_dir)
    with path.open("rb") as photo:
        await target.reply_photo(photo=photo, caption=caption, reply_markup=reply_markup)


async def _reply_notice(
    update: Update,
    title: str,
    message: str,
    slug: str = "notice_card",
    accent: str = "#57E389",
) -> None:
    if update.message:
        await _reply_card(
            update.message,
            lambda output_dir: save_notice_card(title, message, output_dir, slug=slug, accent=accent),
            caption="NEXA",
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
    context.user_data["nexa_domain"] = None
    await configure_command_menu(context.bot, chat_id=update.effective_chat.id)
    user = update.effective_user
    db.upsert_user(
        chat_id=update.effective_chat.id,
        username=user.username,
        first_name=user.first_name,
    )
    name = user.first_name or user.username or "kullanıcı"
    await _reply_card(
        update.message,
        lambda output_dir: save_start_card(name, output_dir),
        caption="NEXA | Borsa & Kripto",
        reply_markup=main_menu(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await _reply_card(
            update.message,
            save_help_card,
            caption="NEXA | Komut rehberi",
            reply_markup=main_menu(),
        )
        await _reply_command_list(update.message, "YARDIM", help_commands_for_domain(context.user_data.get("nexa_domain")))


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        context.user_data["nexa_domain"] = None
        if update.effective_chat:
            await configure_command_menu(context.bot, chat_id=update.effective_chat.id)
        name = update.effective_user.first_name if update.effective_user else "kullanıcı"
        await _reply_card(
            update.message,
            lambda output_dir: save_start_card(name or "kullanıcı", output_dir),
            caption="NEXA | Ana menü",
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
        await _reply_notice(
            update,
            "KOMUT KULLANIMI",
            f"Kullanım: /{command} {example}",
            slug=f"usage_{command}",
            accent="#F3C76B",
        )
        return

    symbol = context.args[0].upper()
    chat_id = update.effective_chat.id if update.effective_chat else None
    await _activate_domain(context, chat_id, "bist" if asset_type == "stock" else "crypto")
    try:
        if asset_type == "stock":
            client = context.application.bot_data["bist"]
        else:
            client = context.application.bot_data["binance"]
        quote = await asyncio.to_thread(client.get_quote, symbol)
    except (MarketDataError, ValueError) as exc:
        await _reply_notice(
            update,
            "VERİ ALINAMADI",
            f"{symbol} için veri alınamadı. {exc}",
            slug=f"quote_error_{asset_type}",
            accent="#FF747D",
        )
        return
    except Exception:
        LOGGER.exception("%s sorgusunda beklenmeyen hata: %s", asset_type, symbol)
        await _reply_notice(
            update,
            "GEÇİCİ SAĞLAYICI HATASI",
            "Veri sağlayıcısı şu anda yanıt vermedi. Lütfen biraz sonra tekrar deneyin.",
            slug=f"provider_error_{asset_type}",
            accent="#FF747D",
        )
        return

    snapshot: dict[str, object] | None = None
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
    else:
        try:
            fundamentals = await asyncio.to_thread(client.get_fundamentals, symbol)
            snapshot = {
                "name": fundamentals.get("name"),
                "market_cap": fundamentals.get("market_cap"),
            }
        except Exception:
            LOGGER.info("Hisse piyasa değeri alınamadı: %s", quote.symbol)
    ohlcv = None
    try:
        if asset_type == "stock":
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "1y", "1d")
        else:
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "1d", 60)
    except Exception:
        LOGGER.error("Piyasa kartı OHLCV verisi alınamadı: %s (%s)", quote.symbol, asset_type, exc_info=True)

    await _reply_card(
        update.message,
        lambda output_dir: save_quote_card(quote, output_dir, snapshot=snapshot, ohlcv=ohlcv),
        caption=f"NEXA | {quote.symbol} piyasa kartı",
    )


async def technical_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 2:
        await _reply_notice(update, "KOMUT KULLANIMI", "Kullanım: /teknik hisse THYAO veya /teknik kripto BTC", slug="usage_teknik", accent="#F3C76B")
        return
    try:
        asset_type = parse_asset_type(context.args[0])
        await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist" if asset_type == "stock" else "crypto")
        symbol = canonical_symbol(asset_type, context.args[1])
        client = context.application.bot_data["bist" if asset_type == "stock" else "binance"]
        if asset_type == "stock":
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "6mo", "1d")
        else:
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "1d", 180)
        snapshot = calculate_indicators(ohlcv)
    except (MarketDataError, ValueError) as exc:
        await _reply_notice(update, "TEKNİK VERİ ALINAMADI", str(exc), slug="technical_error", accent="#FF747D")
        return
    closes = ohlcv.get("close", pd.Series(dtype=float)).dropna()
    last_price = float(closes.iloc[-1]) if not closes.empty else None
    await _reply_card(
        update.message,
        lambda output_dir: save_technical_card(symbol, snapshot, output_dir, last_price=last_price, source="NEXA ücretsiz veri katmanı"),
        caption=f"NEXA | {symbol} teknik analiz",
    )


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 2:
        await _reply_notice(update, "KOMUT KULLANIMI", "Kullanım: /grafik hisse THYAO veya /grafik kripto BTC", slug="usage_grafik", accent="#F3C76B")
        return
    try:
        asset_type = parse_asset_type(context.args[0])
        await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist" if asset_type == "stock" else "crypto")
        symbol = canonical_symbol(asset_type, context.args[1])
        client = context.application.bot_data["bist" if asset_type == "stock" else "binance"]
        if asset_type == "stock":
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "6mo", "1d")
        else:
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "1d", 180)
        chart_path = await asyncio.to_thread(
            save_price_chart,
            ohlcv,
            f"NEXA | {symbol} fiyat grafiği",
            Path("/tmp") / "nexa_charts" / str(update.effective_chat.id if update.effective_chat else "unknown"),
        )
    except (MarketDataError, ValueError) as exc:
        await _reply_notice(update, "GRAFİK ÜRETİLEMEDİ", str(exc), slug="chart_error", accent="#FF747D")
        return
    with chart_path.open("rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=f"NEXA | {symbol} fiyat grafiği",
        )


async def fundamentals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if len(context.args) != 1:
        await _reply_notice(update, "KOMUT KULLANIMI", "Kullanım: /temel THYAO", slug="usage_temel", accent="#F3C76B")
        return
    try:
        await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist")
        symbol = canonical_symbol("stock", context.args[0])
        data = await asyncio.to_thread(context.application.bot_data["bist"].get_fundamentals, symbol)
    except (MarketDataError, ValueError) as exc:
        await _reply_notice(update, "TEMEL VERİ ALINAMADI", str(exc), slug="fundamentals_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_fundamentals_card(data, output_dir),
        caption=f"NEXA | {data.get('symbol', 'BIST')} temel oranlar",
    )


async def crypto_market_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "crypto")
    try:
        data = await asyncio.to_thread(context.application.bot_data["coingecko"].get_global)
    except MarketDataError as exc:
        await _reply_notice(update, "PİYASA ÖZETİ ALINAMADI", str(exc), slug="market_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_global_market_card(data, output_dir),
        caption="NEXA | Kripto piyasa özeti",
    )


async def fear_greed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "crypto")
    try:
        index = await asyncio.to_thread(context.application.bot_data["alternative"].get_fear_greed)
    except MarketDataError as exc:
        await _reply_notice(update, "FEAR & GREED ALINAMADI", str(exc), slug="fng_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_fear_greed_card(index, output_dir),
        caption="NEXA | Fear & Greed",
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    asset_type = context.user_data.get("nexa_domain")
    if context.args:
        try:
            asset_type = parse_asset_type(context.args[0])
        except ValueError as exc:
            await _reply_notice(update, "KOMUT KULLANIMI", str(exc), slug="scan_usage", accent="#F3C76B")
            return
    if asset_type not in {"stock", "crypto"}:
        await _reply_notice(update, "TARAMA KULLANIMI", "/tara hisse veya /tara kripto yazın; seçtiğiniz alana göre liste hazırlanır.", slug="scan_usage", accent="#F3C76B")
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, asset_type)
    try:
        if asset_type == "crypto":
            result = await asyncio.to_thread(scan_crypto_movers, context.application.bot_data["binance"], 10)
        else:
            raw = os.getenv("BIST_UNIVERSE", "THYAO,ASELS,AKBNK,EREGL,TUPRS,BIMAS,SISE,TCELL,KOZAL,PGSUS")
            symbols = [item.strip().upper() for item in raw.split(",") if item.strip()]
            result = await asyncio.to_thread(scan_bist_symbols, context.application.bot_data["bist"], symbols, 10)
    except Exception:
        LOGGER.exception("Tarama başarısız")
        await _reply_notice(update, "TARAMA BAŞARISIZ", "Tarama geçici olarak başarısız oldu; sağlayıcı limitini veya erişimi kontrol edin.", slug="scan_error", accent="#FF747D")
        return
    label = "KRİPTO" if asset_type == "crypto" else "BIST"
    await _reply_card(
        update.message,
        lambda output_dir: save_movers_card(result, output_dir, asset_label=label),
        caption=f"NEXA | {label} tarama",
    )


async def daily_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist")
    symbols = ["XU100", "XU030", "USDTRY", "EURTRY", "ALTIN"]
    items = []
    for symbol in symbols:
        try:
            item = await asyncio.to_thread(context.application.bot_data["macro"].get_daily_bar, symbol)
            items.append(item)
        except (MarketDataError, ValueError):
            LOGGER.info("Günlük özet için veri yok: %s", symbol)
    if not items:
        await _reply_notice(update, "GÜNLÜK ÖZET ALINAMADI", "Piyasa verileri şu anda okunamadı; lütfen daha sonra tekrar deneyin.", slug="summary_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_daily_summary_card(items, output_dir),
        caption="NEXA | Günlük piyasa özeti",
    )


async def macro_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist")
    symbol = context.args[0] if context.args else "XU100"
    try:
        quote = await asyncio.to_thread(context.application.bot_data["macro"].get_quote, symbol)
    except (MarketDataError, ValueError) as exc:
        await _reply_notice(update, "MAKRO VERİ ALINAMADI", str(exc), slug="macro_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_quote_card(quote, output_dir),
        caption=f"NEXA | {quote.symbol} piyasa kartı",
    )


async def kap_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist")
    try:
        disclosures = await asyncio.to_thread(context.application.bot_data["kap"].fetch_recent_disclosures, 20)
    except Exception:
        LOGGER.exception("KAP public sayfa gözlemi başarısız")
        await _reply_notice(update, "KAP OKUNAMADI", "KAP public sayfası şu anda okunamadı; daha sonra tekrar deneyin.", slug="kap_error", accent="#FF747D")
        return
    await _reply_card(
        update.message,
        lambda output_dir: save_kap_card(disclosures, output_dir),
        caption="NEXA | KAP bildirimleri",
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_quote(update, context, "stock")


async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_quote(update, context, "crypto")


async def depth_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """BIST’te açık erişim sınırını, kriptoda gerçek Binance kademelerini gösterir."""
    if not update.message:
        return
    domain = context.user_data.get("nexa_domain")
    asset_type = "stock" if domain == "bist" else "crypto" if domain == "crypto" else None
    args = context.args
    if args and args[0].lower() in {"hisse", "kripto"}:
        asset_type = "stock" if args[0].lower() == "hisse" else "crypto"
        args = args[1:]
    if asset_type is None:
        await _reply_notice(update, "DERİNLİK KULLANIMI", "/derinlik THYAO (BIST menüsünde) veya /derinlik BTC (Kripto menüsünde)", slug="depth_usage", accent="#F3C76B")
        return
    symbol = (args[0] if args else ("THYAO" if asset_type == "stock" else "BTC")).upper()
    await _activate_domain(context, update.effective_chat.id if update.effective_chat else None, "bist" if asset_type == "stock" else "crypto")
    client = context.application.bot_data["bist" if asset_type == "stock" else "binance"]
    try:
        quote = await asyncio.to_thread(client.get_quote, symbol)
        if asset_type == "stock":
            ohlcv = await asyncio.to_thread(client.get_ohlcv, symbol, "3mo", "1d")
            profile = calculate_volume_profile(ohlcv, bars=30, zones=5)
            await _reply_card(
                update.message,
                lambda output_dir: save_volume_profile_card(quote.symbol, quote, profile, output_dir),
                caption=f"NEXA | {quote.symbol} BIST hacim dağılımı",
            )
            return
        depth = await asyncio.to_thread(client.get_depth, symbol, 10)
        await _reply_card(
            update.message,
            lambda output_dir: save_depth_card(quote.symbol, "crypto", output_dir, depth=depth, quote=quote),
            caption=f"NEXA | {quote.symbol} kripto derinliği",
        )
    except (MarketDataError, ValueError) as exc:
        LOGGER.error("Derinlik verisi alınamadı: %s %s", asset_type, symbol, exc_info=True)
        await _reply_notice(update, "DERİNLİK ALINAMADI", str(exc), slug=f"depth_error_{asset_type}", accent="#FF747D")


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
        await _reply_notice(update, "ALARM KULLANIMI", "/alarm ekle hisse THYAO ust 350\n/alarm liste\n/alarm sil 12", slug="alarm_usage", accent="#F3C76B")
        return

    db: Database = context.application.bot_data["db"]
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    action = context.args[0].lower()
    if action == "liste":
        items = db.list_alarms(chat_id, active_only=True)
        await _reply_card(update.message, lambda output_dir: save_alarms_card(items, output_dir), caption="NEXA | Aktif alarmlar")
        return
    if action == "sil" and len(context.args) == 2:
        try:
            alarm_id = int(context.args[1])
        except ValueError:
            await _reply_notice(update, "ALARM SİLİNEMEDİ", "Alarm numarası tam sayı olmalı.", slug="alarm_delete_error", accent="#FF747D")
            return
        db.deactivate_alarm(alarm_id, chat_id=chat_id)
        items = db.list_alarms(chat_id, active_only=True)
        await _reply_card(update.message, lambda output_dir: save_alarms_card(items, output_dir), caption="NEXA | Alarm listesi")
        return
    if action != "ekle" or len(context.args) != 5:
        await _reply_notice(update, "ALARM KULLANIMI", "/alarm ekle hisse THYAO ust 350 veya /alarm ekle kripto BTC degisim 5", slug="alarm_usage", accent="#F3C76B")
        return

    try:
        asset_type = parse_asset_type(context.args[1])
        await _activate_domain(context, chat_id, asset_type)
        symbol = canonical_symbol(asset_type, context.args[2])
        condition = parse_alarm_condition(context.args[3])
        target = parse_number(context.args[4])
        if target <= 0:
            raise ValueError("Eşik sıfırdan büyük olmalı")
        alarm_id = db.add_alarm(chat_id, asset_type, symbol, condition, target)
    except ValueError as exc:
        await _reply_notice(update, "ALARM OLUŞTURULAMADI", str(exc), slug="alarm_create_error", accent="#FF747D")
        return

    items = db.list_alarms(chat_id, active_only=True)
    await _reply_card(update.message, lambda output_dir: save_alarms_card(items, output_dir), caption=f"NEXA | Alarm #{alarm_id} oluşturuldu")


async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    db: Database = context.application.bot_data["db"]
    args = context.args
    if not args or args[0].lower() == "liste":
        items = db.list_watches(chat_id)
        await _reply_card(update.message, lambda output_dir: save_watchlist_card(items, output_dir), caption="NEXA | İzleme listesi")
        return
    if len(args) != 3 or args[0].lower() not in {"ekle", "sil"}:
        await _reply_notice(update, "İZLEME KULLANIMI", "/izleme ekle hisse THYAO veya /izleme sil kripto BTC", slug="watch_usage", accent="#F3C76B")
        return
    try:
        asset_type = parse_asset_type(args[1])
        await _activate_domain(context, chat_id, asset_type)
        symbol = canonical_symbol(asset_type, args[2])
    except ValueError as exc:
        await _reply_notice(update, "İZLEME İŞLEMİ BAŞARISIZ", str(exc), slug="watch_error", accent="#FF747D")
        return
    if args[0].lower() == "ekle":
        db.add_watch(chat_id, asset_type, symbol)
    else:
        db.remove_watch(chat_id, asset_type, symbol)
    items = db.list_watches(chat_id)
    await _reply_card(update.message, lambda output_dir: save_watchlist_card(items, output_dir), caption=f"NEXA | {symbol} izleme listesi")


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
        await _reply_card(
            update.message,
            lambda output_dir: save_portfolio_card(positions, current_quotes, output_dir),
            caption="NEXA | Sanal portföy",
        )
        return
    if len(args) != 5 or args[0].lower() not in {"al", "sat"}:
        await _reply_notice(update, "PORTFÖY KULLANIMI", "/portfoy al hisse THYAO 10 300\nSatış için ilk kelimeyi sat yapın.", slug="portfolio_usage", accent="#F3C76B")
        return
    try:
        side = "buy" if args[0].lower() == "al" else "sell"
        asset_type = parse_asset_type(args[1])
        await _activate_domain(context, chat_id, asset_type)
        symbol = canonical_symbol(asset_type, args[2])
        quantity = parse_number(args[3])
        price = parse_number(args[4])
        if quantity <= 0 or price < 0:
            raise ValueError("Miktar sıfırdan büyük, fiyat sıfır veya daha büyük olmalı")
        currency = "TRY" if asset_type == "stock" else "USDT"
        db.add_transaction(chat_id, asset_type, symbol, side, quantity, price, currency)
    except ValueError as exc:
        await _reply_notice(update, "PORTFÖY İŞLEMİ BAŞARISIZ", str(exc), slug="portfolio_error", accent="#FF747D")
        return
    positions = db.portfolio_positions(chat_id)
    current_quotes = await _fetch_position_quotes(context, positions)
    await _reply_card(
        update.message,
        lambda output_dir: save_portfolio_card(positions, current_quotes, output_dir),
        caption=f"NEXA | {symbol} portföye işlendi",
    )


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

    if not query.message:
        return
    if key == "home":
        if update.effective_chat:
            await configure_command_menu(context.bot, chat_id=update.effective_chat.id)
            context.user_data["nexa_domain"] = None
        name = update.effective_user.first_name if update.effective_user else "kullanıcı"
        await _reply_card(
            query.message,
            lambda output_dir: save_start_card(name or "kullanıcı", output_dir),
            caption="NEXA | Ana menü",
            reply_markup=main_menu(),
        )
        return
    if key == "help":
        await _reply_card(
            query.message,
            save_help_card,
            caption="NEXA | Komut rehberi",
            reply_markup=back_keyboard(),
        )
        await _reply_command_list(query.message, "YARDIM", help_commands_for_domain(context.user_data.get("nexa_domain")))
        return

    guide = active_menu_guide(key, context.user_data.get("nexa_domain"))
    if guide:
        domain = "bist" if key == "stock" else "crypto" if key == "crypto" else None
        if domain:
            context.user_data["nexa_domain"] = domain
            if update.effective_chat:
                await configure_command_menu(context.bot, chat_id=update.effective_chat.id, domain=domain)
        await _reply_card(
            query.message,
            lambda output_dir: save_notice_card(
                guide["title"],
                guide["message"],
                output_dir,
                slug=f"menu_{key}",
                accent=guide["accent"],
                commands=guide["commands"],
            ),
            caption=f"NEXA | {guide['title']}",
            reply_markup=guide_keyboard(key),
        )
        await _reply_command_list(query.message, guide["title"], guide["commands"])
        return

    label = MENU_LABELS.get(key, "NEXA")
    await _reply_card(
        query.message,
        lambda output_dir: save_notice_card(label.upper(), "/yardim ile tüm komutları ve örnek kullanımları görebilirsiniz.", output_dir, slug=f"menu_{key}"),
        caption=f"NEXA | {label}",
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
    application.add_handler(CommandHandler("derinlik", depth_command))
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
