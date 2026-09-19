# Polyprism

Phase 0 closes the loop from Polymarket to Postgres. The API polls active markets and their order books on a schedule, stores both, and serves the latest stored book per token. Everything runs in paper mode. No signing, no orders, no live trading.

## Prerequisites

You need Python 3.13, uv, and Docker with the compose plugin. The demo uses ports 5432 (Postgres), 6379 (Redis), and 8000 (API), so stop anything already sitting on those first.

Copy the example env before you start:

```sh
cp .env.example .env
```

The defaults point at a local database and the public Polymarket APIs.

## Demo in five commands

Run these from the repo root on a fresh checkout:

```sh
make db-up       # starts Postgres and Redis in the background
make db-migrate  # applies the schema with alembic
make seed        # one Gamma plus CLOB pass, prints market/token/snapshot counts
make dev         # API on http://localhost:8000, scheduler polling in the background
make test        # offline unit suite, no network and no database
```

The seed already fills the database, so the endpoint below works right away. The dev server also keeps polling in the background, so snapshot rows keep growing while it runs.

## Reading the latest stored book

`GET /books/{token_id}` returns the newest stored snapshot for one token. Token ids are numeric strings (a YES or NO outcome), not market condition ids.

Grab a real token id from what you just seeded:

```sh
docker compose exec postgres psql -U polyprism -d polyprism \
  -c "SELECT token_id, ts FROM orderbook_snapshots ORDER BY ts DESC LIMIT 5;"
```

Then fetch it (replace the id with one from your query):

```sh
curl http://localhost:8000/books/12345678901234567890
```

You get back something like:

```json
{
  "token_id": "12345678901234567890",
  "timestamp": "2026-05-01T12:00:00Z",
  "bids": [{"price": 0.52, "size": 120.0}],
  "asks": [{"price": 0.53, "size": 95.0}],
  "best_bid": 0.52,
  "best_ask": 0.53
}
```

Two error cases to know. Unknown token returns 404 with the token id in the message. A non-numeric id like `/books/not-a-token` returns 422 from path validation.

## Tests

The default suite stays offline on purpose. It uses recorded Gamma and CLOB fixtures, fake clients, and a stubbed scheduler, so plain `make test` needs neither network nor Postgres.

```sh
make test-unit         # same as make test, everything except integration
make test-integration  # needs compose services up, hits a real Postgres
```

Integration tests carry the `integration` marker and are excluded from default runs in `pyproject.toml`. Run them after `make db-up` with:

```sh
uv run pytest -m integration -q
```

Live Polymarket checks live in one manual script only and pytest never collects it (the filename sits outside the `test_*.py` pattern on purpose):

```sh
make check-live
```

Only run that when you actually want to hit the public APIs.
