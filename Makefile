.PHONY: up down logs test eval lint migrate api mcp

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

test:
	uv run pytest

eval:
	uv run python -m ragcore.evals.runner

lint:
	uv run ruff check src/ tests/

migrate:
	uv run alembic upgrade head

api:
	uv run uvicorn ragcore.api.app:app --host 0.0.0.0 --port 8800

mcp:
	uv run python -m ragcore.mcp_server.app
