import json
from datetime import datetime

import httpx

from polyprism.config import get_settings
from polyprism.ingestion.schemas import MarketMetadata


class GammaClient:
    """
    Client for Polymarket Gamma API (market metadata).
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or get_settings().gamma_api_url).rstrip("/")
        self.timeout = timeout

    async def fetch_active_markets(self, limit: int = 100, offset: int = 0) -> list[MarketMetadata]:
        """
        Fetch active markets from Gamma API.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/markets",
                params={
                    "limit": limit,
                    "offset": offset,
                    "active": "true",
                    "closed": "false",
                },
            )
            response.raise_for_status()
            data = response.json()

        markets = []
        for item in data:
            # Parse timestamps
            created_at = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
            closes_at = None
            if item.get("endDateIso"):
                closes_at = datetime.fromisoformat(item["endDateIso"].replace("Z", "+00:00"))

            # Extract tokens (YES/NO outcomes)
            tokens = []
            try:
                outcomes = json.loads(item["outcomes"]) if isinstance(item.get("outcomes"), str) else item.get("outcomes")
                token_ids = json.loads(item["clobTokenIds"]) if isinstance(item.get("clobTokenIds"), str) else item.get("clobTokenIds")
            except (json.JSONDecodeError, TypeError):
                outcomes, token_ids = None, None
            if isinstance(outcomes, list) and isinstance(token_ids, list):
                for outcome, token_id in zip(outcomes, token_ids, strict=False):
                    tokens.append({"token_id": token_id, "outcome": outcome})

            market = MarketMetadata(
                condition_id=item["conditionId"],
                question=item["question"],
                category=item.get("category"),
                tags=item.get("tags"),
                resolution_source=item.get("resolutionSource"),
                created_at=created_at,
                closes_at=closes_at,
                resolved_at=None,  # Not in Gamma API response
                outcome=item.get("outcome"),
                active=item.get("active", True),
                tokens=tokens,
            )
            markets.append(market)

        return markets

    async def fetch_all_active_markets(self, max_markets: int = 200) -> list[MarketMetadata]:
        """
        Paginate through all active markets.
        """
        all_markets = []
        offset = 0
        page_size = 100

        while len(all_markets) < max_markets:
            markets = await self.fetch_active_markets(limit=page_size, offset=offset)
            if not markets:
                break
            all_markets.extend(markets)
            offset += page_size

        return all_markets[:max_markets]
