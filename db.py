import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import aiosqlite

DB_PATH = "expenses.db"
MSK = ZoneInfo("Europe/Moscow")

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    category TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses (user_id, created_at);
"""


async def init_db(path: str = DB_PATH) -> None:
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


def start_of_period(period: str) -> int:
    now = datetime.now(MSK)
    if period == "день":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "неделя":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "месяц":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"неизвестный период: {period}")
    return int(start.timestamp())


async def add_expense(
    user_id: int, amount_cents: int, category: str, path: str = DB_PATH
) -> int:
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "INSERT INTO expenses (user_id, amount_cents, category, created_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, amount_cents, category, int(datetime.now(MSK).timestamp())),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def stats_by_category(
    user_id: int, since: int, path: str = DB_PATH
) -> list[tuple[str, int]]:
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            """
            SELECT category, SUM(amount_cents) AS total
            FROM expenses
            WHERE user_id = ? AND created_at >= ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, since),
        )
        rows = await cursor.fetchall()
        return [(row[0], row[1]) for row in rows]


async def recent(
    user_id: int, limit: int = 10, path: str = DB_PATH
) -> list[tuple[int, str, int]]:
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT created_at, category, amount_cents FROM expenses"
            " WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [(row[0], row[1], row[2]) for row in rows]


async def export_csv(user_id: int, path: str = DB_PATH) -> bytes:
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(
            "SELECT created_at, category, amount_cents FROM expenses"
            " WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = await cursor.fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["дата", "категория", "сумма, руб"])
    for created_at, category, amount_cents in rows:
        writer.writerow(
            [
                datetime.fromtimestamp(created_at, MSK).strftime("%d.%m.%Y %H:%M"),
                category,
                f"{Decimal(amount_cents) / 100:.2f}",
            ]
        )
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
