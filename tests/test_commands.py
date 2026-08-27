from __future__ import annotations

import asyncio

from nexa.bot import NEXA_COMMANDS, configure_command_menu, guide_keyboard


class FakeBot:
    def __init__(self) -> None:
        self.commands = []

    async def set_my_commands(self, commands) -> None:
        self.commands = list(commands)


def test_configure_command_menu_registers_core_commands() -> None:
    bot = FakeBot()
    assert asyncio.run(configure_command_menu(bot)) is True
    names = [command.command for command in bot.commands]
    assert names == ["start", "yardim", "hisse", "kripto"]
    assert all(1 <= len(command.description) <= 256 for command in bot.commands)


def test_configure_command_menu_keeps_bist_and_crypto_separate() -> None:
    class ScopedBot(FakeBot):
        def __init__(self) -> None:
            super().__init__()
            self.scope = None

        async def set_my_commands(self, commands, scope=None) -> None:
            self.commands = list(commands)
            self.scope = scope

    bist_bot = ScopedBot()
    assert asyncio.run(configure_command_menu(bist_bot, chat_id=42, domain="bist")) is True
    bist_names = [command.command for command in bist_bot.commands]
    assert "hisse" in bist_names
    assert "kripto" not in bist_names
    assert "derinlik" in bist_names

    crypto_bot = ScopedBot()
    assert asyncio.run(configure_command_menu(crypto_bot, chat_id=42, domain="crypto")) is True
    crypto_names = [command.command for command in crypto_bot.commands]
    assert "kripto" in crypto_names
    assert "hisse" not in crypto_names
    assert "derinlik" in crypto_names



def test_domain_guides_do_not_cross_list_commands() -> None:
    from nexa.bot import active_menu_guide

    bist = active_menu_guide("portfolio", "bist")
    crypto = active_menu_guide("portfolio", "crypto")
    assert bist is not None and crypto is not None
    assert all("kripto" not in command.lower() for command, _ in bist["commands"])
    assert all("hisse" not in command.lower() for command, _ in crypto["commands"])

    stock_rows = guide_keyboard("stock").inline_keyboard
    crypto_rows = guide_keyboard("crypto").inline_keyboard
    assert all(row for row in stock_rows + crypto_rows)
