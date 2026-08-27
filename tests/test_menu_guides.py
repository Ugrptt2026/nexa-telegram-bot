from nexa.bot import MENU_GUIDES, guide_keyboard


def test_all_actionable_menu_sections_have_commands() -> None:
    expected = {"stock", "crypto", "portfolio", "alerts", "watchlist"}
    assert set(MENU_GUIDES) == expected
    for guide in MENU_GUIDES.values():
        assert guide["title"]
        assert guide["message"]
        assert len(guide["commands"]) >= 3
        assert all(command.startswith("/") and description for command, description in guide["commands"])


def test_guide_keyboard_has_help_and_home_actions() -> None:
    markup = guide_keyboard("stock")
    labels = [button.text for row in markup.inline_keyboard for button in row]
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "Yardım" in labels
    assert "Ana menü" in labels
    assert "menu:home" in callbacks
    assert "menu:help" in callbacks


class FakeTarget:
    def __init__(self) -> None:
        self.text = ""
        self.reply_markup = None

    async def reply_text(self, text, reply_markup=None) -> None:
        self.text = text
        self.reply_markup = reply_markup


def test_written_command_list_is_copyable() -> None:
    from nexa.bot import HELP_COMMANDS, _reply_command_list

    target = FakeTarget()
    import asyncio

    asyncio.run(_reply_command_list(target, "YARDIM", HELP_COMMANDS))
    assert "/hisse THYAO" in target.text
    assert "/kripto BTC" in target.text
    first_button = target.reply_markup.inline_keyboard[0][0]
    assert first_button.copy_text.text == "/hisse THYAO"
