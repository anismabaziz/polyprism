"""Offline CLOB book parsing tests (no network, no database)."""

from polyprism.ingestion.clob_client import parse_order_book
from tests.conftest import load_fixture


def test_parse_recorded_book():
    raw = load_fixture("clob_book.json")
    token_id = raw["asset_id"]

    book = parse_order_book(token_id, raw)

    assert book.token_id == token_id
    assert len(book.bids) > 0
    assert len(book.asks) > 0
    assert book.timestamp is not None
    # Levels are numeric after parsing (payload carries strings).
    assert all(isinstance(level.price, float) for level in book.bids)
    assert all(isinstance(level.size, float) for level in book.asks)
    # Best bid/ask are derived from the levels.
    assert book.best_bid == max(level.price for level in book.bids)
    assert book.best_ask == min(level.price for level in book.asks)


def test_parse_empty_book_has_no_best_prices():
    book = parse_order_book("123", {"bids": [], "asks": []})
    assert book.bids == []
    assert book.asks == []
    assert book.best_bid is None
    assert book.best_ask is None
    assert book.timestamp is not None
