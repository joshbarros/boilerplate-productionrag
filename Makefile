.PHONY: up down logs test eval lint migrate

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
