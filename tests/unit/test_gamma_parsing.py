"""Offline Gamma market parsing tests (no network, no database)."""

from polyprism.ingestion.gamma_client import parse_gamma_market, parse_gamma_markets
from tests.conftest import load_fixture


def test_parse_recorded_markets_page():
    raw = load_fixture("gamma_markets.json")
    # First two entries are verbatim recorded payloads.
    markets = parse_gamma_markets(raw[:2])

    assert len(markets) == 2
    first = markets[0]
    assert (
        first.condition_id == "0xa467b14d51f01b957109d9cbb1d6c124fab2a089d52ed8f471d23c2812e743b7"
    )
    assert first.question == "Xi Jinping out before 2027?"
    assert first.active is True
    assert len(first.tokens) == 2
    assert {t["outcome"] for t in first.tokens} == {"Yes", "No"}
    assert all(t["token_id"].isdigit() for t in first.tokens)
    assert first.created_at is not None
    assert first.closes_at is not None


def test_parse_tags_none_stays_none():
    raw = load_fixture("gamma_markets.json")
    market = parse_gamma_market(raw[0])
    assert market.tags is None


def test_parse_tags_list_form():
    raw = load_fixture("gamma_markets.json")
    market = parse_gamma_market(raw[2])
    assert market.tags == ["Politics", "US Elections"]


def test_parse_tags_string_form():
    raw = load_fixture("gamma_markets.json")
    market = parse_gamma_market(raw[3])
    assert market.tags == ["Politics", "US Elections"]


def test_parse_skips_market_with_bad_token_json():
    raw = load_fixture("gamma_markets.json")
    broken = dict(raw[0])
    broken["outcomes"] = "not-json{{{"
    broken["clobTokenIds"] = "not-json{{{"
    market = parse_gamma_market(broken)
    assert market.tokens == []
    # Market itself still parses; only tokens are empty.
    assert market.condition_id == raw[0]["conditionId"]
