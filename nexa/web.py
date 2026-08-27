"""Render webhook ve dış cron giriş noktası."""

from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update
from telegram.error import TelegramError

from .bot import build_application, configure_command_menu
from .config import Settings
from .scheduler import check_active_alarms, check_kap_updates

LOGGER = logging.getLogger(__name__)
settings = Settings.from_env()
application = None
telegram_ready = False
telegram_task: asyncio.Task[None] | None = None


async def _start_telegram_with_retry() -> None:
    """Telegram ağı geçici olarak timeout verirse web servisini düşürmeden tekrar dener."""
    global application, telegram_ready
    for attempt in range(1, 7):
        candidate = build_application(settings)
        try:
            await candidate.initialize()
            await candidate.start()
            await configure_command_menu(candidate.bot)
            if settings.app_base_url:
                webhook_url = f"{settings.app_base_url.rstrip('/')}/telegram/webhook"
                await candidate.bot.set_webhook(
                    url=webhook_url,
                    secret_token=settings.telegram_webhook_secret,
                    allowed_updates=Update.ALL_TYPES,
                )
                LOGGER.info("Telegram webhook ayarlandı: %s", webhook_url)
            application = candidate
            telegram_ready = True
            LOGGER.info("Telegram bot hazır")
            return
        except (TelegramError, TimeoutError, OSError) as exc:
            LOGGER.warning("Telegram başlatılamadı; %s/6 denemesi sonrası tekrar denenecek: %s", attempt, exc)
            try:
                await candidate.shutdown()
            except Exception:
                LOGGER.debug("Başarısız Telegram adayının kapanışı tamamlanamadı", exc_info=True)
            if attempt < 6:
                await asyncio.sleep(min(60, attempt * 10))
        except Exception:
            LOGGER.exception("Telegram başlatılırken beklenmeyen hata oluştu")
            try:
                await candidate.shutdown()
            except Exception:
                LOGGER.debug("Başarısız Telegram adayının kapanışı tamamlanamadı", exc_info=True)
            if attempt < 6:
                await asyncio.sleep(min(60, attempt * 10))
    LOGGER.error("Telegram altı denemeden sonra hazır olmadı; /health çalışır, webhook ve cron 503 döner")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_task
    settings.validate()
    telegram_task = asyncio.create_task(_start_telegram_with_retry())
    try:
        yield
    finally:
        if telegram_task:
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass
        if application and telegram_ready:
            await application.stop()
            await application.shutdown()


app = FastAPI(title="Nexa Telegram Bot", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexa", "telegram": "ready" if telegram_ready else "starting"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict[str, bool]:
    if application is None or not telegram_ready:
        raise HTTPException(status_code=503, detail="Telegram bot henüz hazır değil")
    expected = settings.telegram_webhook_secret
    if expected and not secrets.compare_digest(x_telegram_bot_api_secret_token or "", expected):
        raise HTTPException(status_code=403, detail="Geçersiz webhook imzası")
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    await application.process_update(update)
    return {"ok": True}


@app.post("/internal/cron")
async def internal_cron(x_cron_secret: str | None = Header(default=None)) -> dict[str, bool]:
    if not settings.cron_secret or not secrets.compare_digest(x_cron_secret or "", settings.cron_secret):
        raise HTTPException(status_code=403, detail="Geçersiz cron anahtarı")
    if application is None or not telegram_ready:
        raise HTTPException(status_code=503, detail="Telegram bot henüz hazır değil")
    context = type("CronContext", (), {"application": application, "bot": application.bot})()
    await check_active_alarms(context)
    await check_kap_updates(context)
    return {"checked": True}
