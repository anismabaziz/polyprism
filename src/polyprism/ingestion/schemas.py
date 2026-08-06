from datetime import datetime

from pydantic import BaseModel, Field


class MarketMetadata(BaseModel):
    """Market metadata from Gamma API."""

    condition_id: str = Field(..., description="Unique market identifier (66-char hex)")
    question: str
    category: str | None = None
    tags: dict | None = None
    resolution_source: str | None = None
    created_at: datetime
    closes_at: datetime | None = None
    resolved_at: datetime | None = None
    outcome: str | None = None  # YES/NO/PENDING
    active: bool = True
    tokens: list[dict] = Field(default_factory=list)  # [{token_id, outcome}]


class OrderBookLevel(BaseModel):
    """Single price level in the order book."""

    price: float
    size: float


class OrderBook(BaseModel):
    """Order book snapshot from CLOB API."""

    market_id: str
    timestamp: datetime
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    best_bid: float | None = None
    best_ask: float | None = None
