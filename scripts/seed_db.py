"""One shot seed: fetch markets and books, persist via the repository."""

from __future__ import annotations

import asyncio
import logging

from polyprism.config import get_settings
from polyprism.ingestion.clob_client import ClobClient
from polyprism.ingestion.gamma_client import GammaClient
from polyprism.ingestion.seeding import seed_once
from polyprism.storage.database import get_session_factory

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    gamma = GammaClient()
    clob = ClobClient()
    factory = get_session_factory()
    async with factory() as session:
        result = await seed_once(
            session,
            gamma,
            clob,
            max_markets=settings.max_markets_to_track,
        )
        await session.commit()
    print(
        f"Seed complete: {result.market_count} markets, "
        f"{result.token_count} tokens, "
        f"{result.snapshot_count} snapshots, "
        f"{result.skipped_token_count} skipped"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
