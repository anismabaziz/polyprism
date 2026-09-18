"""Repository round trips against compose Postgres.

Run with: ``pytest -m integration`` (needs ``docker compose up postgres``).
Excluded from default unit runs.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from polyprism.config import get_settings
from polyprism.ingestion.clob_client import parse_order_book
from polyprism.ingestion.gamma_client import parse_gamma_markets
from polyprism.storage import repository
from polyprism.storage.models import Base, Market, OrderBookSnapshot
from tests.conftest import load_fixture

pytestmark = pytest.mark.integration


@pytest.fixture()
async def session():
    url = get_settings().database_url
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        for table in (OrderBookSnapshot, Market):
            await s.execute(table.__table__.delete())
        await s.commit()
    await engine.dispose()


async def test_market_upserts_are_idempotent(session):
    raw = load_fixture("gamma_markets.json")
    markets = parse_gamma_markets(raw[:2])

    await repository.upsert_markets(session, markets)
    await session.commit()
    await repository.upsert_markets(session, markets)
    await session.commit()

    stored = await repository.list_markets(session)
    assert len(stored) == 2
    by_id = {m.market_id: m for m in stored}
    assert by_id[markets[0].condition_id].question == markets[0].question


async def test_snapshot_write_and_latest_fetch(session):
    raw = load_fixture("clob_book.json")
    token_id = raw["asset_id"]
    older = parse_order_book(token_id, raw, timestamp=datetime.now(UTC) - timedelta(minutes=5))
    newer = parse_order_book(token_id, raw, timestamp=datetime.now(UTC))

    await repository.save_snapshots(session, [older])
    await session.commit()
    await repository.save_snapshots(session, [newer])
    await session.commit()

    latest = await repository.get_latest_snapshot(session, token_id)
    assert latest is not None
    assert latest.token_id == token_id
    assert latest.ts is not None
    assert latest.bids and latest.asks
    assert latest.best_bid == newer.best_bid
    assert latest.best_ask == newer.best_ask
    # Newest row wins.
    assert latest.ts >= older.timestamp


async def test_latest_snapshot_missing_returns_none(session):
    assert await repository.get_latest_snapshot(session, "no-such-token") is None


async def test_market_listing_returns_stored_markets(session):
    raw = load_fixture("gamma_markets.json")
    markets = parse_gamma_markets(raw[:2])
    await repository.upsert_markets(session, markets)
    await session.commit()

    stored = await repository.list_markets(session)
    assert {m.market_id for m in stored} == {m.condition_id for m in markets}
