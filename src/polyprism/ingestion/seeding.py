"""One shot market and order book seeding.

Routes, the snapshot job, and the seed script talk to storage only through
the repository functions. This module is the seed entry point doing a
single Gamma plus CLOB pass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from polyprism.ingestion.schemas import MarketMetadata
from polyprism.storage import repository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedResult:
    market_count: int = 0
    token_count: int = 0
    snapshot_count: int = 0
    skipped_token_count: int = 0


class GammaLike(Protocol):
    async def fetch_all_active_markets(self, max_markets: int = 200) -> list[MarketMetadata]: ...


class ClobLike(Protocol):
    async def fetch_order_book(self, token_id: str) -> Any: ...


def extract_tradeable_tokens(markets: list[MarketMetadata]) -> list[str]:
    """Resolve tradeable token ids from market metadata in first-seen order."""
    seen: dict[str, None] = {}
    for market in markets:
        for token in market.tokens or []:
            token_id = str(token.get("token_id", "")).strip()
            if not token_id or not token_id.isdigit():
                continue
            seen.setdefault(token_id)
    return list(seen)


async def seed_once(
    session: Any,
    gamma_client: GammaLike,
    clob_client: ClobLike,
    max_markets: int = 200,
) -> SeedResult:
    """Fetch markets and one book per token, persisting via the repository."""
    markets = await gamma_client.fetch_all_active_markets(max_markets=max_markets)
    await repository.upsert_markets(session, markets)

    token_ids = extract_tradeable_tokens(markets)
    books: list[Any] = []
    skipped = 0
    for token_id in token_ids:
        try:
            books.append(await clob_client.fetch_order_book(token_id))
        except Exception as exc:  # keep seeding on single token failures
            skipped += 1
            logger.warning("Skipping token %s: %s", token_id, exc)

    await repository.save_snapshots(session, books)

    return SeedResult(
        market_count=len(markets),
        token_count=len(token_ids),
        snapshot_count=len(books),
        skipped_token_count=skipped,
    )
