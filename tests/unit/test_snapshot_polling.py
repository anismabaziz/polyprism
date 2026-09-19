"""Scheduled snapshot polling tests (no network, no database)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

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
    def __init__(self, markets: list[MarketMetadata], fail: bool = False):
        self._markets = markets
        self.fail = fail
        self.seen_max: int | None = None

    async def fetch_all_active_markets(self, max_markets: int = 200):
        self.seen_max = max_markets
        if self.fail:
            raise RuntimeError("gamma down")
        return self._markets[:max_markets]


class _FakeClob:
    def __init__(self, books: dict[str, OrderBook], failing: set[str] | None = None):
        self._books = books
        self._failing = failing or set()

    async def fetch_order_book(self, token_id: str):
        if token_id in self._failing:
            raise RuntimeError(f"book failed for {token_id}")
        return self._books[token_id]


class _FakeSession:
    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


def _factory_for(session: _FakeSession):
    @asynccontextmanager
    async def factory():
        yield session

    return factory


async def test_poll_reuses_seed_path_and_commits(monkeypatch):
    from polyprism.ingestion import seeding, snapshot_job

    markets = [_market("0x" + "a" * 64, "111", "222")]
    gamma = _FakeGamma(markets)
    clob = _FakeClob({tid: _book(tid) for tid in ("111", "222")})
    session = _FakeSession()

    calls: list = []

    async def fake_seed_once(sess, gamma_client, clob_client, max_markets=200):
        calls.append((sess, gamma_client, clob_client, max_markets))
        return seeding.SeedResult(
            market_count=1, token_count=2, snapshot_count=2, skipped_token_count=0
        )

    monkeypatch.setattr(seeding, "seed_once", fake_seed_once)

    result = await snapshot_job.poll_once(_factory_for(session), gamma, clob, max_markets=200)

    assert result is not None
    assert result.snapshot_count == 2
    assert len(calls) == 1
    assert calls[0][1] is gamma
    assert calls[0][2] is clob
    assert calls[0][3] == 200
    assert session.committed == 1


async def test_poll_skips_gamma_failure_and_logs_without_raising(caplog):
    from polyprism.ingestion import snapshot_job

    gamma = _FakeGamma([], fail=True)
    clob = _FakeClob({})
    session = _FakeSession()

    with caplog.at_level(logging.WARNING, logger="polyprism.ingestion.snapshot_job"):
        result = await snapshot_job.poll_once(_factory_for(session), gamma, clob, max_markets=50)

    assert result is None
    assert session.committed == 0
    assert any("gamma" in r.message.lower() or "poll" in r.message.lower() for r in caplog.records)


async def test_poll_keeps_single_token_failures_without_aborting(monkeypatch):
    from polyprism.ingestion import snapshot_job
    from polyprism.storage import repository

    markets = [_market("0x" + "b" * 64, "111", "222")]
    gamma = _FakeGamma(markets)
    clob = _FakeClob({"111": _book("111")}, failing={"222"})
    session = _FakeSession()

    async def fake_upsert(sess, items):
        return len(items)

    saved: list = []

    async def fake_save(sess, books):
        saved.extend(books)
        return len(books)

    monkeypatch.setattr(repository, "upsert_markets", fake_upsert)
    monkeypatch.setattr(repository, "save_snapshots", fake_save)

    result = await snapshot_job.poll_once(_factory_for(session), gamma, clob, max_markets=200)

    assert result is not None
    assert result.snapshot_count == 1
    assert result.skipped_token_count == 1
    assert session.committed == 1


def test_scheduler_uses_interval_and_max_markets_from_settings(monkeypatch):
    from polyprism.ingestion import snapshot_job

    seen: dict = {}

    class _FakeScheduler:
        def add_job(self, func, trigger=None, **kwargs):
            seen["func"] = func
            seen["trigger"] = trigger
            seen["kwargs"] = kwargs

    monkeypatch.setattr(snapshot_job, "AsyncIOScheduler", lambda *a, **k: _FakeScheduler())

    scheduler = snapshot_job.create_scheduler(
        _factory_for(_FakeSession()),
        _FakeGamma([]),
        _FakeClob({}),
        interval_seconds=42,
        max_markets=77,
    )

    assert seen["kwargs"]["max_instances"] == 1
    assert seen["kwargs"].get("coalesce") is True
    # IntervalTrigger carries the configured interval.
    assert seen["trigger"].interval.total_seconds() == 42
    assert scheduler is not None


async def test_api_lifespan_starts_and_stops_scheduler(monkeypatch):
    from polyprism.api import main as api_main

    started: list = []
    stopped: list = []

    class _FakeScheduler:
        def start(self):
            started.append(True)

        def shutdown(self, wait=False):
            stopped.append(wait)

    created: dict = {}

    def fake_create(session_factory, gamma, clob, interval_seconds, max_markets):
        created["interval_seconds"] = interval_seconds
        created["max_markets"] = max_markets
        return _FakeScheduler()

    monkeypatch.setattr(api_main, "create_scheduler", fake_create)

    async with api_main.lifespan(api_main.app):
        assert started == [True]

    assert stopped == [False]
    assert created["interval_seconds"] == api_main.get_settings().snapshot_interval_seconds
    assert created["max_markets"] == api_main.get_settings().max_markets_to_track
