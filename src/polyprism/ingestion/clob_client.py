from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from polyprism.config import get_settings
from polyprism.ingestion.schemas import OrderBook, OrderBookLevel


def parse_order_book(
    token_id: str,
    data: dict[str, Any],
    timestamp: datetime | None = None,
) -> OrderBook:
    """Parse one raw CLOB book payload into an OrderBook (no network)."""
    bids = [
        OrderBookLevel(price=float(level["price"]), size=float(level["size"]))
        for level in data.get("bids", [])
    ]
    asks = [
        OrderBookLevel(price=float(level["price"]), size=float(level["size"]))
        for level in data.get("asks", [])
    ]

    best_bid = max((b.price for b in bids), default=None)
    best_ask = min((a.price for a in asks), default=None)

    return OrderBook(
        token_id=token_id,
        timestamp=timestamp or datetime.now(UTC),
        bids=bids,
        asks=asks,
        best_bid=best_bid,
        best_ask=best_ask,
    )


class ClobClient:
    """
    Client for Polymarket CLOB API (order books).
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or get_settings().polymarket_clob_url).rstrip("/")
        self.timeout = timeout

    async def fetch_order_book(self, token_id: str) -> OrderBook:
        """
        Fetch order book for a specific token.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/book",
                params={"token_id": token_id},
            )
            response.raise_for_status()
            data = response.json()

        return parse_order_book(token_id, data)
