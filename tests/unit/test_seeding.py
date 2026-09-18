"""Offline seeding tests (no network, no database)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from polyprism.ingestion.schemas import MarketMetadata, OrderBook, OrderBookLevel


def _market(condition_id: str, *token_ids: str) -> MarketMetadata:
    now = datetime.now(UTC)
    return MarketMetadata(
        condition_id=condition_id,
        question=f"Question {condition_id[:8]}",
        created_at=now,
        active=True,
        tokens=[{"token_id": tid, "outcome": "Yes"} for tid in token_ids],
    )


def _book(token_id: str) -> OrderBook:
    return OrderBook(
        token_id=token_id,
        timestamp=datetime.now(UTC),
        bids=[OrderBookLevel(price=0.5, size=10.0)],
        asks=[OrderBookLevel(price=0.51, size=10.0)],
        best_bid=0.5,
        best_ask=0.51,
    )


class _FakeGamma:
    def __init__(self, markets: list[MarketMetadata]):
        self._markets = markets
        self.seen_max: int | None = None

    async def fetch_all_active_markets(self, max_markets: int = 200):
        self.seen_max = max_markets
        return self._markets[:max_markets]


class _FakeClob:
    def __init__(self, books: dict[str, OrderBook], failing: set[str] | None = None):
        self._books = books
        self._failing = failing or set()
        self.requested: list[str] = []

    async def fetch_order_book(self, token_id: str):
        self.requested.append(token_id)
        if token_id in self._failing:
            raise RuntimeError(f"book failed for {token_id}")
        return self._books[token_id]


class _FakeSession:
    pass


@pytest.fixture()
def anyio_backend():
    return "asyncio"


async def test_seed_persists_markets_and_books_through_repository(monkeypatch):
    from polyprism.ingestion import seeding
    from polyprism.storage import repository

    markets = [
        _market("0x" + "a" * 64, "111", "222"),
        _market("0x" + "b" * 64, "333"),
    ]
    gamma = _FakeGamma(markets)
    clob = _FakeClob({tid: _book(tid) for tid in ("111", "222", "333")})

    upserted: list = []
    saved: list = []

    async def fake_upsert(session, items):
        upserted.extend(items)
        return len(items)

    async def fake_save(session, books):
        saved.extend(books)
        return len(books)

    monkeypatch.setattr(repository, "upsert_markets", fake_upsert)
    monkeypatch.setattr(repository, "save_snapshots", fake_save)

    result = await seeding.seed_once(_FakeSession(), gamma, clob, max_markets=200)

    assert gamma.seen_max == 200
    assert result.market_count == 2
    assert result.token_count == 3
    assert result.snapshot_count == 3
    assert len(upserted) == 2
    assert {b.token_id for b in saved} == {"111", "222", "333"}


async def test_seed_skips_single_token_failure_and_logs(monkeypatch, caplog):
    from polyprism.ingestion import seeding
    from polyprism.storage import repository

    markets = [_market("0x" + "c" * 64, "111", "222")]
    gamma = _FakeGamma(markets)
    clob = _FakeClob({"111": _book("111")}, failing={"222"})

    async def fake_upsert(session, items):
        return len(items)

    saved: list = []

    async def fake_save(session, books):
        saved.extend(books)
        return len(books)

    monkeypatch.setattr(repository, "upsert_markets", fake_upsert)
    monkeypatch.setattr(repository, "save_snapshots", fake_save)

    with caplog.at_level(logging.WARNING, logger="polyprism.ingestion.seeding"):
        result = await seeding.seed_once(_FakeSession(), gamma, clob, max_markets=200)

    assert result.market_count == 1
    assert result.token_count == 2
    assert result.snapshot_count == 1
    assert result.skipped_token_count == 1
    assert [b.token_id for b in saved] == ["111"]
    assert any("222" in r.message for r in caplog.records)


def test_extract_tradeable_tokens_skips_empty_and_non_digit():
    from polyprism.ingestion.seeding import extract_tradeable_tokens

    markets = [
        _market("0x" + "d" * 64, "123", "", "abc"),
        _market("0x" + "e" * 64),
    ]
    assert extract_tradeable_tokens(markets) == ["123"]
