"""Latest stored book endpoint tests (no network, no database)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from polyprism.api.main import app
from polyprism.storage import repository
from polyprism.storage.database import get_session
from polyprism.storage.models import OrderBookSnapshot


def _snapshot(token_id: str) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        token_id=token_id,
        ts=datetime.now(UTC),
        bids=[{"price": 0.5, "size": 10.0}],
        asks=[{"price": 0.51, "size": 12.0}],
        best_bid=0.5,
        best_ask=0.51,
    )


@pytest.fixture()
def client():
    async def override_get_session():
        yield object()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_get_latest_book_returns_stored_snapshot(monkeypatch, client: TestClient):
    snapshot = _snapshot("123")

    async def fake_get_latest(session, token_id: str):
        return snapshot if token_id == "123" else None

    monkeypatch.setattr(repository, "get_latest_snapshot", fake_get_latest)
    response = client.get("/books/123")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["token_id"] == "123"
    assert "timestamp" in payload
    assert payload["bids"] == [{"price": 0.5, "size": 10.0}]
    assert payload["asks"] == [{"price": 0.51, "size": 12.0}]
    assert payload["best_bid"] == 0.5
    assert payload["best_ask"] == 0.51


def test_get_latest_book_missing_returns_404(monkeypatch, client: TestClient):
    async def fake_get_latest(session, token_id: str):
        return None

    monkeypatch.setattr(repository, "get_latest_snapshot", fake_get_latest)
    response = client.get("/books/999")

    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_get_latest_book_malformed_token_returns_422(client: TestClient):
    response = client.get("/books/not-a-token")

    assert response.status_code == 422
