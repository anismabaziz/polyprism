from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from polyprism.config import get_settings
from polyprism.ingestion.clob_client import ClobClient
from polyprism.ingestion.gamma_client import GammaClient
from polyprism.ingestion.schemas import OrderBook, OrderBookLevel
from polyprism.ingestion.snapshot_job import create_scheduler
from polyprism.storage import repository
from polyprism.storage.database import get_session, get_session_factory

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


@app.get("/books/{token_id}", response_model=OrderBook)
async def get_latest_book(
    token_id: Annotated[str, Path(pattern=r"^\d+$")],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Return the newest stored order book snapshot for a token."""
    snapshot = await repository.get_latest_snapshot(session, token_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshots stored for token {token_id}",
        )
    return OrderBook(
        token_id=snapshot.token_id,
        timestamp=snapshot.ts,
        bids=[OrderBookLevel(**level) for level in snapshot.bids],
        asks=[OrderBookLevel(**level) for level in snapshot.asks],
        best_bid=snapshot.best_bid,
        best_ask=snapshot.best_ask,
    )
