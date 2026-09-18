"""Market and order book snapshot storage.

Routes, the snapshot job, and the seed script talk to storage only through
these functions. Services never embed raw queries.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from polyprism.ingestion.schemas import MarketMetadata, OrderBook
from polyprism.storage.models import Market, OrderBookSnapshot


async def upsert_markets(session: AsyncSession, markets: list[MarketMetadata]) -> int:
    """Insert or update markets by condition id. Idempotent across polls."""
    for market in markets:
        await session.merge(
            Market(
                market_id=market.condition_id,
                question=market.question,
                category=market.category,
                tags=market.tags,
                resolution_source=market.resolution_source,
                created_at=market.created_at,
                closes_at=market.closes_at,
                resolved_at=market.resolved_at,
                outcome=market.outcome,
                active=market.active,
            )
        )
    await session.flush()
    return len(markets)


async def save_snapshots(session: AsyncSession, books: list[OrderBook]) -> int:
    """Persist one row per token at one timestamp."""
    for book in books:
        session.add(
            OrderBookSnapshot(
                token_id=book.token_id,
                ts=book.timestamp,
                bids=[level.model_dump() for level in book.bids],
                asks=[level.model_dump() for level in book.asks],
                best_bid=book.best_bid,
                best_ask=book.best_ask,
            )
        )
    await session.flush()
    return len(books)


async def get_latest_snapshot(session: AsyncSession, token_id: str) -> OrderBookSnapshot | None:
    """Return the newest stored snapshot for a token, if any."""
    result = await session.execute(
        select(OrderBookSnapshot)
        .where(OrderBookSnapshot.token_id == token_id)
        .order_by(desc(OrderBookSnapshot.ts))
        .limit(1)
    )
    return result.scalars().first()


async def list_markets(session: AsyncSession, *, limit: int = 100, offset: int = 0) -> list[Market]:
    """Return stored markets in insertion-friendly order."""
    result = await session.execute(
        select(Market).order_by(Market.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
