from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from polyprism.config import get_settings
from polyprism.ingestion.schemas import MarketMetadata


def normalize_tags(raw: Any) -> list[str] | None:
    """Normalize Gamma tag shapes seen in the wild.

    The API returns ``None`` most of the time, but tagged markets show up
    either as a list of strings or as a comma-separated string. Anything
    else (e.g. a JSON-encoded string or an unexpected dict) is coerced to a
    string list so parsing never crashes on tag shape.
    """
    if raw is None:
        return None
    if isinstance(raw, list):
        tags = [str(item).strip() for item in raw if str(item).strip()]
        return tags or None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            decoded = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            decoded = None
        if isinstance(decoded, list):
            tags = [str(item).strip() for item in decoded if str(item).strip()]
            return tags or None
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return [text]
    if isinstance(raw, dict):
        tags = [str(value).strip() for value in raw.values() if str(value).strip()]
        return tags or None
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_gamma_market(item: dict[str, Any]) -> MarketMetadata:
    """Parse one raw Gamma market dict into MarketMetadata (no network)."""
    created_at = _parse_datetime(item["createdAt"])
    if created_at is None:
        raise ValueError("Gamma market missing required createdAt")
    closes_at = _parse_datetime(item.get("endDateIso"))

    try:
        outcomes = (
            json.loads(item["outcomes"])
            if isinstance(item.get("outcomes"), str)
            else item.get("outcomes")
        )
        token_ids = (
            json.loads(item["clobTokenIds"])
            if isinstance(item.get("clobTokenIds"), str)
            else item.get("clobTokenIds")
        )
    except (json.JSONDecodeError, TypeError):
        outcomes, token_ids = None, None
    tokens: list[dict[str, str]] = []
    if isinstance(outcomes, list) and isinstance(token_ids, list):
        for outcome, token_id in zip(outcomes, token_ids, strict=False):
            tokens.append({"token_id": str(token_id), "outcome": str(outcome)})

    category = item.get("category")
    if not isinstance(category, str):
        category = None

    return MarketMetadata(
        condition_id=item["conditionId"],
        question=item["question"],
        category=category,
        tags=normalize_tags(item.get("tags")),
        resolution_source=item.get("resolutionSource"),
        created_at=created_at,
        closes_at=closes_at,
        resolved_at=None,  # Not in Gamma API response
        outcome=item.get("outcome"),
        active=item.get("active", True),
        tokens=tokens,
    )


def parse_gamma_markets(data: list[dict[str, Any]]) -> list[MarketMetadata]:
    """Parse a raw Gamma markets page (no network)."""
    return [parse_gamma_market(item) for item in data]


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

        return parse_gamma_markets(data)

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
