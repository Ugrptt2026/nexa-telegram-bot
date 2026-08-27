"""Nexa için küçük ve bağımlılıksız SQLite katmanı.

İlk sürümde kullanıcı tercihleri için SQLite kullanılır. Render Free'ın
ephemeral filesystem davranışı nedeniyle deploy aşamasında kalıcı dış DB
seçeneği ayrıca belgelenir.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
    chat_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('stock', 'crypto')),
    symbol TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, asset_type, symbol)
);

CREATE TABLE IF NOT EXISTS alarms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('stock', 'crypto')),
    symbol TEXT NOT NULL,
    condition TEXT NOT NULL CHECK(condition IN ('above', 'below', 'change_pct')),
    target REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_triggered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('stock', 'crypto')),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
    quantity REAL NOT NULL CHECK(quantity > 0),
    price REAL NOT NULL CHECK(price >= 0),
    currency TEXT NOT NULL DEFAULT 'TRY',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kap_seen (
    fingerprint TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    company TEXT NOT NULL,
    subject TEXT NOT NULL,
    url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """SQLite bağlantılarını kısa ömürlü açıp kapatan repository."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def upsert_user(
        self,
        chat_id: int,
        username: str | None,
        first_name: str | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (chat_id, username, first_name)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chat_id, username, first_name),
            )

    def add_watch(self, chat_id: int, asset_type: str, symbol: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO watchlist (chat_id, asset_type, symbol) VALUES (?, ?, ?)",
                (chat_id, asset_type, symbol),
            )

    def remove_watch(self, chat_id: int, asset_type: str, symbol: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM watchlist WHERE chat_id = ? AND asset_type = ? AND symbol = ?",
                (chat_id, asset_type, symbol),
            )
        return cursor.rowcount > 0

    def list_watches(self, chat_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT asset_type, symbol, created_at FROM watchlist WHERE chat_id = ? ORDER BY created_at, asset_type, symbol",
                (chat_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_alarm(
        self,
        chat_id: int,
        asset_type: str,
        symbol: str,
        condition: str,
        target: float,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO alarms (chat_id, asset_type, symbol, condition, target)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chat_id, asset_type, symbol, condition, target),
            )
        return int(cursor.lastrowid)

    def list_alarms(self, chat_id: int, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM alarms WHERE chat_id = ?"
        params: list[Any] = [chat_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY id DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_all_active_alarms(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alarms WHERE is_active = 1 ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def deactivate_alarm(self, alarm_id: int, chat_id: int | None = None) -> bool:
        query = "UPDATE alarms SET is_active = 0 WHERE id = ?"
        params: list[Any] = [alarm_id]
        if chat_id is not None:
            query += " AND chat_id = ?"
            params.append(chat_id)
        with self.connect() as connection:
            cursor = connection.execute(query, params)
        return cursor.rowcount > 0

    def mark_alarm_triggered(self, alarm_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE alarms SET last_triggered_at = CURRENT_TIMESTAMP, is_active = 0 WHERE id = ?",
                (alarm_id,),
            )

    def list_user_chat_ids(self) -> list[int]:
        with self.connect() as connection:
            rows = connection.execute("SELECT chat_id FROM users ORDER BY chat_id").fetchall()
        return [int(row["chat_id"]) for row in rows]

    def kap_seen_count(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM kap_seen").fetchone()
        return int(row["count"])

    def mark_kap_seen(self, fingerprint: str, date: str, company: str, subject: str, url: str | None) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO kap_seen (fingerprint, date, company, subject, url) VALUES (?, ?, ?, ?, ?)",
                (fingerprint, date, company, subject, url),
            )
        return cursor.rowcount > 0

    def add_transaction(
        self,
        chat_id: int,
        asset_type: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        currency: str,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO portfolio_transactions
                    (chat_id, asset_type, symbol, side, quantity, price, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (chat_id, asset_type, symbol, side, quantity, price, currency),
            )
        return int(cursor.lastrowid)

    def list_transactions(self, chat_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM portfolio_transactions
                WHERE chat_id = ?
                ORDER BY id
                """,
                (chat_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def portfolio_positions(self, chat_id: int) -> list[dict[str, Any]]:
        """Alış-satış miktarını ve basit maliyet toplamını döndürür.

        Satışlar FIFO/ortalama maliyet değil, pozisyon maliyetinden oransal
        düşümle yaklaşıklaştırılır; bot bunu açıkça "basit sanal portföy"
        olarak sunar.
        """
        transactions = self.list_transactions(chat_id)
        positions: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in transactions:
            key = (row["asset_type"], row["symbol"], row["currency"])
            position = positions.setdefault(
                key,
                {"asset_type": row["asset_type"], "symbol": row["symbol"], "currency": row["currency"], "quantity": 0.0, "cost": 0.0},
            )
            quantity = float(row["quantity"])
            price = float(row["price"])
            if row["side"] == "buy":
                position["quantity"] += quantity
                position["cost"] += quantity * price
            else:
                old_quantity = position["quantity"]
                if old_quantity > 0:
                    average_cost = position["cost"] / old_quantity
                    position["cost"] = max(0.0, position["cost"] - quantity * average_cost)
                position["quantity"] = max(0.0, old_quantity - quantity)
        return [position for position in positions.values() if position["quantity"] > 1e-12]
