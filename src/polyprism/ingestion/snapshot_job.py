"""Scheduled snapshot polling.

Each poll reuses the same fetch and persist calls as the one shot seed
path (``seeding.seed_once`` through the repository functions). The API
lifespan starts the interval job on startup and stops it on shutdown.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from polyprism.ingestion import seeding

logger = logging.getLogger(__name__)


async def poll_once(
    session_factory: Any,
    gamma_client: Any,
    clob_client: Any,
    max_markets: int = 200,
) -> seeding.SeedResult | None:
    """Run one Gamma plus CLOB pass, committing via its own session.

    Returns the seed result, or None when the poll was skipped after a
    top-level failure. Single token failures are already skipped inside
    ``seed_once``; this layer keeps Gamma or commit failures from
    stopping the schedule.
    """
    try:
        async with session_factory() as session:
            try:
                result = await seeding.seed_once(
                    session,
                    gamma_client,
                    clob_client,
                    max_markets=max_markets,
                )
                await session.commit()
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    logger.exception("Snapshot poll rollback failed")
                raise
    except Exception as exc:
        logger.warning("Skipping snapshot poll: %s", exc)
        return None
    logger.info(
        "Snapshot poll stored %d markets, %d tokens, %d snapshots (%d skipped)",
        result.market_count,
        result.token_count,
        result.snapshot_count,
        result.skipped_token_count,
    )
    return result


def create_scheduler(
    session_factory: Any,
    gamma_client: Any,
    clob_client: Any,
    interval_seconds: int,
    max_markets: int,
) -> AsyncIOScheduler:
    """Build (but do not start) the repeating snapshot poll scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_once,
        trigger=IntervalTrigger(seconds=interval_seconds),
        args=[session_factory, gamma_client, clob_client],
        kwargs={"max_markets": max_markets},
        id="snapshot-poll",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
