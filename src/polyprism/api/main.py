from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from polyprism.config import get_settings
from polyprism.ingestion.clob_client import ClobClient
from polyprism.ingestion.gamma_client import GammaClient
from polyprism.ingestion.snapshot_job import create_scheduler
from polyprism.storage.database import get_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler = create_scheduler(
        get_session_factory(),
        GammaClient(),
        ClobClient(),
        interval_seconds=settings.snapshot_interval_seconds,
        max_markets=settings.max_markets_to_track,
    )
    scheduler.start()
    logger.info(
        "Snapshot polling every %ds for up to %d markets",
        settings.snapshot_interval_seconds,
        settings.max_markets_to_track,
    )
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Polyprism", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "OK"}
