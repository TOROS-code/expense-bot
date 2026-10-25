import asyncio
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message
from dotenv import load_dotenv

import db

AMOUNT_RE = re.compile(r"^\s*(\D+?)\s+(\d+(?:[.,]\d{1,2})?)\s*₽?\s*$")

HELP = (
    "Как пользоваться:\n\n"
    "Просто напиши «кофе 250» — запишу расход.\n"
    "/add кофе 250 — то же самое\n"
    "/stats — траты за сегодня\n"
    "/stats неделя или /stats месяц\n"
    "/last — последние 10 записей\n"
    "/export — выгрузить всё в CSV"
)

dp = Dispatcher()


def format_money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f} ₽"


def parse_expense(text: str) -> tuple[str, int] | None:
    match = AMOUNT_RE.match(text)
    if not match:
        return None
    category = match.group(1).strip().lower()
    try:
        amount = Decimal(match.group(2).replace(",", "."))
    except InvalidOperation:
        return None
    cents = int(amount * 100)
    if cents <= 0 or not category:
        return None
    return category, cents


async def save(message: Message, category: str, cents: int) -> None:
    await db.add_expense(message.from_user.id, cents, category)
    await message.answer(f"Записал: {category} — {format_money(cents)}")


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Привет! Я считаю твои расходы.\n\n" + HELP)


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@dp.message(Command("add"))
async def cmd_add(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /add кофе 250")
        return
    parsed = parse_expense(parts[1])
    if parsed is None:
        await message.answer("Не понял. Формат: /add кофе 250")
        return
    await save(message, *parsed)


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    period = parts[1].strip().lower() if len(parts) > 1 else "день"
    if period not in {"день", "неделя", "месяц"}:
        await message.answer("Период: день, неделя или месяц. Например: /stats месяц")
        return
    since = db.start_of_period(period)
    rows = await db.stats_by_category(message.from_user.id, since)
    if not rows:
        await message.answer("За этот период записей нет.")
        return
    lines = [f"• {category} — {format_money(total)}" for category, total in rows]
    total = sum(total for _, total in rows)
    await message.answer(
        f"Траты за {period}:\n" + "\n".join(lines) + f"\n\nИтого: {format_money(total)}"
    )


@dp.message(Command("last"))
async def cmd_last(message: Message) -> None:
    rows = await db.recent(message.from_user.id)
    if not rows:
        await message.answer("Пока пусто.")
        return
    lines = [
        f"{datetime.fromtimestamp(ts, db.MSK).strftime('%d.%m %H:%M')} — "
        f"{category} — {format_money(cents)}"
        for ts, category, cents in rows
    ]
    await message.answer("\n".join(lines))


@dp.message(Command("export"))
async def cmd_export(message: Message) -> None:
    data = await db.export_csv(message.from_user.id)
    await message.answer_document(
        BufferedInputFile(data, filename="expenses.csv"),
        caption="Твои расходы в CSV",
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    parsed = parse_expense(message.text or "")
    if parsed is None:
        await message.answer("Не понял. Напиши «кофе 250» или /help.")
        return
    await save(message, *parsed)


async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Нет BOT_TOKEN: создай .env по образцу .env.example")
    await db.init_db()
    bot = Bot(token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
