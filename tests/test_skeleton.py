from pathlib import Path

import pytest

from nexa.bot import main_menu
from nexa.config import Settings
from nexa.db import Database
from nexa.texts import HELP_TEXT


def test_settings_requires_token(tmp_path: Path) -> None:
    settings = Settings(
        telegram_bot_token="",
        database_path=tmp_path / "nexa.sqlite3",
        log_level="INFO",
        app_base_url=None,
        cron_secret=None,
    )
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        settings.validate()


def test_database_initializes_and_saves_user_and_watchlist(tmp_path: Path) -> None:
    db = Database(tmp_path / "data" / "nexa.sqlite3")
    db.initialize()
    db.upsert_user(chat_id=42, username="tester", first_name="Test")
    db.add_watch(chat_id=42, asset_type="stock", symbol="THYAO")
    db.add_watch(chat_id=42, asset_type="crypto", symbol="BTC")

    assert {item["symbol"] for item in db.list_watches(42)} == {"THYAO", "BTC"}


def test_main_menu_contains_core_buttons() -> None:
    markup = main_menu()
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "BIST Hisse" in labels
    assert "Kripto" in labels
    assert "Portföy" in labels
    assert "Alarmlar" in labels
    assert "İzleme Listesi" in labels
    assert "Yardım" in labels


def test_help_contains_required_commands() -> None:
    for command in ("/start", "/yardim", "/hisse", "/kripto", "/portfoy", "/alarm"):
        assert command in HELP_TEXT
