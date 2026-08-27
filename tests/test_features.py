from pathlib import Path

import pytest

from nexa.alerts import alarm_matches, parse_alarm_condition, parse_asset_type
from nexa.db import Database
from nexa.providers import Quote


def make_quote(price: float = 100.0, change_pct: float | None = 6.0) -> Quote:
    return Quote(
        symbol="TEST",
        name="TEST",
        price=price,
        change_pct=change_pct,
        volume=None,
        currency="TRY",
        as_of=None,
        source="test",
        delayed=True,
    )


def test_alarm_conditions() -> None:
    assert alarm_matches({"id": 1, "condition": "above", "target": 99}, make_quote())
    assert alarm_matches({"id": 2, "condition": "below", "target": 101}, make_quote())
    assert alarm_matches({"id": 3, "condition": "change_pct", "target": 5}, make_quote())
    assert alarm_matches({"id": 4, "condition": "above", "target": 101}, make_quote()) is None


def test_alarm_and_asset_aliases() -> None:
    assert parse_alarm_condition("ÜST") == "above"
    assert parse_alarm_condition("degisim") == "change_pct"
    assert parse_asset_type("BIST") == "stock"
    assert parse_asset_type("coin") == "crypto"
    with pytest.raises(ValueError):
        parse_asset_type("forex")


def test_portfolio_positions_reduce_average_cost(tmp_path: Path) -> None:
    db = Database(tmp_path / "nexa.sqlite3")
    db.initialize()
    db.add_transaction(42, "stock", "THYAO", "buy", 10, 100, "TRY")
    db.add_transaction(42, "stock", "THYAO", "buy", 10, 120, "TRY")
    db.add_transaction(42, "stock", "THYAO", "sell", 5, 110, "TRY")

    positions = db.portfolio_positions(42)
    assert len(positions) == 1
    assert positions[0]["quantity"] == 15
    assert positions[0]["cost"] == pytest.approx(1650)
