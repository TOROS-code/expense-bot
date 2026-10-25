import asyncio

import pytest

import db


def test_stats_groups_by_category(tmp_path):
    path = str(tmp_path / "test.db")

    async def scenario():
        await db.init_db(path)
        await db.add_expense(1, 45000, "еда", path)
        await db.add_expense(1, 20000, "транспорт", path)
        await db.add_expense(1, 5500, "еда", path)
        await db.add_expense(2, 99900, "еда", path)
        return await db.stats_by_category(1, since=0, path=path)

    assert asyncio.run(scenario()) == [("еда", 50500), ("транспорт", 20000)]


def test_recent_returns_newest_first(tmp_path):
    path = str(tmp_path / "test.db")

    async def scenario():
        await db.init_db(path)
        await db.add_expense(1, 10000, "кофе", path)
        await db.add_expense(1, 25000, "обед", path)
        return await db.recent(1, path=path)

    rows = asyncio.run(scenario())
    assert [row[1] for row in rows] == ["обед", "кофе"]


def test_export_csv_is_utf8_with_bom(tmp_path):
    path = str(tmp_path / "test.db")

    async def scenario():
        await db.init_db(path)
        await db.add_expense(1, 45050, "еда", path)
        return await db.export_csv(1, path)

    data = asyncio.run(scenario()).decode("utf-8-sig")
    assert "еда" in data
    assert "450.50" in data


def test_unknown_period_raises():
    with pytest.raises(ValueError):
        db.start_of_period("год")
