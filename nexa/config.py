"""Nexa uygulama ayarları."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    """Uygulamanın çevre değişkenlerinden yüklenen ayarları."""

    telegram_bot_token: str
    database_path: Path
    log_level: str
    app_base_url: str | None
    cron_secret: str | None
    telegram_webhook_secret: str | None = None
    alarm_check_interval_seconds: int = 60
    enable_internal_scheduler: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        db_path = Path(os.getenv("DATABASE_PATH", "./data/nexa.sqlite3"))
        app_base_url = (os.getenv("APP_BASE_URL", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip() or None)
        cron_secret = os.getenv("CRON_SECRET", "").strip() or None
        webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
        try:
            interval = max(30, int(os.getenv("ALARM_CHECK_INTERVAL_SECONDS", "60")))
        except ValueError:
            interval = 60
        enable_scheduler = os.getenv("ENABLE_INTERNAL_SCHEDULER", "true").strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            telegram_bot_token=token,
            database_path=db_path,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            app_base_url=app_base_url,
            cron_secret=cron_secret,
            telegram_webhook_secret=webhook_secret,
            alarm_check_interval_seconds=interval,
            enable_internal_scheduler=enable_scheduler,
        )

    def validate(self) -> None:
        if not self.telegram_bot_token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN tanımlı değil. @BotFather üzerinden token oluşturup .env içine ekleyin."
            )
