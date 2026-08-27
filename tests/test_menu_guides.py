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
