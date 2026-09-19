.PHONY: dev test test-unit test-integration lint format db-up db-down db-migrate db-shell seed check-live

export PYTHONPATH := src

dev:
	uv run uvicorn polyprism.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -q

test-unit:
	uv run pytest -q -m "not integration"

test-integration:
	uv run pytest -q -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down

db-migrate:
	uv run alembic upgrade head

db-shell:
	docker compose exec postgres psql -U polyprism -d polyprism

seed:
	uv run python scripts/seed_db.py

check-live:
	uv run python scripts/check_live.py
