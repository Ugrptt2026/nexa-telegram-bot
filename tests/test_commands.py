from __future__ import annotations

import asyncio

from nexa.bot import NEXA_COMMANDS, configure_command_menu


class FakeBot:
    def __init__(self) -> None:
        self.commands = []

    async def set_my_commands(self, commands) -> None:
        self.commands = list(commands)


def test_configure_command_menu_registers_core_commands() -> None:
    bot = FakeBot()
    assert asyncio.run(configure_command_menu(bot)) is True
    names = [command.command for command in bot.commands]
    assert names[:4] == ["start", "yardim", "hisse", "kripto"]
    assert "grafik" in names
    assert "portfoy" in names
    assert all(1 <= len(command.description) <= 256 for command in bot.commands)
